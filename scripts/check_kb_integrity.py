#!/usr/bin/env python3
"""Validate KB discoverability, format, and basic non-leakage constraints."""

from __future__ import annotations

import argparse
import json
import re
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
KB_DOMAIN = REPO_ROOT / "kb" / "domain"
DEFAULT_DAB_ROOT = REPO_ROOT / "DataAgentBench"

CORE_DOCS = [
    "dab_schemas.md",
    "query_patterns.md",
    "join_keys.md",
    "unstructured_fields.md",
    "domain_terms.md",
]

RUNTIME_DOCS = [
    REPO_ROOT / "kb" / "corrections" / "corrections-log.md",
    REPO_ROOT / "probes" / "probes.md",
]

NON_RUNTIME_DOMAIN_DOCS = {
    "README.md",
    "CHANGELOG.md",
    "dab_dataset_risk_matrix.md",
}

BLOCKED_PATTERNS = {
    "query_label": re.compile(r"\bQ\d+\s*:", re.IGNORECASE),
    "expected_answer": re.compile(r"expected\s*answer|ground\s*truth", re.IGNORECASE),
    "forbidden_list": re.compile(r"forbidden\s+list|none\s+of\s+these\s+may\s+appear", re.IGNORECASE),
}


def check_markdown_heading(path: Path) -> list[str]:
    issues: list[str] = []
    if not path.exists():
        return [f"missing file: {path.relative_to(REPO_ROOT)}"]
    text = path.read_text(encoding="utf-8")
    if not text.lstrip().startswith("#"):
        issues.append(f"missing top-level markdown heading: {path.relative_to(REPO_ROOT)}")
    return issues


def lint_runtime_file(path: Path) -> list[str]:
    findings: list[str] = []
    if not path.exists():
        return [f"missing runtime KB file: {path.relative_to(REPO_ROOT)}"]
    text = path.read_text(encoding="utf-8")
    for name, pat in BLOCKED_PATTERNS.items():
        for m in pat.finditer(text):
            ln = text.count("\n", 0, m.start()) + 1
            line = text.splitlines()[ln - 1].strip().lower()
            # Allow negation policy statements.
            if "do not" in line:
                continue
            if "no expected answers" in line or "no ground-truth values" in line:
                continue
            findings.append(f"{path.relative_to(REPO_ROOT)}:{ln}: blocked {name}")
    return findings


def runtime_domain_docs() -> list[Path]:
    docs: list[Path] = []
    for p in sorted(KB_DOMAIN.glob("*.md")):
        if p.name in NON_RUNTIME_DOMAIN_DOCS:
            continue
        if p.name in CORE_DOCS:
            continue
        docs.append(p)
    return docs


def resolve_dab_root(cli_value: str | None) -> Path:
    if cli_value:
        return Path(cli_value)
    env_path = os.getenv("DAB_ROOT") or os.getenv("DATAAGENTBENCH_ROOT")
    if env_path:
        return Path(env_path)
    return DEFAULT_DAB_ROOT


def resolve_dataset_kb_doc(dataset_key: str) -> tuple[str, Path | None]:
    candidates = [f"{dataset_key}.md", f"{dataset_key.lower()}.md"]
    seen: set[str] = set()
    for name in candidates:
        if name in seen:
            continue
        seen.add(name)
        p = KB_DOMAIN / name
        if p.exists():
            return name, p
    return candidates[-1], None


def check_dataset_docs(dab_root: Path) -> tuple[list[str], dict[str, str]]:
    issues: list[str] = []
    mapping: dict[str, str] = {}
    if not dab_root.exists():
        return ["DataAgentBench directory not found"], mapping

    for ds in sorted(p for p in dab_root.glob("query_*") if p.is_dir()):
        dataset_key = ds.name.replace("query_", "")
        doc_name, doc_path = resolve_dataset_kb_doc(dataset_key)
        mapping[dataset_key] = doc_name
        if doc_path is None:
            issues.append(
                f"missing dataset KB doc for {dataset_key}: "
                f"tried kb/domain/{dataset_key}.md and kb/domain/{dataset_key.lower()}.md"
            )
    return issues, mapping


def main() -> int:
    parser = argparse.ArgumentParser(description="KB integrity/discoverability checks")
    parser.add_argument("--json", action="store_true", help="print JSON report")
    parser.add_argument("--strict", action="store_true", help="exit non-zero on issues")
    parser.add_argument("--dab-root", default=None, help="Path to DataAgentBench root")
    args = parser.parse_args()
    dab_root = resolve_dab_root(args.dab_root)

    issues: list[str] = []

    for name in CORE_DOCS:
        issues.extend(check_markdown_heading(KB_DOMAIN / name))

    dataset_issues, dataset_map = check_dataset_docs(dab_root)
    issues.extend(dataset_issues)

    for p in [*runtime_domain_docs(), *RUNTIME_DOCS]:
        issues.extend(check_markdown_heading(p))
        issues.extend(lint_runtime_file(p))

    report = {
        "issues": issues,
        "core_docs_checked": CORE_DOCS,
        "dataset_kb_map": dataset_map,
        "dab_root": str(dab_root),
        "status": "PASS" if not issues else "FAIL",
    }

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"KB integrity status: {report['status']}")
        if issues:
            for i in issues:
                print(f"- {i}")

    if args.strict and issues:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
