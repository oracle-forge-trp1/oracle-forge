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

Env:
    ORACLE_FORGE_REGISTER_ONLY_DB_CONFIG — optional absolute path to one db_config.yaml.
    When set, only that dataset is registered (avoids logical-name collisions across
    many query_* folders). The eval harness sets this automatically.

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

import sqlite3
import pymongo
import duckdb
import psycopg2
import psycopg2.extras
import yaml
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_YAML = Path(__file__).resolve().parent / "tools.yaml"
DAB_ROOT = Path(os.getenv("DATAAGENTBENCH_ROOT", str(REPO_ROOT / "DataAgentBench")))
MAX_ROWS = 500

# ── Utils import (JoinKeyResolver) ───────────────────────────────────────────
# Repo root is added to sys.path so `utils` is importable regardless of cwd.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from utils.join_key_resolver import JoinKeyResolver  # noqa: E402

_join_resolver = JoinKeyResolver()

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
        "description": "Run a SQL query against a PostgreSQL database.",
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
        "name": "query_sqlite",
        "description": "Run a SQL query against a SQLite database.",
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
        "name": "normalize_join_key",
        "description": (
            "Normalize a cross-database join key to its canonical integer form, "
            "then optionally re-prefix it for the target database. "
            "Handles all DAB prefix mismatches: businessid_N→N, businessref_N→N, "
            "CRM #-prefix corruption, zero-padded integers, trailing whitespace. "
            "Use this whenever a cross-database join returns 0 rows."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "value":         {"type": "string", "description": "Raw key value to normalize (e.g. 'businessid_42')"},
                "target_prefix": {"type": "string", "description": "Optional prefix for target DB (e.g. 'businessref_'). If omitted, returns the integer N."},
            },
            "required": ["value"],
        },
    },
    {
        "name": "diagnose_join",
        "description": (
            "Diagnose why a cross-database join returned 0 results. "
            "Pass sample key values (JSON arrays) from both sides. "
            "Returns detected formats, mismatch type, and a suggested fix."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "left_values":  {"type": "string", "description": "JSON array of sample key values from the left database (e.g. '[\"businessid_1\",\"businessid_2\"]')"},
                "right_values": {"type": "string", "description": "JSON array of sample key values from the right database (e.g. '[\"businessref_1\",\"businessref_2\"]')"},
            },
            "required": ["left_values", "right_values"],
        },
    },
]

# ── Connection registry — populated from db_config.yaml files ─────────────────

_mongo_connections:    dict[str, dict] = {}   # logical_name → {db_name, uri}
_duckdb_connections:   dict[str, str]  = {}   # logical_name → abs_path
_sqlite_connections:   dict[str, str]  = {}   # logical_name → abs_path
_postgres_connections: dict[str, dict] = {}   # logical_name → {db_name, host, port, user, password}


def _clear_connection_registry() -> None:
    """Reset all logical DB registrations (used before single-dataset registration)."""
    _mongo_connections.clear()
    _duckdb_connections.clear()
    _sqlite_connections.clear()
    _postgres_connections.clear()


def register_dataset(db_config_path: str) -> None:
    """Load a db_config.yaml and register its connections globally.
    Entries whose db_path / dump_folder / sql_file does not exist on disk are skipped
    (same behaviour as the DAB scaffold db_config.py fix).
    """
    cfg_path = Path(db_config_path).resolve()
    cfg = yaml.safe_load(cfg_path.read_text())
    base = cfg_path.parent
    for name, details in cfg.get("db_clients", {}).items():
        db_type = details.get("db_type", "")

        # Validate that referenced files/folders actually exist before registering
        for file_key in ("db_path", "dump_folder", "sql_file"):
            if file_key in details:
                resolved = base / details[file_key]
                if not resolved.exists():
                    logger.warning(
                        "[%s] %s does not exist: %s — skipping this client.",
                        name, file_key, resolved
                    )
                    break  # skip this db_client entirely
        else:
            # All referenced paths exist (or no file references) — register normally
            if db_type == "mongo":
                _mongo_connections[name] = {
                    "db_name": details["db_name"],
                    "uri": os.getenv("MONGO_URI", "mongodb://localhost:27017/"),
                }
            elif db_type == "duckdb":
                _duckdb_connections[name] = str(base / details["db_path"])
            elif db_type == "sqlite":
                _sqlite_connections[name] = str(base / details["db_path"])
            elif db_type in ("postgres", "postgresql"):
                _postgres_connections[name] = {
                    "db_name":  details["db_name"],
                    "host":     os.getenv("PG_HOST",     "localhost"),
                    "port":     int(os.getenv("PG_PORT", "5432")),
                    "user":     os.getenv("PG_USER",     "oracle_forge"),
                    "password": os.getenv("PG_PASSWORD", "oracle_forge_pw"),
                }
    logger.info(
        "Registered dataset from %s: mongo=%s duckdb=%s sqlite=%s postgres=%s",
        cfg_path, list(_mongo_connections), list(_duckdb_connections),
        list(_sqlite_connections), list(_postgres_connections),
    )


