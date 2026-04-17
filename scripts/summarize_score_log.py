#!/usr/bin/env python3
"""Build a strict benchmark summary markdown from a score log JSON file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _read_log(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(
            f"Warning: could not parse score log as JSON: {path} ({exc})",
            file=sys.stderr,
        )
        return []
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _latest_per_dataset(rows: list[dict]) -> list[dict]:
    latest: dict[str, dict] = {}
    for r in rows:
        ds = str(r.get("dataset", "")).strip()
        rid = str(r.get("run_id", "")).strip()
        if not ds:
            continue
        prev = latest.get(ds)
        if prev is None or rid > str(prev.get("run_id", "")):
            latest[ds] = r
    return [latest[k] for k in sorted(latest)]


def _fmt_ratio(passed: int, total: int) -> str:
    if total <= 0:
        return "0/0 (0.0000)"
    return f"{passed}/{total} ({passed/total:.4f})"


def build_summary(rows: list[dict], source_label: str) -> str:
    latest = _latest_per_dataset(rows)
    total_passed = sum(int(r.get("passed", 0)) for r in latest)
    total_total = sum(int(r.get("total_queries", 0)) for r in latest)
    total_failed = total_total - total_passed
    combined = (total_passed / total_total) if total_total else 0.0

    lines: list[str] = []
    lines.append("# Strict No-Leakage Score Summary")
    lines.append("")
    lines.append("## Source")
    lines.append("")
    lines.append(f"Generated from `{source_label}` only.")
    lines.append("This summary is isolated from historical mixed-mode runs.")
    lines.append("")
    lines.append("## Latest Snapshot (Most Recent Run Per Dataset)")
    lines.append("")
    lines.append("| Dataset | Run ID | Date | Strict pass@1 | Failed |")
    lines.append("|---|---|---|---:|---:|")
    for r in latest:
        ds = str(r.get("dataset", ""))
        rid = str(r.get("run_id", ""))
        date = str(r.get("date", ""))
        passed = int(r.get("passed", 0))
        total = int(r.get("total_queries", 0))
        failed = int(r.get("failed", total - passed))
        lines.append(f"| {ds} | `{rid}` | {date} | {_fmt_ratio(passed, total)} | {failed}/{total} |")

    lines.append("")
    lines.append(
        f"Combined latest: **{total_passed}/{total_total} passed, {total_failed}/{total_total} failed, combined pass@1 = {combined:.4f}**."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize benchmark score log")
    parser.add_argument("--score-log", required=True, help="Path to score log JSON")
    parser.add_argument("--out", required=True, help="Output markdown path")
    args = parser.parse_args()

    score_log = Path(args.score_log).resolve()
    out = Path(args.out).resolve()

    rows = _read_log(score_log)
    md = build_summary(rows, args.score_log)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md + "\n", encoding="utf-8")
    print(f"Wrote summary: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
