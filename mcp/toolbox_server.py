"""
mcp/toolbox_server.py — Oracle Forge MCP JSON-RPC Tool Server

Implements the Model Context Protocol (JSON-RPC 2.0 over HTTP) and exposes
four database tool types: MongoDB, DuckDB, PostgreSQL (stub), SQLite (stub).

The Google MCP Toolbox binary (genai-toolbox) does not support DuckDB natively
and crashes silently when given a config on this server. This Python server is
a drop-in replacement that supports all four DAB database types.

Usage:
    conda run -n dabench python mcp/toolbox_server.py
    # Listens on http://localhost:5000/mcp (MCP JSON-RPC endpoint)

Protocol:
    POST /mcp  — MCP JSON-RPC 2.0
    GET  /     — health check (returns "🧰 Oracle Forge MCP Server 🧰")
"""

from __future__ import annotations

import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pymongo
import duckdb
import yaml
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_YAML = Path(__file__).resolve().parent / "tools.yaml"
DAB_ROOT = Path(os.getenv("DATAAGENTBENCH_ROOT", str(REPO_ROOT / "DataAgentBench")))
MAX_ROWS = 500

# ── Tool schemas (for tools/list response) ────────────────────────────────────

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "query_mongodb",
        "description": (
            "Query a MongoDB collection. "
            "Use query_type='find' for simple filters, 'aggregate' for pipelines."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "db_name":     {"type": "string", "description": "Logical DB name from db_config.yaml"},
                "collection":  {"type": "string", "description": "Collection name (e.g. 'business')"},
                "query_type":  {"type": "string", "enum": ["find", "aggregate"]},
                "query":       {"type": "string", "description": "JSON filter dict or pipeline array"},
                "projection":  {"type": "string", "description": "Optional JSON projection (find only)"},
            },
            "required": ["db_name", "collection", "query_type", "query"],
        },
    },
    {
        "name": "query_duckdb",
        "description": "Run a SQL query against a DuckDB database file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "db_name": {"type": "string", "description": "Logical DB name from db_config.yaml"},
                "sql":     {"type": "string", "description": "SQL query to execute"},
            },
            "required": ["db_name", "sql"],
        },
    },
    {
        "name": "query_postgres",
        "description": "Run a SQL query against a PostgreSQL database. (PENDING — no DAB datasets loaded yet)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "db_name": {"type": "string"},
                "sql":     {"type": "string"},
            },
            "required": ["db_name", "sql"],
        },
    },
    {
        "name": "query_sqlite",
        "description": "Run a SQL query against a SQLite database. (PENDING — no DAB datasets loaded yet)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "db_name": {"type": "string"},
                "sql":     {"type": "string"},
            },
            "required": ["db_name", "sql"],
        },
    },
]

# ── Connection registry — populated from db_config.yaml files ─────────────────

_mongo_connections: dict[str, dict] = {}   # logical_name → {db_name, uri}
_duckdb_connections: dict[str, str] = {}   # logical_name → abs_path


def register_dataset(db_config_path: str) -> None:
    """Load a db_config.yaml and register its connections globally."""
    cfg_path = Path(db_config_path).resolve()
    cfg = yaml.safe_load(cfg_path.read_text())
    base = cfg_path.parent
    for name, details in cfg.get("db_clients", {}).items():
        db_type = details.get("db_type", "")
        if db_type == "mongo":
            _mongo_connections[name] = {
                "db_name": details["db_name"],
                "uri": os.getenv("MONGO_URI", "mongodb://localhost:27017/"),
            }
        elif db_type == "duckdb":
            _duckdb_connections[name] = str(base / details["db_path"])
    logger.info("Registered dataset from %s: mongo=%s duckdb=%s",
                cfg_path, list(_mongo_connections), list(_duckdb_connections))


def _auto_register() -> None:
    """Auto-register all db_config.yaml files found under DAB_ROOT."""
    for p in DAB_ROOT.rglob("db_config.yaml"):
        try:
            register_dataset(str(p))
        except Exception as exc:
            logger.warning("Could not register %s: %s", p, exc)


# ── JSON serialisation ────────────────────────────────────────────────────────

def _serializable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serializable(i) for i in obj]
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


