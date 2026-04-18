"""Subprocess entrypoint for eval/harness.py — isolates agent + enforces parent-side timeout."""
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path


def main() -> int:
    payload = json.loads(sys.stdin.read())
    mcp_url = payload.get("mcp_url")
    if mcp_url:
        os.environ["MCP_URL"] = str(mcp_url)
    repo_root = Path(payload["repo_root"])
    agent_dir = Path(payload["agent_dir"])
    for p in (str(repo_root), str(agent_dir)):
        if p not in sys.path:
            sys.path.insert(0, p)

    try:
        if payload.get("dummy"):
            out = {"ok": True, "answer": "No answer"}
        else:
            mod = importlib.import_module(payload["module"])
            fn = getattr(mod, "run_agent")
            ans = fn(
                payload["query"],
                payload["db_config_path"],
                payload["db_description"],
            )
            if isinstance(ans, dict):
                out = {"ok": True, "answer": str(ans.get("answer", "")), "query_trace": ans.get("query_trace", [])}
            else:
                out = {"ok": True, "answer": str(ans), "query_trace": []}
    except Exception as e:  # noqa: BLE001 — child must always emit JSON
        out = {"ok": False, "error": repr(e)}

    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
