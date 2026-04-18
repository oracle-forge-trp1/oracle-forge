#!/usr/bin/env python3
"""
Pre-push checks for oracle-forge + optional DataAgentBench checkout validation.

Usage:
  python scripts/preflight_push_check.py
  python scripts/preflight_push_check.py --dab-root DataAgentBench
  python scripts/preflight_push_check.py --dab-root C:/path/to/DataAgentBench --check-data-files

Exits non-zero if a strict repo check fails. Missing DAB skips layout checks.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run(cmd: list[str], *, cwd: Path) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out


def _check_repo_scripts() -> list[str]:
    errors: list[str] = []
    for rel, args in (
        ("scripts/lint_kb_no_leakage.py", ["--strict"]),
        ("scripts/check_kb_integrity.py", ["--strict"]),
        ("scripts/verify_agent_context.py", ["--strict"]),
    ):
        script = REPO_ROOT / rel
        if not script.is_file():
            errors.append(f"missing {rel}")
            continue
        code, out = _run([sys.executable, str(script), *args], cwd=REPO_ROOT)
        if code != 0:
            errors.append(f"{rel} {' '.join(args)} failed (exit {code}):\n{out[-4000:]}")
    return errors


def _import_smoke() -> list[str]:
    errors: list[str] = []
    try:
        sys.path.insert(0, str(REPO_ROOT))
        sys.path.insert(0, str(REPO_ROOT / "agent"))
        import agent.data_agent as da  # noqa: WPS433

        if not hasattr(da, "run_agent") or not hasattr(da, "dispatch_tool"):
            errors.append("agent.data_agent missing run_agent / dispatch_tool")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"import agent.data_agent failed: {exc}")
    try:
        spec = importlib.util.spec_from_file_location("_of_harness", REPO_ROOT / "eval" / "harness.py")
        if spec is None or spec.loader is None:
            errors.append("cannot load eval/harness.py spec")
        else:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if not hasattr(mod, "run_harness"):
                errors.append("eval/harness.py missing run_harness")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"load eval/harness.py failed: {exc}")
    return errors


def _validate_dab_root(dab: Path) -> list[str]:
    errors: list[str] = []
    if not dab.is_dir():
        return [f"DAB root is not a directory: {dab}"]

    cs = dab / "common_scaffold"
    if not cs.is_dir():
        errors.append(f"Missing common_scaffold/ under {dab} (need full ucbepic/DataAgentBench clone).")

    query_dirs = sorted(p for p in dab.iterdir() if p.is_dir() and p.name.lower().startswith("query_"))
    if not query_dirs:
        errors.append(f"No query_* dataset folders under {dab}")
        return errors

    qdir_pat = re.compile(r"^query\d+$", re.I)
    for ds in query_dirs:
        if not (ds / "db_config.yaml").is_file():
            errors.append(f"{ds.name}: missing db_config.yaml")
        if not (ds / "db_description.txt").is_file():
            errors.append(f"{ds.name}: missing db_description.txt")
        sub = [p for p in ds.iterdir() if p.is_dir() and qdir_pat.match(p.name)]
        if not sub:
            errors.append(f"{ds.name}: no queryN/ subdirs (query1, …)")
            continue
        for qn in sorted(sub, key=lambda p: int(re.match(r"^query(\d+)$", p.name, re.I).group(1))):  # type: ignore[union-attr]
            if not (qn / "query.json").is_file():
                errors.append(f"{ds.name}/{qn.name}: missing query.json")
            if not (qn / "validate.py").is_file():
                errors.append(f"{ds.name}/{qn.name}: missing validate.py")

    return errors


def _validate_db_config_paths(dab: Path) -> list[str]:
    try:
        import yaml
    except ImportError:
        return ["PyYAML is required to validate db_config paths (install pyyaml)."]

    errors: list[str] = []
    for ds in sorted(p for p in dab.iterdir() if p.is_dir() and p.name.lower().startswith("query_")):
        cfg_path = ds / "db_config.yaml"
        if not cfg_path.is_file():
            continue
        try:
            config = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{ds.name}/db_config.yaml: parse error: {exc}")
            continue
        clients = (config or {}).get("db_clients") or {}
        if not isinstance(clients, dict):
            errors.append(f"{ds.name}/db_config.yaml: db_clients must be a mapping")
            continue
        for _logical, details in clients.items():
            if not isinstance(details, dict):
                continue
            dtype = (details.get("db_type") or "").lower()
            if dtype == "mongo":
                dump = details.get("dump_folder")
                if dump:
                    p = ds / dump
                    if not p.exists():
                        errors.append(f"{ds.name}: missing mongo dump_folder: {p}")
            elif dtype == "duckdb":
                rel = details.get("db_path")
                if rel:
                    p = ds / rel
                    if not p.is_file():
                        errors.append(f"{ds.name}: duckdb file missing (git LFS?): {p}")
            elif dtype == "sqlite":
                rel = details.get("db_path")
                if rel:
                    p = ds / rel
                    if not p.is_file():
                        errors.append(f"{ds.name}: sqlite file missing (git LFS?): {p}")
            elif dtype in ("postgres", "postgresql"):
                sqlf = details.get("sql_file")
                if sqlf:
                    p = ds / sqlf
                    if not p.is_file():
                        errors.append(f"{ds.name}: postgres sql_file missing: {p}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-push checks for oracle-forge + DAB layout")
    parser.add_argument(
        "--dab-root",
        default=None,
        help="Path to DataAgentBench (else DATAAGENTBENCH_ROOT or ./DataAgentBench if present)",
    )
    parser.add_argument(
        "--check-data-files",
        action="store_true",
        help="Verify DB files / mongo dumps / sql exist (needs full clone + git lfs pull)",
    )
    args = parser.parse_args()

    print("== Oracle Forge preflight ==")
    print(f"repo: {REPO_ROOT}")

    errs = _import_smoke()
    errs.extend(_check_repo_scripts())

    dab: Path | None = Path(args.dab_root).resolve() if args.dab_root else None
    if dab is None:
        env_dab = REPO_ROOT / "DataAgentBench"
        env_var = os.environ.get("DATAAGENTBENCH_ROOT", "").strip()
        if env_var:
            dab = Path(env_var).resolve()
        elif env_dab.is_dir():
            dab = env_dab.resolve()

    if dab is not None and dab.is_dir():
        print(f"dab_root:  {dab}")
        dab_errs = _validate_dab_root(dab)
        if dab_errs:
            errs.extend(dab_errs)
        elif args.check_data_files:
            path_errs = _validate_db_config_paths(dab)
            if path_errs:
                errs.extend(path_errs)
            else:
                print("dab_paths: db_config on-disk paths OK.")
        else:
            print("dab_paths: skipped (use --check-data-files for DB file / dump checks).")
    else:
        print(
            "dab_root:  (not found — skipped DAB layout)\n"
            "  Example (Windows): python scripts/preflight_push_check.py --dab-root DataAgentBench\n"
            "  Or set DATAAGENTBENCH_ROOT to an absolute path."
        )

    if not (REPO_ROOT / "mcp" / "toolbox_server.py").is_file():
        errs.append("missing mcp/toolbox_server.py")

    if errs:
        print("\nFAILURES:\n")
        for e in errs:
            print(f"- {e}\n")
        return 1

    print("\nAll preflight checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
