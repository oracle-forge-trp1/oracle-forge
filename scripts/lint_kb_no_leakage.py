#!/usr/bin/env python3
"""Simple leakage lint for runtime-injectable KB files.

Fails when files contain benchmark-shaped leakage patterns such as query labels,
explicit expected answers, ground-truth mentions, or forbidden-list wording.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CORE_DOMAIN_DOCS = {
    "dab_schemas.md",
    "query_patterns.md",
    "join_keys.md",
    "unstructured_fields.md",
    "domain_terms.md",
}

NON_RUNTIME_DOMAIN_DOCS = {
    "README.md",
    "CHANGELOG.md",
    "dab_dataset_risk_matrix.md",
}

PATTERNS = {
    "query_label": re.compile(r"\bQ\d+\s*:", re.IGNORECASE),
    "ground_truth": re.compile(r"ground\s*truth|expected\s*answer", re.IGNORECASE),
    "forbidden_list": re.compile(r"forbidden\s+list|none\s+of\s+these\s+may\s+appear", re.IGNORECASE),
    "score_hint": re.compile(r"matches\s+ground\s+truth|post-fix\s+score", re.IGNORECASE),
}


def lint_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    findings: list[str] = []
    for name, pattern in PATTERNS.items():
        for m in pattern.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            line = text.splitlines()[line_no - 1].strip()
            line_lower = line.lower()
            # Policy negations like "do not store ... ground-truth" are expected.
            if "do not" in line_lower and name in {"ground_truth", "forbidden_list", "score_hint"}:
                continue
            if "no expected answers" in line_lower or "no ground-truth values" in line_lower:
                continue
            findings.append(f"{path.relative_to(REPO_ROOT)}:{line_no}: {name}: {line}")
    return findings


def build_targets() -> list[Path]:
    targets: list[Path] = []
    domain_dir = REPO_ROOT / "kb" / "domain"
    for p in sorted(domain_dir.glob("*.md")):
        if p.name in CORE_DOMAIN_DOCS or p.name in NON_RUNTIME_DOMAIN_DOCS:
            continue
        targets.append(p)
    targets.extend(
        [
            REPO_ROOT / "kb" / "corrections" / "corrections-log.md",
            REPO_ROOT / "probes" / "probes.md",
        ]
    )
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(description="Leakage lint for runtime KB files")
    parser.add_argument("--strict", action="store_true", help="exit non-zero on findings")
    args = parser.parse_args()

    all_findings: list[str] = []
    for target in build_targets():
        if target.exists():
            all_findings.extend(lint_file(target))

    if all_findings:
        print("KB leakage lint findings:")
        for f in all_findings:
            print(f"- {f}")
        return 1 if args.strict else 0

    print("KB leakage lint: PASS (no blocked patterns found)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
