"""
utils/benchmark_harness.py — Benchmark Harness Wrapper

Thin callable wrapper around eval/harness.py that exposes a simple
run_dataset(dataset, n_trials) interface for use in notebooks, scripts,
and automated pipelines.

The heavy lifting lives in eval/harness.py. This module adds:
  - A clean function API (no argparse required)
  - Multi-trial looping with score aggregation
  - Pass@k computation across trials
  - JSON export of aggregated results

Usage:
    from utils.benchmark_harness import BenchmarkHarness

    harness = BenchmarkHarness(
        agent_module="agent.data_agent",
        dab_root="/shared/oracle-forge/DataAgentBench",
    )

    # Single dataset, one trial
    result = harness.run_dataset("yelp")
    print(result["pass_at_1"])

    # Multiple trials (required for DAB submission: n >= 5)
    results = harness.run_trials("yelp", n_trials=5)
    print(results["pass_at_k"])   # fraction of queries that pass in at least 1 trial

    # Export to JSON for DAB submission
    harness.export_results(results, output_path="results/team_oracle_forge_results.json")
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Ensure repo root is on sys.path so eval.harness is importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from eval.harness import run_harness, SCORE_LOG  # noqa: E402
except ImportError:
    # Allow import when running tests from utils/ directory
    import importlib.util, pathlib
    _harness_path = pathlib.Path(__file__).resolve().parent.parent / "eval" / "harness.py"
    _spec = importlib.util.spec_from_file_location("eval.harness", _harness_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    run_harness = _mod.run_harness
    SCORE_LOG = _mod.SCORE_LOG


class BenchmarkHarness:
    """
    Callable wrapper around eval/harness.py for programmatic benchmark execution.
    """

    def __init__(
        self,
        agent_module: str = "agent.data_agent",
        dab_root: Optional[str] = None,
        timeout_sec: float = 240.0,
        score_log_path: Optional[str] = None,
    ) -> None:
        """
        Args:
            agent_module: Python module path exposing run_agent().
                          Default: "agent.data_agent"
            dab_root: Path to the DataAgentBench checkout.
                      Default: env DATAAGENTBENCH_ROOT or ./DataAgentBench
            timeout_sec: Per-query agent timeout in seconds. Default: 240.
            score_log_path: Path to append-only score log JSON.
                            Default: eval/score_log.json
        """
        self.agent_module = agent_module
        self.dab_root = Path(
            dab_root
            or os.environ.get("DATAAGENTBENCH_ROOT", str(_REPO_ROOT / "DataAgentBench"))
        )
        self.timeout_sec = timeout_sec
        self.score_log_path = Path(score_log_path or SCORE_LOG)

    def run_dataset(
        self,
        dataset: str,
        run_id: Optional[str] = None,
        dummy: bool = False,
    ) -> dict[str, Any]:
        """
        Run the agent against all queries in one dataset (single trial).

        Args:
            dataset: Dataset key (e.g. "yelp", "stockindex"). Maps to
                     DataAgentBench/query_{dataset}/ directory.
            run_id: Optional run identifier. Auto-generated if None.
            dummy: Use stub agent returning "No answer" (for harness testing).

        Returns:
            Run record dict with keys: run_id, dataset, pass_at_1, passed,
            failed, total_queries, results (list of per-query dicts).
        """
        logger.info(
            "BenchmarkHarness.run_dataset: dataset=%s agent=%s",
            dataset,
            self.agent_module if not dummy else "dummy",
        )
        return run_harness(
            dataset=dataset,
            dab_root=self.dab_root,
            agent_module=self.agent_module if not dummy else None,
            dummy=dummy,
            timeout_sec=self.timeout_sec,
            run_id=run_id,
            score_log_path=self.score_log_path,
        )

    def run_trials(
        self,
        dataset: str,
        n_trials: int = 5,
    ) -> dict[str, Any]:
        """
        Run n_trials independent trials on a dataset and compute pass@k statistics.

        DAB submission requires n >= 5 trials per query (n >= 50 for full benchmark).

        Args:
            dataset: Dataset key (e.g. "yelp").
            n_trials: Number of independent trials. Default: 5.

        Returns:
            Aggregated result dict with keys:
              - dataset: dataset name
              - n_trials: number of trials run
              - trial_runs: list of individual run_harness results
              - pass_at_1: mean pass@1 across all trials
              - pass_at_k: fraction of queries that pass in at least 1 trial
              - query_pass_counts: {query_id: pass_count} across trials
        """
        logger.info(
            "BenchmarkHarness.run_trials: dataset=%s n_trials=%d", dataset, n_trials
        )
        trial_runs: list[dict[str, Any]] = []
        query_pass_counts: dict[str, int] = {}

        for trial_num in range(n_trials):
            today = datetime.now(timezone.utc).date().isoformat()
            run_id = f"{today}-trial{trial_num:02d}"
            logger.info("Trial %d/%d (run_id=%s)", trial_num + 1, n_trials, run_id)

            run = self.run_dataset(dataset, run_id=run_id)
            trial_runs.append(run)

            for result in run.get("results", []):
                qid = result.get("query_id", "")
                if result.get("passed"):
                    query_pass_counts[qid] = query_pass_counts.get(qid, 0) + 1

        # Aggregate statistics
        mean_pass_at_1 = (
            sum(r.get("pass_at_1", 0.0) for r in trial_runs) / len(trial_runs)
            if trial_runs else 0.0
        )

        all_query_ids = {
            r.get("query_id")
            for run in trial_runs
            for r in run.get("results", [])
        }
        pass_at_k = (
            sum(1 for qid in all_query_ids if query_pass_counts.get(qid, 0) > 0)
            / len(all_query_ids)
            if all_query_ids else 0.0
        )

        return {
            "dataset": dataset,
            "n_trials": n_trials,
            "trial_runs": trial_runs,
            "pass_at_1": round(mean_pass_at_1, 4),
            "pass_at_k": round(pass_at_k, 4),
            "query_pass_counts": query_pass_counts,
        }

    def export_results(
        self,
        trial_results: dict[str, Any],
        output_path: str,
    ) -> None:
        """
        Export multi-trial results to a JSON file in the DAB submission format.

        Each entry represents one query × one trial:
          {"dataset": "yelp", "query": "1", "run": "0", "answer": "3.55"}

        Args:
            trial_results: Dict returned by run_trials().
            output_path: Path to write the results JSON.
        """
        entries: list[dict[str, str]] = []
        dataset = trial_results.get("dataset", "unknown")

        for trial_idx, run in enumerate(trial_results.get("trial_runs", [])):
            for result in run.get("results", []):
                qid = str(result.get("query_id", "")).replace("query", "")
                entries.append({
                    "dataset": dataset,
                    "query": qid,
                    "run": str(trial_idx),
                    "answer": str(result.get("agent_answer", "")),
                })

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(entries, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        logger.info("BenchmarkHarness.export_results: wrote %d entries to %s", len(entries), out_path)
        print(f"Exported {len(entries)} result entries to {out_path}")