def _auto_register() -> None:
    """Populate connection registries from db_config.yaml files.

    If ORACLE_FORGE_REGISTER_ONLY_DB_CONFIG is set to an absolute or repo-relative
    path, only that file is loaded. This avoids logical-name collisions when many
    datasets reuse the same keys (e.g. metadata_database) — otherwise the last
    file wins and queries hit the wrong SQLite/DuckDB files.

    When unset, every db_config.yaml under DATAAGENTBENCH_ROOT is registered
    (dev convenience; duplicate keys still overwrite).
    """
    only = os.getenv("ORACLE_FORGE_REGISTER_ONLY_DB_CONFIG", "").strip()
    if only:
        cfg = Path(only)
        if not cfg.is_absolute():
            cfg = (REPO_ROOT / cfg).resolve()
        else:
            cfg = cfg.resolve()
        if not cfg.is_file():
            logger.error(
                "ORACLE_FORGE_REGISTER_ONLY_DB_CONFIG is not a file: %s — no DBs registered.",
                cfg,
            )
            return
        _clear_connection_registry()
        try:
            register_dataset(str(cfg))
        except Exception as exc:
            logger.error("Could not register %s: %s", cfg, exc)
        return

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


def _exec_sqlite(args: dict) -> dict:
    logical = args["db_name"]
    if logical not in _sqlite_connections:
        return {"success": False, "error": f"Unknown SQLite db_name '{logical}'. Available: {list(_sqlite_connections)}"}
    try:
        conn = sqlite3.connect(_sqlite_connections[logical])
        conn.row_factory = sqlite3.Row
        cur = conn.execute(args["sql"])
        rows = [dict(r) for r in cur.fetchmany(MAX_ROWS)]
        conn.close()
        return {"success": True, "rows": len(rows), "data": rows}
    except Exception as exc:
        # Include an explicit error payload so the agent can self-correct.
        return {"success": False, "error": str(exc), "rows": 0, "data": []}


def _exec_postgres(args: dict) -> dict:
    logical = args["db_name"]
    if logical not in _postgres_connections:
        return {"success": False, "error": f"Unknown PostgreSQL db_name '{logical}'. Available: {list(_postgres_connections)}"}
    cfg = _postgres_connections[logical]
    try:
        conn = psycopg2.connect(
            host=cfg["host"], port=cfg["port"],
            user=cfg["user"], password=cfg["password"],
            dbname=cfg["db_name"],
        )
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(args["sql"])
        rows = [dict(r) for r in cur.fetchmany(MAX_ROWS)]
        conn.close()
        return {"success": True, "rows": len(rows), "data": rows}
    except Exception as exc:
        # Return explicit error payload (without a fake empty data array) so
        # upstream traces and the LLM can see the true failure reason.
        return {"success": False, "error": str(exc), "rows": 0, "data": []}


def _exec_normalize_join_key(args: dict) -> dict:
    """Normalize a single join key using JoinKeyResolver."""
    raw = args.get("value")
    if raw is None:
        return {"success": False, "error": "Missing required parameter: value"}
    target_prefix = args.get("target_prefix")
    try:
        normalized_int = _join_resolver.normalize(raw, target_type="integer")
        if target_prefix is not None:
            result = f"{target_prefix}{normalized_int}"
        else:
            result = normalized_int
        detected = _join_resolver.detect_format([raw])
        return {
            "success": True,
            "original": raw,
            "normalized_int": normalized_int,
            "result": result,
            "detected_format": detected,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _exec_diagnose_join(args: dict) -> dict:
    """Diagnose join key mismatches between two sets of sample values."""
    try:
        left_vals  = json.loads(args["left_values"])
        right_vals = json.loads(args["right_values"])
    except (KeyError, json.JSONDecodeError) as exc:
        return {"success": False, "error": f"Invalid JSON input: {exc}"}
    try:
        left_format  = _join_resolver.detect_format(left_vals)
        right_format = _join_resolver.detect_format(right_vals)
        left_norm  = _join_resolver.normalize_batch(left_vals)
        right_norm = _join_resolver.normalize_batch(right_vals)
        overlap = set(left_norm) & set(right_norm)
        return {
            "success": True,
            "left_format":  left_format,
            "right_format": right_format,
            "left_samples_normalized":  left_norm[:5],
            "right_samples_normalized": right_norm[:5],
            "normalized_overlap_count": len(overlap),
            "suggestion": (
                "Normalize both sides to integer before joining. "
                f"Left prefix: '{left_format.get('prefix')}', "
                f"Right prefix: '{right_format.get('prefix')}'."
            ) if left_format.get("prefix") != right_format.get("prefix") else
            "Key formats appear compatible after normalization.",
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ── MCP dispatcher ────────────────────────────────────────────────────────────

def dispatch(tool_name: str, arguments: dict) -> Any:
    if tool_name == "query_mongodb":
        return _exec_mongodb(arguments)
    elif tool_name == "query_duckdb":
        return _exec_duckdb(arguments)
    elif tool_name == "query_sqlite":
        return _exec_sqlite(arguments)
    elif tool_name == "query_postgres":
        return _exec_postgres(arguments)
    elif tool_name == "normalize_join_key":
        return _exec_normalize_join_key(arguments)
    elif tool_name == "diagnose_join":
        return _exec_diagnose_join(arguments)
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
    logger.info("Mongo    connections: %s", list(_mongo_connections))
    logger.info("DuckDB   connections: %s", list(_duckdb_connections))
    logger.info("SQLite   connections: %s", list(_sqlite_connections))
    logger.info("Postgres connections: %s", list(_postgres_connections))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down.")


if __name__ == "__main__":
    main()
