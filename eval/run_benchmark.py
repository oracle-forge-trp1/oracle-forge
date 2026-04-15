#!/usr/bin/env python3
"""
Batch runner to generate per-query artifacts for DAB submission packaging.

This script runs the repo agent module against DAB query folders and writes:

  DataAgentBench/query_{dataset}/queryN/data_agent/run_{R}/final_agent.json

The JSON is intentionally simple and stable:
  {
    "dataset": "yelp",
    "query": "1",
    "run": "0",
    "answer": "...",
    "agent_module": "agent.data_agent",
    "model": "anthropic/claude-haiku-4.5",
    "created_at": "..."
  }

Then `results/build_results_json.py` can package these into results/dab_results.json.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DAB = REPO_ROOT / "DataAgentBench"


def resolve_dab_root(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit)
    env = os.environ.get("DATAAGENTBENCH_ROOT")
    if env:
        return Path(env)
    return DEFAULT_DAB


def iter_query_dirs(dataset_root: Path) -> list[Path]:
    qdirs = [p for p in dataset_root.iterdir() if p.is_dir() and p.name.lower().startswith("query")]
    # Expect query1, query2, ...
    def key(p: Path) -> int:
        s = "".join(ch for ch in p.name if ch.isdigit())
        return int(s) if s else 0

    qdirs.sort(key=key)
    return qdirs


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _ensure_import_paths() -> None:
    agent_dir = REPO_ROOT / "agent"
    for p in (str(REPO_ROOT), str(agent_dir)):
        if p not in os.sys.path:
            os.sys.path.insert(0, p)


def run_one(
    *,
    agent_module: str,
    question: str,
    db_config_path: str,
    db_description: str,
) -> str:
    mod = importlib.import_module(agent_module)
    fn = getattr(mod, "run_agent")
    return str(fn(question, db_config_path, db_description))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DAB queries in batch and write run artifacts.")
    parser.add_argument("--dataset", required=True, help='Dataset key like "yelp" (folder query_yelp/)')
    parser.add_argument("--dab-root", default=None, help="Path to DataAgentBench checkout")
    parser.add_argument("--agent-module", default="agent.data_agent", help="Agent module exposing run_agent()")
    parser.add_argument("--trials", type=int, default=5, help="Trials per query (minimum 5 for final submission)")
    parser.add_argument("--start-run", type=int, default=0, help="Start run index (default 0)")
    parser.add_argument("--only-queries", default=None, help='Comma-separated query numbers, e.g. "1,3,7"')
    parser.add_argument("--model", default=None, help="OpenRouter model name (sets OPENROUTER_MODEL)")
    args = parser.parse_args()

    if args.model:
        os.environ["OPENROUTER_MODEL"] = args.model

    dab_root = resolve_dab_root(args.dab_root)
    dataset_root = dab_root / f"query_{args.dataset}"
    if not dataset_root.is_dir():
        raise FileNotFoundError(f"Missing dataset directory: {dataset_root}")

    only: Optional[set[str]] = None
    if args.only_queries:
        only = {q.strip() for q in args.only_queries.split(",") if q.strip()}

    _ensure_import_paths()

    created_total = 0
    for qdir in iter_query_dirs(dataset_root):
        qnum = "".join(ch for ch in qdir.name if ch.isdigit()) or qdir.name.replace("query", "")
        if only is not None and qnum not in only:
            continue

        query_json = qdir / "query.json"
        db_config = dataset_root / "db_config.yaml"
        db_desc = dataset_root / "db_description.txt"

        if not query_json.is_file():
            print(f"[skip] {query_json} missing")
            continue
        if not db_config.is_file() or not db_desc.is_file():
            raise FileNotFoundError(f"Missing db_config.yaml or db_description.txt under {dataset_root}")

        question_raw = _read_text(query_json).strip()
        if question_raw.startswith("{"):
            try:
                qobj = json.loads(question_raw)
                if isinstance(qobj, dict) and isinstance(qobj.get("question"), str):
                    question = qobj["question"]
                else:
                    question = question_raw
            except json.JSONDecodeError:
                question = question_raw
        else:
            question = question_raw

        db_description = _read_text(db_desc)

        for r in range(args.start_run, args.start_run + args.trials):
            out_dir = qdir / "data_agent" / f"run_{r}"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / "final_agent.json"

            # Skip if already exists (idempotent)
            if out_path.is_file() and out_path.stat().st_size > 0:
                continue

            try:
                answer = run_one(
                    agent_module=args.agent_module,
                    question=question,
                    db_config_path=str(db_config),
                    db_description=db_description,
                )
            except Exception as e:  # noqa: BLE001
                answer = f"Agent error: {e!r}"

            record = {
                "dataset": args.dataset,
                "query": str(qnum),
                "run": str(r),
                "answer": answer,
                "agent_module": args.agent_module,
                "model": os.environ.get("OPENROUTER_MODEL"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            created_total += 1
            print(f"[wrote] {out_path}")

    print(f"\nDone. Artifacts written: {created_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

