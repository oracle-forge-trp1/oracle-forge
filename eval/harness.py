#!/usr/bin/env python3
"""
DataAgentBench evaluation harness.

Example:
  python eval/harness.py --dataset yelp --agent-module agent.data_agent
  python eval/harness.py --dataset yelp --dummy

Env:
  ORACLE_FORGE_HARNESS_REUSE_MCP — if set to 1/true, reuse an MCP server already
 listening on MCP_URL (default http://127.0.0.1:5000/mcp). Otherwise the harness
  starts a dedicated MCP on a free port and passes MCP_URL to each agent child (avoids wrong db_config/registry from another process on :5000).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = Path(__file__).resolve().parent
AGENT_DIR = REPO_ROOT / "agent"
CHILD_SCRIPT = EVAL_DIR / "agent_runner_child.py"
DEFAULT_DAB = str(REPO_ROOT / "DataAgentBench")
SCORE_LOG = EVAL_DIR / "score_log.json"
QUERY_TIMEOUT_SEC = 240

# Per-dataset timeouts override the default. CLI --timeout still takes precedence.
# Rationale: crmarenapro (6 DBs, 13 queries, complex joins) regularly needs 6-7 min.
# pancancer_atlas, deps_dev_v1, github_repos need ~5 min for heavy reasoning steps.
DATASET_TIMEOUT_SEC: dict[str, float] = {
    "crmarenapro":     420,   # 6 DBs, most complex dataset
    "pancancer_atlas": 300,   # molecular + clinical cross-DB, chi-square calcs
    "deps_dev_v1":     300,   # 3-table chain join + JSON parsing + timestamp math
    "github_repos":    300,   # large content table, commit parsing
}
MCP_SERVER_SCRIPT = REPO_ROOT / "mcp" / "toolbox_server.py"
MCP_HEALTH_URL = os.getenv("MCP_URL", "http://127.0.0.1:5000/mcp").replace("/mcp", "/health")


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _mcp_is_up_at(health_url: str) -> bool:
    try:
        with urllib.request.urlopen(health_url, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def _mcp_is_up() -> bool:
    return _mcp_is_up_at(MCP_HEALTH_URL)


def _start_mcp_server(db_config_path: Optional[str] = None) -> tuple[Optional[subprocess.Popen], Optional[str]]:
    """
    Start the MCP server and return (proc, mcp_rpc_url).

    mcp_rpc_url is the JSON-RPC endpoint (e.g. http://127.0.0.1:PORT/mcp) for the agent
    child. It is None when reusing an existing server on the default MCP_URL (see
    ORACLE_FORGE_HARNESS_REUSE_MCP).

    By default the harness binds an ephemeral port so a stale toolbox on :5000 cannot
    serve the wrong db_config/registry for this dataset.
    """
    if not MCP_SERVER_SCRIPT.is_file():
        raise RuntimeError(f"MCP server script not found at {MCP_SERVER_SCRIPT}")

    reuse = os.getenv("ORACLE_FORGE_HARNESS_REUSE_MCP", "").strip().lower() in {
        "1", "true", "yes", "on",
    }

    if reuse and _mcp_is_up():
        print("[harness] MCP server already running (ORACLE_FORGE_HARNESS_REUSE_MCP).", flush=True)
        return None, None

    env = os.environ.copy()
    if db_config_path:
        env["ORACLE_FORGE_REGISTER_ONLY_DB_CONFIG"] = str(Path(db_config_path).resolve())

    if reuse:
        print("[harness] Starting MCP server on default MCP_PORT ...", flush=True)
        proc = subprocess.Popen(
            [sys.executable, str(MCP_SERVER_SCRIPT)],
            cwd=str(REPO_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        rpc_url = os.getenv("MCP_URL", "http://127.0.0.1:5000/mcp").rstrip("/")
        if not rpc_url.endswith("/mcp"):
            rpc_url = rpc_url + "/mcp"
        health_url = rpc_url.replace("/mcp", "/health")
    else:
        port = _find_free_port()
        env["MCP_PORT"] = str(port)
        print(f"[harness] Starting dedicated MCP server on port {port} ...", flush=True)
        proc = subprocess.Popen(
            [sys.executable, str(MCP_SERVER_SCRIPT)],
            cwd=str(REPO_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        rpc_url = f"http://127.0.0.1:{port}/mcp"
        health_url = f"http://127.0.0.1:{port}/health"

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if _mcp_is_up_at(health_url):
            print(f"[harness] MCP server ready at {rpc_url} (pid {proc.pid}).", flush=True)
            return proc, rpc_url
        if proc.poll() is not None:
            raise RuntimeError("MCP server exited immediately on startup — check mcp/toolbox_server.py logs")
        time.sleep(0.25)

    proc.terminate()
    raise RuntimeError("MCP server did not become ready within 10s")


def _stop_mcp_server(proc: Optional[subprocess.Popen]) -> None:
    if proc is None:
        return
    print(f"[harness] Stopping MCP server (pid {proc.pid}) ...", flush=True)
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _ensure_import_paths() -> None:
    for p in (str(REPO_ROOT), str(AGENT_DIR)):
        if p not in sys.path:
            sys.path.insert(0, p)


def _check_llm_api() -> Optional[str]:
    """
    Quick sanity check: verify the LLM API key is usable before running queries.
    Returns None if OK, or an error string if the key is exhausted / invalid.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv(override=False)
    except ImportError:
        pass

    # Default behavior: prefer OpenAI if OPENAI_API_KEY is present.
    llm_provider = os.getenv("ORACLE_FORGE_LLM_PROVIDER", "").strip().lower()
    has_openai = bool(os.getenv("OPENAI_API_KEY", "").strip())
    if llm_provider in ("openrouter", "open_router"):
        has_openai = False

    if llm_provider in ("openai", "open_ai") or (not llm_provider and has_openai):
        api_key = os.getenv("OPENAI_API_KEY", "")
        model = os.getenv("OPENAI_MODEL", "gpt-4.1")
        url = "https://api.openai.com/v1/chat/completions"
        if not api_key:
            return "OPENAI_API_KEY not set in environment or .env"
    else:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-haiku-4.5")
        url = "https://openrouter.ai/api/v1/chat/completions"
        if not api_key:
            return "ANTHROPIC_API_KEY not set in environment or .env"

    try:
        import urllib.request as _req
        import json as _json
        payload = _json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }).encode()
        request = _req.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        with _req.urlopen(request, timeout=10) as resp:
            if resp.status == 200:
                return None
            body = resp.read().decode()
            return f"API returned HTTP {resp.status}: {body[:200]}"
    except Exception as exc:
        msg = str(exc)
        if "403" in msg and "limit" in msg.lower():
            if llm_provider in ("openai", "open_ai"):
                return f"OpenAI access blocked (HTTP 403) — check account/quota. Details: {msg[:200]}"
            return (
                "OpenRouter weekly token limit exceeded (HTTP 403). "
                "Update ANTHROPIC_API_KEY in .env with a fresh key, or wait for the weekly reset. "
                f"Details: {msg[:200]}"
            )
        if "401" in msg:
            if llm_provider in ("openai", "open_ai"):
                return f"API authentication failed (HTTP 401) — check OPENAI_API_KEY in .env. Details: {msg[:200]}"
            return f"API authentication failed (HTTP 401) — check ANTHROPIC_API_KEY in .env. Details: {msg[:200]}"
        return f"API health check failed: {msg[:300]}"


