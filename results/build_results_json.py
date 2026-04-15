#!/usr/bin/env python3
"""
Build results/dab_results.json in the strict DataAgentBench submission format.

Walks:
  DataAgentBench/query_{dataset}/queryN/data_agent/run_{R}/final_agent.json

Extracts a final answer from common shapes:
- {"answer": "..."} (preferred)
- {"final_answer": "..."}
- {"trajectory": [... tool calls ...]} where tool/function name == "return_answer"

Writes:
  results/dab_results.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results"
DEFAULT_DAB = REPO_ROOT / "DataAgentBench"


def resolve_dab_root(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit)
    env = os.environ.get("DATAAGENTBENCH_ROOT")
    return Path(env) if env else DEFAULT_DAB


def iter_final_agent_files(dab_root: Path) -> List[Path]:
    out: List[Path] = []
    for dataset_dir in dab_root.glob("query_*"):
        if not dataset_dir.is_dir():
            continue
        for qdir in dataset_dir.glob("query*"):
            if not qdir.is_dir():
                continue
            for run_dir in (qdir / "data_agent").glob("run_*"):
                p = run_dir / "final_agent.json"
                if p.is_file():
                    out.append(p)
    out.sort()
    return out


def _load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def _extract_answer(obj: Any) -> Optional[str]:
    if isinstance(obj, dict):
        for k in ("answer", "final_answer"):
            v = obj.get(k)
            if isinstance(v, str):
                return v
        traj = obj.get("trajectory") or obj.get("messages") or obj.get("steps")
        ans = _extract_answer_from_trajectory(traj)
        if ans is not None:
            return ans
    if isinstance(obj, list):
        # Sometimes file is a list of steps/messages
        ans = _extract_answer_from_trajectory(obj)
        if ans is not None:
            return ans
    return None


def _extract_answer_from_trajectory(traj: Any) -> Optional[str]:
    if not isinstance(traj, list):
        return None
    # Look from the end for a return_answer tool call
    for step in reversed(traj):
        if not isinstance(step, dict):
            continue
        # Common shapes
        tool = step.get("tool") or step.get("tool_name") or step.get("name")
        if tool == "return_answer":
            args = step.get("args") or step.get("arguments") or {}
            if isinstance(args, dict) and isinstance(args.get("answer"), str):
                return args["answer"]
            if isinstance(step.get("answer"), str):
                return step["answer"]
        fn = step.get("function")
        if isinstance(fn, dict) and fn.get("name") == "return_answer":
            args = fn.get("arguments")
            if isinstance(args, dict) and isinstance(args.get("answer"), str):
                return args["answer"]
            if isinstance(args, str):
                try:
                    j = json.loads(args)
                    if isinstance(j, dict) and isinstance(j.get("answer"), str):
                        return j["answer"]
                except json.JSONDecodeError:
                    pass
    # Fallback: last string "content"/"output"
    for step in reversed(traj):
        if isinstance(step, dict):
            for k in ("content", "output", "text"):
                v = step.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
    return None


def parse_path_meta(p: Path) -> Tuple[str, str, str]:
    # p: .../query_{dataset}/queryN/data_agent/run_R/final_agent.json
    parts = p.parts
    dataset = ""
    query = ""
    run = ""

    for i, part in enumerate(parts):
        if part.startswith("query_") and dataset == "":
            dataset = part.replace("query_", "")
        if re.fullmatch(r"query\d+", part, re.IGNORECASE):
            query = re.sub(r"\D", "", part) or part.replace("query", "")
        if part.startswith("run_"):
            run = part.replace("run_", "")

    if not (dataset and query and run):
        raise ValueError(f"Could not parse dataset/query/run from path: {p}")
    return dataset, query, run


def main() -> int:
    parser = argparse.ArgumentParser(description="Build DAB submission results JSON from per-run artifacts.")
    parser.add_argument("--dab-root", default=None, help="Path to DataAgentBench checkout (or any folder containing query_*/)")
    args = parser.parse_args()

    dab_root = resolve_dab_root(args.dab_root)
    if not dab_root.is_dir():
        raise FileNotFoundError(f"DAB root not found: {dab_root}")

    files = iter_final_agent_files(dab_root)
    if not files:
        print(f"No final_agent.json files found under {dab_root}. Run eval/run_benchmark.py first.")
        return 1

    rows: List[Dict[str, str]] = []
    warnings: List[str] = []

    for p in files:
        dataset, query, run = parse_path_meta(p)
        try:
            obj = _load_json(p)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"[skip] {p}: failed to parse JSON: {e}")
            continue

        ans = _extract_answer(obj)
        if ans is None:
            warnings.append(f"[skip] {p}: could not extract answer")
            continue

        rows.append({"dataset": dataset, "query": str(query), "run": str(run), "answer": str(ans)})

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "dab_results.json"
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Summary
    datasets = sorted({r["dataset"] for r in rows})
    queries = sorted({(r["dataset"], r["query"]) for r in rows})
    print(f"Wrote {out_path}")
    print(f"Collected: datasets={len(datasets)} queries={len(queries)} total_runs={len(rows)}")
    if warnings:
        print("\nWarnings:")
        for w in warnings[:50]:
            print(w)
        if len(warnings) > 50:
            print(f"... {len(warnings) - 50} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

