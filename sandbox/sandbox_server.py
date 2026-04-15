#!/usr/bin/env python3
"""
sandbox/sandbox_server.py — Oracle Forge Code Execution Sandbox

Wraps MCP tool calls in a safe HTTP execution layer:
  - Enforces per-query timeouts (default 60 s) in an isolated daemon thread
  - Returns structured trace JSON for every execution
  - Persists trace log to sandbox/trace_log.jsonl (append-only JSONL)
  - Keeps a ring buffer of the last 100 traces in memory for GET /traces

Usage:
    python3 sandbox/sandbox_server.py [--port 8080] [--timeout 60] [--mcp-url URL]

Endpoints:
    POST /execute  — execute one tool call, returns trace JSON
    GET  /health   — {"status": "ok", "mcp_url": "..."}
    GET  /traces   — last 50 traces from the in-memory ring buffer
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

REPO_ROOT  = Path(__file__).resolve().parent.parent
TRACE_LOG  = Path(__file__).resolve().parent / "trace_log.jsonl"

# Overridden by CLI arg --mcp-url
_mcp_url: str = os.getenv("MCP_URL", "http://127.0.0.1:5000/mcp")

DEFAULT_TIMEOUT_SEC  = 60
MAX_MEMORY_TRACES    = 100

_traces: list[dict]     = []
_traces_lock            = threading.Lock()


# ── MCP call ──────────────────────────────────────────────────────────────────

def _call_mcp(tool_name: str, arguments: dict, timeout_sec: float) -> dict:
    """
    Send a tools/call request to the MCP server and unpack the response envelope.
    Returns the inner result dict {success, rows, data, ...} or raises on failure.
    """
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }).encode()

    req = urllib.request.Request(
        _mcp_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        rpc_response = json.loads(resp.read())

    # Unpack: result → content[0] → text → inner dict
    rpc_result   = rpc_response.get("result", {})
    content_list = rpc_result.get("content", [{}])
    text         = (content_list[0].get("text", "{}") if content_list else "{}")
    return json.loads(text)


def _execute_with_timeout(
    tool_name: str, arguments: dict, timeout_sec: float
) -> dict:
    """
    Run _call_mcp in a daemon thread.  If the thread does not finish within
    timeout_sec, return a structured timeout error (the thread will eventually
    terminate on its own when the urllib socket times out).
    """
    result_box: list[Optional[dict]]      = [None]
    exc_box:    list[Optional[Exception]] = [None]

    def _worker():
        try:
            result_box[0] = _call_mcp(tool_name, arguments, timeout_sec)
        except Exception as exc:  # noqa: BLE001
            exc_box[0] = exc

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout=timeout_sec)

    if thread.is_alive():
        return {
            "success": False,
            "error":   f"timeout after {timeout_sec:.0f}s",
            "rows":    0,
            "data":    [],
        }
    if exc_box[0] is not None:
        return {
            "success": False,
            "error":   str(exc_box[0]),
            "rows":    0,
            "data":    [],
        }
    result = result_box[0]
    if result is None:
        return {"success": False, "error": "empty result from MCP", "rows": 0, "data": []}
    return result


# ── Trace persistence ─────────────────────────────────────────────────────────

def _append_trace(entry: dict) -> None:
    """Append a trace entry to JSONL log and the in-memory ring buffer."""
    try:
        TRACE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(TRACE_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning("Could not write trace log: %s", exc)

    with _traces_lock:
        _traces.append(entry)
        if len(_traces) > MAX_MEMORY_TRACES:
            _traces.pop(0)


# ── HTTP request handler ──────────────────────────────────────────────────────

class SandboxHandler(BaseHTTPRequestHandler):
    # Set by main() before the server starts
    server_default_timeout: float = DEFAULT_TIMEOUT_SEC

    def log_message(self, fmt, *args):  # suppress default request log; use logger instead
        logger.debug(fmt, *args)

    def _send_json(self, obj: Any, status: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    # ── GET ───────────────────────────────────────────────────────────────────

    def do_GET(self):
        if self.path in ("/", "/health"):
            self._send_json({
                "status":  "ok",
                "service": "oracle-forge-sandbox",
                "mcp_url": _mcp_url,
                "default_timeout_sec": self.server_default_timeout,
                "trace_log": str(TRACE_LOG),
            })

        elif self.path.startswith("/traces"):
            with _traces_lock:
                snapshot = list(_traces)
            self._send_json({
                "total":  len(snapshot),
                "traces": snapshot[-50:],
            })

        else:
            self._send_json({"error": "not found"}, status=404)

    # ── POST /execute ─────────────────────────────────────────────────────────

    def do_POST(self):
        if self.path != "/execute":
            self._send_json({"error": "not found"}, status=404)
            return

        body = self._read_body()
        try:
            req = json.loads(body)
        except json.JSONDecodeError as exc:
            self._send_json({"ok": False, "error": f"invalid JSON: {exc}"}, status=400)
            return

        tool_name = req.get("tool")
        arguments = req.get("arguments", {})
        timeout   = float(req.get("timeout", self.server_default_timeout))

        # Input validation
        if not tool_name or not isinstance(tool_name, str):
            self._send_json(
                {"ok": False, "error": "missing or invalid 'tool' field"}, status=400
            )
            return
        if not isinstance(arguments, dict):
            self._send_json(
                {"ok": False, "error": "'arguments' must be a JSON object"}, status=400
            )
            return

        trace_id   = str(uuid.uuid4())[:8]
        started_at = datetime.now(timezone.utc).isoformat()
        t0         = time.monotonic()

        logger.info("[%s] %-22s  args=%s", trace_id, tool_name, str(arguments)[:200])

        result    = _execute_with_timeout(tool_name, arguments, timeout_sec=timeout)
        elapsed_ms = round((time.monotonic() - t0) * 1000, 1)

        timed_out = "timeout" in (result.get("error") or "")
        succeeded = bool(result.get("success"))

        trace_entry = {
            "trace_id":          trace_id,
            "tool":              tool_name,
            "arguments":         arguments,
            "success":           succeeded,
            "rows":              result.get("rows", 0),
            "error":             result.get("error"),
            "data_preview":      str(result.get("data", ""))[:400] if result.get("data") else None,
            "execution_time_ms": elapsed_ms,
            "timed_out":         timed_out,
            "started_at":        started_at,
        }
        _append_trace(trace_entry)

        logger.info(
            "[%s] %-22s  success=%-5s rows=%-5s time=%.0fms",
            trace_id, tool_name, succeeded, result.get("rows", 0), elapsed_ms,
        )

        # HTTP status: 200 OK, 422 query error, 504 timeout, 502 MCP unreachable
        if timed_out:
            http_status = 504
        elif not succeeded:
            err = result.get("error", "")
            http_status = 502 if "Connection refused" in err or "timed out" in err else 422
        else:
            http_status = 200

        self._send_json(
            {
                "ok":                succeeded,
                "trace_id":          trace_id,
                "tool":              tool_name,
                "success":           succeeded,
                "rows":              result.get("rows", 0),
                "data":              result.get("data"),
                "error":             result.get("error"),
                "execution_time_ms": elapsed_ms,
                "timed_out":         timed_out,
            },
            status=http_status,
        )


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    global _mcp_url

    parser = argparse.ArgumentParser(description="Oracle Forge Code Execution Sandbox")
    parser.add_argument(
        "--port",    type=int,   default=8080,
        help="HTTP port to listen on (default: 8080)",
    )
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT_SEC,
        help="Per-execution timeout in seconds (default: 60)",
    )
    parser.add_argument(
        "--mcp-url", default=_mcp_url,
        help=f"MCP server base URL (default: {_mcp_url})",
    )
    args = parser.parse_args()

    _mcp_url = args.mcp_url
    SandboxHandler.server_default_timeout = args.timeout

    logger.info("Oracle Forge Sandbox — http://0.0.0.0:%d/execute", args.port)
    logger.info("MCP server   : %s",  _mcp_url)
    logger.info("Timeout      : %.0f s",  args.timeout)
    logger.info("Trace log    : %s",  TRACE_LOG)

    server = HTTPServer(("0.0.0.0", args.port), SandboxHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down.")


if __name__ == "__main__":
    main()