def discover_query_dirs(dataset_root: Path) -> List[Path]:
    dirs = [p for p in dataset_root.iterdir() if p.is_dir() and re.match(r"^query\d+$", p.name, re.I)]
    dirs.sort(key=lambda p: int(re.match(r"^query(\d+)$", p.name, re.I).group(1)))
    return dirs


def load_question(query_json: Path) -> str:
    raw = query_json.read_text(encoding="utf-8").strip()
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        for key in ("question", "query", "text", "nl_query"):
            v = data.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return raw


def load_validate_fn(validate_py: Path, *, dab_root: Path) -> Callable[..., Any]:
    mod_name = f"dab_validate_{validate_py.parent.name}"
    # DAB validators often import helpers like `common_scaffold.*`.
    # Ensure the DataAgentBench checkout is importable.
    dab_root = dab_root.resolve()
    dab_root_str = str(dab_root)
    if dab_root_str not in sys.path:
        sys.path.insert(0, dab_root_str)
    cs = dab_root / "common_scaffold"
    if not cs.is_dir():
        raise ImportError(
            f"DataAgentBench root {dab_root} is missing the `common_scaffold/` package. "
            "Use a full clone of ucbepic/DataAgentBench (not a partial copy) or set --dab-root / DATAAGENTBENCH_ROOT correctly."
        )
    spec = importlib.util.spec_from_file_location(mod_name, validate_py)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load spec for {validate_py}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = getattr(mod, "validate", None)
    if fn is None or not callable(fn):
        raise AttributeError(f"{validate_py} has no callable validate()")
    return fn