# ── Tool executors ────────────────────────────────────────────────────────────

def _exec_mongodb(args: dict) -> dict:
    logical = args["db_name"]
    if logical not in _mongo_connections:
        return {"success": False, "error": f"Unknown MongoDB db_name '{logical}'. Available: {list(_mongo_connections)}"}
    cfg = _mongo_connections[logical]
    try:
        client = pymongo.MongoClient(cfg["uri"], serverSelectionTimeoutMS=5000)
        coll = client[cfg["db_name"]][args["collection"]]
        q = json.loads(args["query"])
        if args["query_type"] == "find":
            proj = json.loads(args["projection"]) if args.get("projection") else None
            cursor = coll.find(q, proj) if proj else coll.find(q)
            rows = [_serializable(doc) for doc in cursor.limit(MAX_ROWS)]
        else:
            pipeline = q if isinstance(q, list) else [q]
            rows = [_serializable(doc) for doc in coll.aggregate(pipeline)]
        client.close()
        return {"success": True, "rows": len(rows), "data": rows}
    except Exception as exc:
        return {"success": False, "error": str(exc), "rows": 0, "data": []}


def _exec_duckdb(args: dict) -> dict:
    logical = args["db_name"]
    if logical not in _duckdb_connections:
        return {"success": False, "error": f"Unknown DuckDB db_name '{logical}'. Available: {list(_duckdb_connections)}"}
    try:
        conn = duckdb.connect(_duckdb_connections[logical], read_only=True)
        df = conn.execute(args["sql"]).fetchdf()
        conn.close()
        records = _serializable(df.to_dict(orient="records"))
        return {"success": True, "rows": len(records), "data": records[:MAX_ROWS]}
    except Exception as exc:
        return {"success": False, "error": str(exc), "rows": 0, "data": []}


def _exec_stub(db_type: str, args: dict) -> dict:
    return {"success": False, "error": f"{db_type} not yet configured (PENDING — no DAB datasets loaded)"}


# ── MCP dispatcher ────────────────────────────────────────────────────────────

def dispatch(tool_name: str, arguments: dict) -> Any:
    if tool_name == "query_mongodb":
        return _exec_mongodb(arguments)
    elif tool_name == "query_duckdb":
        return _exec_duckdb(arguments)
    elif tool_name == "query_postgres":
        return _exec_stub("PostgreSQL", arguments)
    elif tool_name == "query_sqlite":
        return _exec_stub("SQLite", arguments)
    return {"success": False, "error": f"Unknown tool: {tool_name}"}


# ── HTTP / MCP JSON-RPC handler ───────────────────────────────────────────────

class MCPHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # suppress default access log
        logger.debug(fmt, *args)

    def _send_json(self, obj: Any, status: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/health"):
            body = b"\xf0\x9f\xa7\xb0 Oracle Forge MCP Server \xf0\x9f\xa7\xb0"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/mcp":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            req = json.loads(body)
        except json.JSONDecodeError as e:
            self._send_json({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(e)}})
            return

        rpc_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        if method == "initialize":
            self._send_json({
                "jsonrpc": "2.0", "id": rpc_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "oracle-forge-mcp", "version": "1.0.0"},
                },
            })

        elif method == "tools/list":
            self._send_json({
                "jsonrpc": "2.0", "id": rpc_id,
                "result": {"tools": TOOL_SCHEMAS},
            })

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            logger.info("tools/call %s args=%s", tool_name, str(arguments)[:200])
            result = dispatch(tool_name, arguments)
            self._send_json({
                "jsonrpc": "2.0", "id": rpc_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                    "isError": not result.get("success", True),
                },
            })

        else:
            self._send_json({
                "jsonrpc": "2.0", "id": rpc_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            })


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    port = int(os.getenv("MCP_PORT", "5000"))
    _auto_register()
    server = HTTPServer(("127.0.0.1", port), MCPHandler)
    logger.info("Oracle Forge MCP server listening on http://127.0.0.1:%d/mcp", port)
    logger.info("Mongo connections: %s", list(_mongo_connections))
    logger.info("DuckDB connections: %s", list(_duckdb_connections))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down.")


if __name__ == "__main__":
    main()
