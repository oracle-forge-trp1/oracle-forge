#!/usr/bin/env python3
"""Generate a reproducible markdown report for the latest benchmark run stamp.

Reads eval/score_log.json, finds the latest run stamp shared by dataset entries,
and writes results/run_reports/run_report_<stamp>.md.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

RUN_ID_STAMPED_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{8}-\d{6})-(.+)$")
RUN_ID_SIMPLE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{3})$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate markdown report for latest score_log run stamp")
    parser.add_argument("--score-log", default="eval/score_log.json", help="Path to score_log.json")
    parser.add_argument("--output-dir", default="results/run_reports", help="Directory for generated markdown reports")
    return parser.parse_args()


def load_runs(score_log_path: Path) -> list[dict[str, Any]]:
    if not score_log_path.exists():
        raise FileNotFoundError(f"score log not found: {score_log_path}")
    data = json.loads(score_log_path.read_text())
    if not isinstance(data, list):
        raise ValueError("score_log.json must be a JSON array")
    return [r for r in data if isinstance(r, dict)]


def get_stamp(run: dict[str, Any]) -> str | None:
    run_id = str(run.get("run_id", ""))
    m = RUN_ID_STAMPED_RE.match(run_id)
    if m:
        # Legacy multi-dataset runs share this timestamp stamp.
        return m.group(2)
    m2 = RUN_ID_SIMPLE_RE.match(run_id)
    if m2:
        # Newer harness emits YYYY-MM-DD-NNN (single dataset per run).
        # Use full run_id as the grouping key so latest run is reportable.
        return run_id
    return None


def latest_stamp(runs: list[dict[str, Any]]) -> str:
    for run in reversed(runs):
        stamp = get_stamp(run)
        if stamp:
            return stamp
    raise ValueError("No parseable run_id stamps found in score_log")


def collect_stamp_runs(runs: list[dict[str, Any]], stamp: str) -> list[dict[str, Any]]:
    out = [r for r in runs if get_stamp(r) == stamp]
    out.sort(key=lambda x: str(x.get("dataset", "")))
    return out


def pct(n: int, d: int) -> str:
    if d == 0:
        return "0.00%"
    return f"{(n / d) * 100:.2f}%"


def build_markdown(stamp_runs: list[dict[str, Any]], stamp: str, generated_at: str) -> str:
    total_q = sum(int(r.get("total_queries", 0)) for r in stamp_runs)
    total_pass = sum(int(r.get("passed", 0)) for r in stamp_runs)
    total_strict_pass = sum(int(r.get("strict_passed", 0)) for r in stamp_runs)
    total_repaired = sum(
        1
        for r in stamp_runs
        for q in r.get("results", [])
        if isinstance(q, dict) and q.get("repaired") is True
    )

    lines: list[str] = []
    lines.append(f"# Benchmark Run Report — {stamp}")
    lines.append("")
    lines.append(f"Generated: {generated_at}")
    lines.append("")
    lines.append("## Combined Summary")
    lines.append("")
    lines.append(f"- Datasets: {', '.join(str(r.get('dataset')) for r in stamp_runs)}")
    lines.append(f"- Queries: {total_q}")
    lines.append(f"- Final pass@1 (post-repair): {total_pass}/{total_q} ({pct(total_pass, total_q)})")
    lines.append(f"- Strict pass@1 (pre-repair): {total_strict_pass}/{total_q} ({pct(total_strict_pass, total_q)})")
    lines.append(f"- Repaired queries: {total_repaired}/{total_q}")
    lines.append("")
    lines.append("## Dataset Summary")
    lines.append("")
    lines.append("| Dataset | Final | Strict | Repaired | LLM | Iterations | Hints | Root |")
    lines.append("|---|---:|---:|---:|---|---:|---|---|")
    for r in stamp_runs:
        total = int(r.get("total_queries", 0))
        passed = int(r.get("passed", 0))
        strict_passed = int(r.get("strict_passed", 0))
        repaired = sum(1 for q in r.get("results", []) if isinstance(q, dict) and q.get("repaired") is True)
        meta = r.get("run_meta", {}) if isinstance(r.get("run_meta"), dict) else {}
        lines.append(
            "| "
            f"{r.get('dataset')} | "
            f"{passed}/{total} ({pct(passed, total)}) | "
            f"{strict_passed}/{total} ({pct(strict_passed, total)}) | "
            f"{repaired}/{total} | "
            f"{meta.get('llm', '')} | "
            f"{meta.get('iterations', '')} | "
            f"{meta.get('use_hints', '')} | "
            f"{meta.get('root_name', '')} |"
        )

    lines.append("")
    lines.append("## Query Details")
    lines.append("")
    for r in stamp_runs:
        dataset = str(r.get("dataset", ""))
        lines.append(f"### {dataset}")
        lines.append("")
        lines.append("| Query | Final | Strict | Repaired | Terminate | Calls | Strict Reason | Final Reason |")
        lines.append("|---|---|---|---|---|---:|---|---|")
        for q in sorted(r.get("results", []), key=lambda x: int(str(x.get("query_id", "query0")).replace("query", "") or 0)):
            if not isinstance(q, dict):
                continue
            final_ok = "PASS" if q.get("passed") else "FAIL"
            strict_ok = "PASS" if q.get("strict_passed") else "FAIL"
            repaired = "yes" if q.get("repaired") else "no"
            qid = str(q.get("query_id", ""))
            term = str(q.get("terminate_reason", ""))
            calls = int(q.get("llm_call_count", 0) or 0)
            strict_msg = str(q.get("strict_validation_message", "")).replace("|", "/")
            final_msg = str(q.get("validation_message", "")).replace("|", "/")
            lines.append(f"| {qid} | {final_ok} | {strict_ok} | {repaired} | {term} | {calls} | {strict_msg} | {final_msg} |")
        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    score_log_path = (repo_root / args.score_log).resolve()
    output_dir = (repo_root / args.output_dir).resolve()

    runs = load_runs(score_log_path)
    stamp = latest_stamp(runs)
    stamp_runs = collect_stamp_runs(runs, stamp)

    md = build_markdown(stamp_runs, stamp, datetime.now().isoformat(timespec="seconds"))
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f"run_report_{stamp}.md"
    out.write_text(md)

    print(f"Generated report: {out}")
    print(f"Datasets in report: {', '.join(str(r.get('dataset')) for r in stamp_runs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
