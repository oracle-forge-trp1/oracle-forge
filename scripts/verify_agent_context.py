#!/usr/bin/env python3
"""
Verify which KB layers would be injected into the agent system prompt.

Does not connect to databases (passes connections=None). Use this to confirm
strict runs still load CORE KB, CORRECTIONS LOG, and DOMAIN KNOWLEDGE unless
ORACLE_FORGE_STRICT_OMIT_KB=1.

Example:
  ORACLE_FORGE_STRICT_NO_LEAKAGE=1 python scripts/verify_agent_context.py --dataset yelp
  ORACLE_FORGE_STRICT_NO_LEAKAGE=1 ORACLE_FORGE_STRICT_OMIT_KB=1 python scripts/verify_agent_context.py --dataset yelp
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv(override=False)
    except ImportError:
        pass

    ap = argparse.ArgumentParser(description="Verify agent system-prompt KB layers.")
    ap.add_argument("--dataset", default="yelp", help="Dataset key (e.g. yelp, agnews)")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Set ORACLE_FORGE_STRICT_NO_LEAKAGE=1 for this process",
    )
    ap.add_argument(
        "--omit-kb",
        action="store_true",
        help="Set ORACLE_FORGE_STRICT_OMIT_KB=1 for this process",
    )
    args = ap.parse_args()

    if args.strict:
        os.environ["ORACLE_FORGE_STRICT_NO_LEAKAGE"] = "1"
    if args.omit_kb:
        os.environ["ORACLE_FORGE_STRICT_OMIT_KB"] = "1"

    # Import after env is set
    from agent.data_agent import _build_system_prompt

    db_config_path = str(REPO_ROOT / f"DataAgentBench/query_{args.dataset}/db_config.yaml")
    db_description = "(verify_agent_context placeholder — real harness passes db_description.txt)"
    text = _build_system_prompt(db_config_path, db_description, connections=None)

    checks = [
        ("AGENT.md (role)", "data analytics agent" in text.lower() or "Role" in text),
        ("CORE KB (METHODOLOGY)", "CORE KB (METHODOLOGY)" in text),
        ("CORRECTIONS LOG", "CORRECTIONS LOG" in text),
        ("DOMAIN KNOWLEDGE", f"DOMAIN KNOWLEDGE ({args.dataset})" in text),
        ("DATABASE DESCRIPTION", "DATABASE DESCRIPTION" in text),
    ]
    if args.strict:
        checks.append(("STRICT MODE banner", "STRICT MODE" in text))

    print("=== Oracle Forge — agent context layer check ===")
    print(f"dataset: {args.dataset}")
    print(f"ORACLE_FORGE_STRICT_NO_LEAKAGE={os.getenv('ORACLE_FORGE_STRICT_NO_LEAKAGE', '')!r}")
    print(f"ORACLE_FORGE_STRICT_OMIT_KB={os.getenv('ORACLE_FORGE_STRICT_OMIT_KB', '')!r}")
    print(f"built_prompt_chars: {len(text)}")
    print()
    for name, ok in checks:
        status = "OK" if ok else "MISSING"
        print(f"{status:8}  {name}")
    print()
    if args.omit_kb:
        expect_core = "CORE KB (METHODOLOGY)" not in text
        if not expect_core:
            print("NOTE: omit_kb set but CORE KB still present — check ORACLE_FORGE_STRICT_OMIT_KB handling.")
    elif args.strict and not all(c[1] for c in checks[:4]):
        print("WARNING: expected CORE KB + CORRECTIONS + DOMAIN in strict mode (omit_kb off).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