def run_validate(validate_fn: Callable[..., Any], agent_answer: str) -> Tuple[bool, str]:
    out = validate_fn(agent_answer)
    if isinstance(out, tuple):
        if len(out) >= 2:
            return bool(out[0]), str(out[1])
        if len(out) == 1:
            return bool(out[0]), ""
    return bool(out), ""


def invoke_agent_subprocess(
    *,
    module_name: str,
    query: str,
    db_config_path: str,
    db_description: str,
    dummy: bool,
    timeout_sec: float,
    mcp_url: Optional[str] = None,
) -> Tuple[str, list, Optional[str]]:
    payload = {
        "repo_root": str(REPO_ROOT),
        "agent_dir": str(AGENT_DIR),
        "module": module_name,
        "query": query,
        "db_config_path": db_config_path,
        "db_description": db_description,
        "dummy": dummy,
        "mcp_url": mcp_url,
    }
    child_env = os.environ.copy()
    if mcp_url:
        child_env["MCP_URL"] = mcp_url
    try:
        proc = subprocess.run(
            [sys.executable, str(CHILD_SCRIPT)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=timeout_sec,
            cwd=str(REPO_ROOT),
            env=child_env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "", [], "timeout"

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        return "", [], f"subprocess_error: {err}"

    line = (proc.stdout or "").strip()
    if not line:
        return "", [], "empty_child_stdout"

    try:
        msg = json.loads(line)
    except json.JSONDecodeError as e:
        return "", [], f"invalid_child_json: {e}: {line[:200]!r}"

    if not msg.get("ok"):
        return "", [], str(msg.get("error", "unknown_error"))
    return str(msg.get("answer", "")), msg.get("query_trace", []), None


def next_run_id(score_log_path: Path, day: str) -> str:
    runs = read_score_log(score_log_path)
    n = sum(1 for r in runs if isinstance(r, dict) and r.get("date") == day)
    return f"{day}-{n + 1:03d}"


def read_score_log(score_log_path: Path) -> List[Dict[str, Any]]:
    if not score_log_path.exists() or score_log_path.stat().st_size == 0:
        return []
    try:
        data = json.loads(score_log_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def append_score_log(score_log_path: Path, record: Dict[str, Any]) -> None:
    score_log_path.parent.mkdir(parents=True, exist_ok=True)
    runs = read_score_log(score_log_path)
    runs.append(record)
    tmp = score_log_path.with_suffix(score_log_path.suffix + ".tmp")
    tmp.write_text(json.dumps(runs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(score_log_path)


def print_summary_table(run: Dict[str, Any]) -> None:
    rows = run.get("results") or []
    print()
    print(f"run_id={run.get('run_id')} dataset={run.get('dataset')} pass@1={run.get('pass_at_1')}")
    print("-" * 100)
    print(f"{'query_id':<12}{'pass':<6}{'time_s':>10}  question")
    print("-" * 100)
    for r in rows:
        qid = str(r.get("query_id", ""))[:10]
        ok = "yes" if r.get("passed") else "no"
        t = r.get("execution_time_sec")
        ts = f"{t:.2f}" if isinstance(t, (int, float)) else str(t)
        qtext = str(r.get("question", "")).replace("\n", " ")[:70]
        print(f"{qid:<12}{ok:<6}{ts:>10}  {qtext}")
    print("-" * 100)
    print(f"passed={run.get('passed')} failed={run.get('failed')} total={run.get('total_queries')}")
    print()


def _resolve_dataset_root(dab_root: Path, dataset: str) -> tuple[str, Path]:
    """Resolve query_<dataset> directory case-insensitively.

    This allows callers to pass dataset keys with mixed case (e.g. DEPS_DEV_V1)
    while still locating the correct folder on disk (e.g. query_DEPS_DEV_V1).
    """
    requested = dataset.strip()
    direct = dab_root / f"query_{requested}"
    if direct.is_dir():
        return requested, direct

    requested_lower = requested.lower()
    for cand in dab_root.glob("query_*"):
        if not cand.is_dir():
            continue
        suffix = cand.name.replace("query_", "", 1)
        if suffix.lower() == requested_lower:
            return suffix, cand

    raise FileNotFoundError(
        f"Dataset directory not found for '{dataset}' under {dab_root}. "
        "Expected a query_<dataset> folder."
    )


# Known environment-failure signatures (not agent reasoning failures).
_ENV_ERROR_PATTERNS = (
    "permission denied for table",
    "permission denied for schema",
    "available: []",          # empty db registry — wiring/config not loaded
    "could not connect to server",
    "connection refused",
    "modulenotfounderror: common_scaffold",
    "no such file or directory",  # missing db file
)


def _classify_error(err: str | None) -> str:
    """Return 'timeout' | 'environment' | 'agent' | None for a harness error string."""
    if err is None:
        return None
    if err.startswith("agent_timeout"):
        return "timeout"
    lower = err.lower()
    if any(p in lower for p in _ENV_ERROR_PATTERNS):
        return "environment"
    return "agent"


def run_harness(
    *,
    dataset: str,
    dab_root: Path,
    agent_module: Optional[str],
    dummy: bool,
    timeout_sec: float,
    run_id: Optional[str],
    score_log_path: Path,
    skip_precheck: bool = False,
) -> Dict[str, Any]:
    dataset_key, dataset_root = _resolve_dataset_root(dab_root, dataset)

    db_config = dataset_root / "db_config.yaml"
    db_desc = dataset_root / "db_description.txt"
    if not db_config.is_file():
        raise FileNotFoundError(f"Missing db_config.yaml under {dataset_root}")
    if not db_desc.is_file():
        raise FileNotFoundError(f"Missing db_description.txt under {dataset_root}")

    db_description = db_desc.read_text(encoding="utf-8")
    db_config_path = str(db_config)

    if not dummy and not agent_module:
        raise ValueError("Provide --agent-module or use --dummy")

    # Fast-fail if the LLM API key is unusable — avoids burning time on all queries.
    # skip_precheck=True when running multiple datasets (pre-check done once by the caller).
    if not dummy and agent_module and not skip_precheck:
        api_err = _check_llm_api()
        if api_err:
            raise RuntimeError(f"LLM API pre-check failed: {api_err}")

    mod_name = agent_module or "dummy"

    # Use dataset-specific timeout when caller passed the global default.
    effective_timeout = timeout_sec
    if timeout_sec == QUERY_TIMEOUT_SEC and dataset_key.lower() in {k.lower() for k in DATASET_TIMEOUT_SEC}:
        matched = next(v for k, v in DATASET_TIMEOUT_SEC.items() if k.lower() == dataset_key.lower())
        effective_timeout = matched
        print(f"[harness] Using dataset timeout {effective_timeout}s for '{dataset_key}'.", flush=True)

    query_dirs = discover_query_dirs(dataset_root)
    if not query_dirs:
        raise FileNotFoundError(f"No queryN directories under {dataset_root}")

    today = datetime.now(timezone.utc).date().isoformat()
    rid = run_id or next_run_id(score_log_path, today)

    results: List[Dict[str, Any]] = []
    passed_n = 0

    mcp_proc: Optional[subprocess.Popen] = None
    mcp_rpc_url: Optional[str] = None
    if not dummy:
        mcp_proc, mcp_rpc_url = _start_mcp_server(db_config_path)
    try:
        for qdir in query_dirs:
            qid = qdir.name
            qjson = qdir / "query.json"
            vpy = qdir / "validate.py"
            t0 = datetime.now(timezone.utc)

            row: Dict[str, Any] = {
                "query_id": qid,
                "question": None,
                "agent_answer": None,
                "query_trace": [],
                "passed": False,
                "execution_time_sec": None,
                "validation_message": None,
                "error": None,
                "error_type": None,
            }

            if not qjson.is_file():
                row["error"] = "missing_query.json"
                row["execution_time_sec"] = 0.0
                results.append(row)
                continue
            if not vpy.is_file():
                row["error"] = "missing_validate.py"
                row["execution_time_sec"] = 0.0
                results.append(row)
                continue

            question = load_question(qjson)
            row["question"] = question

            answer, trace, err = invoke_agent_subprocess(
                module_name=mod_name,
                query=question,
                db_config_path=db_config_path,
                db_description=db_description,
                dummy=dummy,
                timeout_sec=effective_timeout,
                mcp_url=mcp_rpc_url,
            )
            t1 = datetime.now(timezone.utc)
            row["execution_time_sec"] = round((t1 - t0).total_seconds(), 3)

            if err == "timeout":
                row["agent_answer"] = ""
                row["query_trace"] = trace
                row["error"] = f"agent_timeout_after_{effective_timeout}s"
                row["error_type"] = "timeout"
                results.append(row)
                continue
            if err:
                row["agent_answer"] = answer or ""
                row["query_trace"] = trace
                row["error"] = err
                row["error_type"] = _classify_error(err)
                if row["error_type"] == "environment":
                    print(f"[harness] Environment error on {qid} (infrastructure, not agent): {err[:120]}", flush=True)
                results.append(row)
                continue

            row["agent_answer"] = answer
            row["query_trace"] = trace

            try:
                validate_fn = load_validate_fn(vpy, dab_root=dab_root)
                ok, reason = run_validate(validate_fn, answer)
                row["passed"] = ok
                row["validation_message"] = reason
                if ok:
                    passed_n += 1
            except Exception as e:  # noqa: BLE001
                row["error"] = repr(e)
                row["passed"] = False

            results.append(row)
    finally:
        _stop_mcp_server(mcp_proc)

    total = len(results)
    failed_n = total - passed_n
    pass_at_1 = round(passed_n / total, 4) if total else 0.0

    run_record: Dict[str, Any] = {
        "run_id": rid,
        "dataset": dataset_key,
        "date": today,
        "total_queries": total,
        "passed": passed_n,
        "failed": failed_n,
        "pass_at_1": pass_at_1,
        "agent_module": mod_name if not dummy else "dummy",
        "dab_root": str(dab_root.resolve()),
        "results": results,
        "methodology_notes": {
            "harness_script": "eval/harness.py",
            "validation": "Each query: agent subprocess → answer string → validate.py from DataAgentBench (no numeric repair layer).",
            "timeout_sec": effective_timeout,
            "environment_errors": sum(1 for r in results if r.get("error_type") == "environment"),
            "timeout_errors": sum(1 for r in results if r.get("error_type") == "timeout"),
            "agent_errors": sum(1 for r in results if r.get("error_type") == "agent"),
            "strict_no_leakage": os.getenv("ORACLE_FORGE_STRICT_NO_LEAKAGE", ""),
            "oracle_forge_llm_provider": os.getenv("ORACLE_FORGE_LLM_PROVIDER", ""),
            "openai_model": os.getenv("OPENAI_MODEL", ""),
            "openrouter_model": os.getenv("OPENROUTER_MODEL", ""),
            "mcp_url_passed_to_child": bool(mcp_rpc_url),
        },
    }

    append_score_log(score_log_path, run_record)
    return run_record


def main() -> int:
    parser = argparse.ArgumentParser(description="DataAgentBench evaluation harness")
    parser.add_argument("--dataset", required=True, help='Dataset key, e.g. "yelp" -> query_yelp/')
    parser.add_argument(
        "--dab-root",
        default=None,
        help=f"Path to DataAgentBench checkout (default: env DATAAGENTBENCH_ROOT or {DEFAULT_DAB})",
    )
    parser.add_argument("--agent-module", default=None, help="Module exposing run_agent(query, db_config_path, db_description) -> str")
    parser.add_argument("--dummy", action="store_true", help='Use stub agent returning "No answer"')
    parser.add_argument("--timeout", type=float, default=QUERY_TIMEOUT_SEC, help="Per-query agent timeout in seconds")
    parser.add_argument("--run-id", default=None, help="Override auto-generated run id (e.g. 2026-04-10-001)")
    parser.add_argument("--score-log", type=Path, default=SCORE_LOG, help="Append-only JSON score log path")
    parser.add_argument("--skip-precheck", action="store_true", help="Skip LLM API pre-check (use when running multiple datasets to avoid consuming rate-limit quota on health probes)")
    args = parser.parse_args()

    dab = Path(args.dab_root or __import__("os").environ.get("DATAAGENTBENCH_ROOT", DEFAULT_DAB))

    if args.dummy and args.agent_module:
        print("Use either --dummy or --agent-module, not both.", file=sys.stderr)
        return 2

    _ensure_import_paths()

    try:
        run = run_harness(
            dataset=args.dataset,
            dab_root=dab,
            agent_module=args.agent_module,
            dummy=args.dummy,
            timeout_sec=args.timeout,
            run_id=args.run_id,
            score_log_path=args.score_log,
            skip_precheck=args.skip_precheck,
        )
    except Exception as e:  # noqa: BLE001
        print(f"Harness error: {e}", file=sys.stderr)
        return 1

    print(json.dumps(run, indent=2, ensure_ascii=False))
    print_summary_table(run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
