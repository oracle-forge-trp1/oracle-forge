#!/usr/bin/env python3
import argparse
import csv
import subprocess
import sys
from pathlib import Path

def run_agent(query: str, agent_cmd: str) -> str:
    cmd = agent_cmd.format(query=query)
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print("Agent command failed:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    return result.stdout.strip()

def main():
    parser = argparse.ArgumentParser(description="Evaluation harness scaffold")
    parser.add_argument("--query", required=True)
    parser.add_argument("--agent-cmd", required=True)
    parser.add_argument("--ground-truth", default="ground_truth.csv")
    parser.add_argument("--validator", default="validate.py")
    args = parser.parse_args()

    gt_path = Path(args.ground_truth)
    validator_path = Path(args.validator)

    if not gt_path.exists():
        print(f"Missing ground truth file: {gt_path}", file=sys.stderr)
        sys.exit(1)

    if not validator_path.exists():
        print(f"Missing validator file: {validator_path}", file=sys.stderr)
        sys.exit(1)

    answer = run_agent(args.query, args.agent_cmd)
    print("\n=== AGENT ANSWER ===")
    print(answer)

    matched_row = None
    with gt_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("query", "").strip() == args.query.strip():
                matched_row = row
                break

    if matched_row is None:
        print(f'No matching query found in {gt_path}: "{args.query}"', file=sys.stderr)
        sys.exit(1)

    expected = matched_row.get("answer", "") or matched_row.get("ground_truth", "")
    print("\n=== EXPECTED ===")
    print(expected)

    result = subprocess.run(
        [
            sys.executable,
            str(validator_path),
            "--query", args.query,
            "--predicted", answer,
            "--expected", expected,
        ],
        text=True,
    )
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
