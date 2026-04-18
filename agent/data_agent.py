"""
agent/data_agent.py — Oracle Forge Data Analytics Agent

ReAct-style agent: Think → Act (query DB) → Observe → Think → Answer
Uses Claude via OpenRouter. Database access prefers the Oracle Forge MCP server
(mcp/toolbox_server.py) and falls back to direct Python drivers when the MCP
server is unreachable or a call fails at the transport layer.
Loads AGENT.md as system context at startup.
"""

import os
import sys
import json
import logging
import sqlite3
import yaml
from pathlib import Path
from typing import Any

import pymongo
import duckdb
import requests
import psycopg2
import psycopg2.extras
from openai import OpenAI
from dotenv import load_dotenv

# ── Utils import (SchemaIntrospector) ────────────────────────────────────────
# Repo root is added to sys.path so `utils` is importable regardless of cwd.
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from utils.schema_introspector import SchemaIntrospector
    _SCHEMA_INTROSPECTOR = SchemaIntrospector()
except ImportError:
    _SCHEMA_INTROSPECTOR = None  # type: ignore[assignment]

try:
    from utils.join_key_resolver import JoinKeyResolver
    _JOIN_RESOLVER = JoinKeyResolver()
except ImportError:
    _JOIN_RESOLVER = None  # type: ignore[assignment]

# ── Constants ────────────────────────────────────────────────────────────────

AGENT_MD_PATH   = Path(__file__).parent / "AGENT.md"
KB_ROOT         = Path(__file__).parent.parent / "kb"
CORRECTIONS_LOG  = KB_ROOT / "corrections" / "corrections-log.md"
CRITICAL_RULES_LOG = KB_ROOT / "corrections" / "critical_rules.md"
DEFAULT_MODEL   = "anthropic/claude-haiku-4.5"
MAX_ITERATIONS  = int(os.getenv("ORACLE_FORGE_MAX_ITERATIONS", "28"))
MAX_RESULT_ROWS = 500   # cap rows returned to LLM to avoid context overflow
_TOOL_PREVIEW_ROWS = int(os.getenv("ORACLE_FORGE_TOOL_PREVIEW_ROWS", "120"))
MCP_URL         = os.getenv("MCP_URL", "http://127.0.0.1:5000/mcp")

logger = logging.getLogger(__name__)

# ── LLM client init ──────────────────────────────────────────────────────────

def _init_llm_client() -> tuple["OpenAI", str]:
    """Initialize LLM client and model from environment variables."""
    load_dotenv(override=False)
    llm_provider = os.getenv("ORACLE_FORGE_LLM_PROVIDER", "").strip().lower()

    if llm_provider in ("openai", "open_ai"):
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
        _model = os.getenv("OPENAI_MODEL", "gpt-4.1")
        logger.info("LLM provider: openai, model: %s", _model)
    elif llm_provider in ("google", "google_ai_studio", "gemini"):
        _client = OpenAI(
            api_key=os.getenv("GOOGLE_API_KEY", os.getenv("GEMINI_API_KEY", "")),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        _model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        logger.info("LLM provider: google_ai_studio, model: %s", _model)
    else:
        # OpenRouter (default)
        _client = OpenAI(
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            base_url="https://openrouter.ai/api/v1",
        )
        _model = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
        logger.info("LLM provider: openrouter, model: %s", _model)

    return _client, _model


client, model = _init_llm_client()

# Prompt-size guardrails: prevent context_length_exceeded across large datasets.
_MAX_SYSTEM_PROMPT_CHARS = int(os.getenv("ORACLE_FORGE_MAX_SYSTEM_PROMPT_CHARS", "60000"))
_MAX_SCHEMA_SECTION_CHARS = int(os.getenv("ORACLE_FORGE_MAX_SCHEMA_SECTION_CHARS", "12000"))
_MAX_DB_DESC_CHARS = int(os.getenv("ORACLE_FORGE_MAX_DB_DESCRIPTION_CHARS", "12000"))

_DISABLE_FORCE_COMPACT = os.getenv("ORACLE_FORGE_DISABLE_FORCE_COMPACT", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# ── MCP client ───────────────────────────────────────────────────────────────

_mcp_available: bool | None = None   # None = not yet probed

def _probe_mcp() -> bool:
    """Return True if the MCP server responds to a tools/list call."""
    global _mcp_available
    if _mcp_available is not None:
        return _mcp_available
    try:
        r = requests.post(
            MCP_URL,
            json={"jsonrpc": "2.0", "id": 0, "method": "tools/list", "params": {}},
            timeout=2,
        )
        _mcp_available = r.status_code == 200
    except Exception:
        _mcp_available = False
    logger.info("MCP server at %s: %s", MCP_URL, "available" if _mcp_available else "not available (using direct drivers)")
    return _mcp_available


def _call_mcp(tool_name: str, arguments: dict) -> dict:
    """
    Call a tool on the MCP server. Returns the same dict shape as the
    direct driver executors: {success, rows, data} or {success, error}.
    """
    try:
        r = requests.post(
            MCP_URL,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": tool_name, "arguments": arguments}},
            timeout=120,
        )
        r.raise_for_status()
        rpc_result = r.json().get("result", {})
        content_text = rpc_result.get("content", [{}])[0].get("text", "{}")
        return json.loads(content_text)
    except Exception as exc:
        logger.warning("MCP call failed, falling back to direct driver: %s", exc)
        return None   # caller checks for None and falls back

# ── Tool definitions (exposed to the LLM) ────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_mongodb",
            "description": (
                "Query a MongoDB collection. "
                "Use query_type='find' for small probes only. "
                "For global max/min/top-1, counts over the full collection, or any ranking, "
                "use query_type='aggregate' with $match / $group / $sort / $limit — never rely on "
                "find() plus a row cap to guess extrema."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "db_name": {
                        "type": "string",
                        "description": "Logical database name from the DATABASE DESCRIPTION (e.g. 'businessinfo_database')"
                    },
                    "collection": {
                        "type": "string",
                        "description": "Collection name (e.g. 'business', 'checkin')"
                    },
                    "query_type": {
                        "type": "string",
                        "enum": ["find", "aggregate"],
                        "description": "'find' for filter+projection, 'aggregate' for pipeline array"
                    },
                    "query": {
                        "type": "string",
                        "description": "JSON string: filter dict for 'find', pipeline array for 'aggregate'"
                    },
                    "projection": {
                        "type": "string",
                        "description": "Optional JSON projection dict for 'find' queries (e.g. '{\"business_id\": 1, \"_id\": 0}')"
                    }
                },
                "required": ["db_name", "collection", "query_type", "query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_duckdb",
            "description": (
                "Run a SQL query against a DuckDB database. "
                "Supports analytical SQL including TRY_STRPTIME, window functions, CTEs. "
                "Table and column names are case-sensitive: copy identifiers exactly from the schema "
                "or quote mixed-case names (e.g. \"PackageInfo\"). "
                "Quote reserved-word column names (e.g. \"FILTER\") when they are actual columns."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "db_name": {
                        "type": "string",
                        "description": "Logical database name from the DATABASE DESCRIPTION (e.g. 'user_database')"
                    },
                    "sql": {
                        "type": "string",
                        "description": "SQL query to execute"
                    }
                },
                "required": ["db_name", "sql"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_sqlite",
            "description": (
                "Run a SQL query against a SQLite database. "
                "Standard SQL — no analytical extensions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "db_name": {
                        "type": "string",
                        "description": "Logical database name from the DATABASE DESCRIPTION"
                    },
                    "sql": {
                        "type": "string",
                        "description": "SQL query to execute"
                    }
                },
                "required": ["db_name", "sql"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_postgres",
            "description": (
                "Run a SQL query against a PostgreSQL database. "
                "Supports standard SQL and PostgreSQL-specific functions. "
                "Quote mixed-case column names with double quotes (e.g. \"titleFull\", \"titlePart\") — "
                "unquoted identifiers are lowercased and will not match camelCase columns."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "db_name": {
                        "type": "string",
                        "description": "Logical database name from the DATABASE DESCRIPTION"
                    },
                    "sql": {
                        "type": "string",
                        "description": "SQL query to execute (use \"columnName\" for camelCase columns)"
                    }
                },
                "required": ["db_name", "sql"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "normalize_join_key",
            "description": (
                "Normalize a cross-database join key to its canonical integer form, "
                "then optionally re-prefix it for the target database. "
                "Use when a cross-DB join returns 0 rows due to prefix/format mismatch."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {
                        "type": "string",
                        "description": "Raw key value to normalize (e.g. 'bookid_42', '#001Wt000...')",
                    },
                    "target_prefix": {
                        "type": "string",
                        "description": "Optional prefix for target DB (e.g. 'purchaseid_'). If omitted, returns integer N.",
                    },
                },
                "required": ["value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "diagnose_join",
            "description": (
                "Diagnose why a cross-database join returned 0 results. "
                "Provide sample key values from both sides as JSON arrays. "
                "Returns detected formats and a suggested normalization strategy."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "left_values": {
                        "type": "string",
                        "description": "JSON array of sample key values from the left side",
                    },
                    "right_values": {
                        "type": "string",
                        "description": "JSON array of sample key values from the right side",
                    },
                },
                "required": ["left_values", "right_values"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_kb",
            "description": (
                "Look up a specific corrections entry or KB file on demand during the ReAct loop. "
                "Use this whenever you hit a known failure pattern — the Self-Correction Index in "
                "CRITICAL RULES maps symptoms to entry numbers. "
                "Examples: lookup_kb(entry_id='028') for DuckDB binder errors, "
                "lookup_kb(file='domain/unstructured_fields.md') for text-field parsing guidance. "
                "Call with no arguments to retrieve the full Self-Correction Index."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entry_id": {
                        "type": "string",
                        "description": "Corrections entry number, e.g. '028' or '001'. Searches both critical_rules.md and corrections-log.md.",
                    },
                    "file": {
                        "type": "string",
                        "description": "Relative path under kb/, e.g. 'domain/unstructured_fields.md' or 'domain/join_keys.md'.",
                    },
                },
                "required": [],
            },
        },
    },
        {
        "type": "function",
        "function": {
            "name": "return_answer",
            "description": (
                "Return the final verified answer. Call exactly once. "
                "Answer must be plain text only (AGENT.md §3): no markdown, no runner-ups for single-winner prompts, "
                "keep paired values adjacent, include every required list item from your last aggregation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string",
                        "description": "Single plain-text response matching the question and formatting rules"
                    }
                },
                "required": ["answer"]
            }
        }
    }
]

# ── Serialization helper ──────────────────────────────────────────────────────

def _make_json_serializable(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable types (ObjectId, datetime, Decimal, etc.) to str."""
    if isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_json_serializable(i) for i in obj]
    try:
        from decimal import Decimal
        if isinstance(obj, Decimal):
            return float(obj)
    except ImportError:
        pass
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


def _parse_query_arg(val: Any) -> Any:
    """Parse a tool 'query' argument that may arrive as a dict, list, or JSON string.
    Models like Gemini often pass structured args as objects rather than JSON-encoded strings."""
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        val = val.strip()
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            # Tolerate trailing content after valid JSON (e.g. Gemini adds a trailing newline)
            decoder = json.JSONDecoder()
            obj, _ = decoder.raw_decode(val)
            return obj
    return val

# ── Database executors ────────────────────────────────────────────────────────

def execute_mongodb_query(args: dict, uri: str, db_name: str) -> dict:
    """Execute a MongoDB find or aggregate query. Returns {success, rows, data}."""
    try:
        if not args.get("collection"):
            return {"success": False, "error": "Missing required parameter: collection. Specify the MongoDB collection name.", "rows": 0, "data": []}
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
        db     = client[db_name]
        coll   = db[args["collection"]]
        query      = _parse_query_arg(args.get("query", "{}"))
        query_type = args.get("query_type", "find")

        if query_type == "find":
            proj = _parse_query_arg(args["projection"]) if args.get("projection") else None
            cursor = coll.find(query, proj) if proj else coll.find(query)
            results = [_make_json_serializable(doc) for doc in cursor.limit(MAX_RESULT_ROWS)]
        else:
            pipeline = query if isinstance(query, list) else [query]
            results  = [_make_json_serializable(doc) for doc in coll.aggregate(pipeline)]

        client.close()
        return {"success": True, "rows": len(results), "data": results[:MAX_RESULT_ROWS]}
    except Exception as exc:
        logger.error("MongoDB query failed: %s", exc)
        return {"success": False, "error": str(exc), "rows": 0, "data": []}


def execute_duckdb_query(args: dict, db_path: str) -> dict:
    """Execute a DuckDB SQL query. Returns {success, rows, data}."""
    try:
        conn    = duckdb.connect(db_path, read_only=True)
        df      = conn.execute(args["sql"]).fetchdf()
        conn.close()
        records = df.to_dict(orient="records")
        return {"success": True, "rows": len(records), "data": records[:MAX_RESULT_ROWS]}
    except Exception as exc:
        logger.error("DuckDB query failed: %s", exc)
        return {"success": False, "error": str(exc), "rows": 0, "data": []}


def execute_sqlite_query(args: dict, db_path: str) -> dict:
    """Execute a SQLite SQL query. Returns {success, rows, data}."""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(args["sql"])
        rows = [dict(r) for r in cur.fetchmany(MAX_RESULT_ROWS)]
        conn.close()
        return {"success": True, "rows": len(rows), "data": rows}
    except Exception as exc:
        logger.error("SQLite query failed: %s", exc)
        return {"success": False, "error": str(exc), "rows": 0, "data": []}


def execute_postgres_query(args: dict, cfg: dict) -> dict:
    """Execute a PostgreSQL query. Returns {success, rows, data}."""
    try:
        conn = psycopg2.connect(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg["password"],
            dbname=cfg["db_name"],
        )
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(args["sql"])
        rows = [_make_json_serializable(dict(r)) for r in cur.fetchmany(MAX_RESULT_ROWS)]
        conn.close()
        return {"success": True, "rows": len(rows), "data": rows}
    except Exception as exc:
        logger.error("PostgreSQL query failed: %s", exc)
        return {"success": False, "error": str(exc), "rows": 0, "data": []}


def _direct_normalize_join(tool_args: dict) -> dict:
    if _JOIN_RESOLVER is None:
        return {"success": False, "error": "JoinKeyResolver not available"}
    raw = tool_args.get("value")
    if raw is None:
        return {"success": False, "error": "Missing required parameter: value"}
    target_prefix = tool_args.get("target_prefix")
    try:
        normalized_int = _JOIN_RESOLVER.normalize(raw, target_type="integer")
        if target_prefix is not None:
            result = f"{target_prefix}{normalized_int}"
        else:
            result = normalized_int
        detected = _JOIN_RESOLVER.detect_format([raw])
        return {
            "success": True,
            "original": raw,
            "normalized_int": normalized_int,
            "result": result,
            "detected_format": detected,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _direct_diagnose_join(tool_args: dict) -> dict:
    if _JOIN_RESOLVER is None:
        return {"success": False, "error": "JoinKeyResolver not available"}
    try:
        left_vals = json.loads(tool_args["left_values"])
        right_vals = json.loads(tool_args["right_values"])
    except (KeyError, json.JSONDecodeError) as exc:
        return {"success": False, "error": f"Invalid JSON input: {exc}"}
    try:
        left_format = _JOIN_RESOLVER.detect_format(left_vals)
        right_format = _JOIN_RESOLVER.detect_format(right_vals)
        left_norm = _JOIN_RESOLVER.normalize_batch(left_vals)
        right_norm = _JOIN_RESOLVER.normalize_batch(right_vals)
        overlap = set(left_norm) & set(right_norm)
        return {
            "success": True,
            "left_format": left_format,
            "right_format": right_format,
            "left_samples_normalized": left_norm[:5],
            "right_samples_normalized": right_norm[:5],
            "normalized_overlap_count": len(overlap),
            "suggestion": (
                "Normalize both sides to integer before joining. "
                f"Left prefix: '{left_format.get('prefix')}', "
                f"Right prefix: '{right_format.get('prefix')}'."
            )
            if left_format.get("prefix") != right_format.get("prefix")
            else "Key formats appear compatible after normalization.",
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}

# ── MongoDB restore ───────────────────────────────────────────────────────────

def restore_mongodb(db_config_path: str) -> None:
    """
    Restore MongoDB collections from BSON dump folders defined in db_config.yaml.
    Mirrors what the DAB scaffold does before each run.
    """
    import subprocess
    config_path = Path(db_config_path).resolve()
    config      = yaml.safe_load(config_path.read_text())
    base_dir    = config_path.parent

    for logical_name, details in config.get("db_clients", {}).items():
        if details.get("db_type") != "mongo":
            continue
        dump_folder = details.get("dump_folder")
        if not dump_folder:
            continue
        dump_path = base_dir / dump_folder
        if not dump_path.exists():
            logger.warning("MongoDB dump folder not found: %s", dump_path)
            continue
        cmd = ["mongorestore", "--drop", "--dir", str(dump_path)]
        logger.info("Restoring MongoDB from %s ...", dump_path)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("MongoDB restore OK: %s", result.stderr.strip().splitlines()[-1])
        else:
            logger.error("MongoDB restore failed: %s", result.stderr[-300:])

# ── Config loader ─────────────────────────────────────────────────────────────

def load_db_config(db_config_path: str) -> dict:
    """
    Parse db_config.yaml and return resolved connection details.

    Returns:
        {
            "mongo":  { logical_name: {"db_name": str, "uri": str} },
            "duckdb": { logical_name: abs_path_str }
        }
    """
    config_path = Path(db_config_path).resolve()
    config      = yaml.safe_load(config_path.read_text())
    base_dir    = config_path.parent

    mongo_dbs    = {}
    duckdb_paths = {}
    sqlite_paths = {}
    postgres_dbs = {}

    for logical_name, details in config.get("db_clients", {}).items():
        db_type = details.get("db_type", "")
        if db_type == "mongo":
            mongo_dbs[logical_name] = {
                "db_name": details["db_name"],
                "uri":     os.getenv("MONGO_URI", "mongodb://localhost:27017/")
            }
        elif db_type == "duckdb":
            duckdb_paths[logical_name] = str(base_dir / details["db_path"])
        elif db_type == "sqlite":
            sqlite_paths[logical_name] = str(base_dir / details["db_path"])
        elif db_type in ("postgres", "postgresql"):
            postgres_dbs[logical_name] = {
                "db_name":  details["db_name"],
                "host":     os.getenv("PG_HOST",     "localhost"),
                "port":     int(os.getenv("PG_PORT", "5432")),
                "user":     os.getenv("PG_USER",     "oracle_forge"),
                "password": os.getenv("PG_PASSWORD", "oracle_forge_pw"),
            }

    logger.info("Loaded config — mongo: %s, duckdb: %s, sqlite: %s, postgres: %s",
                list(mongo_dbs), list(duckdb_paths), list(sqlite_paths), list(postgres_dbs))
    return {"mongo": mongo_dbs, "duckdb": duckdb_paths, "sqlite": sqlite_paths, "postgres": postgres_dbs}

# ── KB lookup executor ───────────────────────────────────────────────────────

def _execute_lookup_kb(tool_args: dict) -> dict:
    """
    Serve lookup_kb tool calls: return a specific corrections entry or KB file.
    Searches critical_rules.md first (faster, always present), then corrections-log.md.
    """
    import re as _re
    entry_id = (tool_args.get("entry_id") or "").strip()
    file_path = (tool_args.get("file") or "").strip()

    if entry_id:
        num = _re.sub(r"[^0-9]", "", entry_id).zfill(3)
        pattern = rf"(## Entry {num} —[^\n]*\n.*?)(?=\n## Entry |\Z)"
        for source_path in (CRITICAL_RULES_LOG, CORRECTIONS_LOG):
            if not source_path.exists():
                continue
            raw = source_path.read_text(encoding="utf-8")
            m = _re.search(pattern, raw, _re.DOTALL)
            if m:
                content = m.group(1).strip()
                return {
                    "success": True,
                    "entry": f"Entry {num}",
                    "source": source_path.name,
                    "content": content[:3000],
                    "truncated": len(content) > 3000,
                }
        return {"success": False, "error": f"Entry {num} not found in corrections log or critical_rules.md"}

    if file_path:
        safe = (KB_ROOT / file_path).resolve()
        if not str(safe).startswith(str(KB_ROOT.resolve())):
            return {"success": False, "error": "Access denied: path must be inside kb/"}
        if not safe.exists():
            available = sorted(str(p.relative_to(KB_ROOT)) for p in KB_ROOT.rglob("*.md"))
            return {"success": False, "error": f"File not found: {file_path}", "available": available}
        raw = safe.read_text(encoding="utf-8")
        return {
            "success": True,
            "file": file_path,
            "content": raw[:4000],
            "truncated": len(raw) > 4000,
        }

    # No args: return Self-Correction Index from critical_rules.md
    if CRITICAL_RULES_LOG.exists():
        raw = CRITICAL_RULES_LOG.read_text(encoding="utf-8")
        import re as _re2
        m = _re2.search(r"## Self-Correction Index\n\n(.*?)(?=\n---|\Z)", raw, _re2.DOTALL)
        if m:
            return {"success": True, "content": "Self-Correction Index\n\n" + m.group(1).strip()}
    return {"success": False, "error": "Provide entry_id='NNN' or file='domain/file.md'"}


# ── Tool dispatcher ───────────────────────────────────────────────────────────

def dispatch_tool(tool_name: str, tool_args: dict, connections: dict) -> dict:
    """Route a tool call through MCP when possible; otherwise use direct drivers / local join utils."""
    if tool_name == "return_answer":
        return {"success": True, "answer": tool_args.get("answer", "")}

    if tool_name in ("normalize_join_key", "diagnose_join"):
        if _probe_mcp():
            result = _call_mcp(tool_name, tool_args)
            if result is not None:
                return result
            logger.warning("MCP failed for %s; using local JoinKeyResolver", tool_name)
        if tool_name == "normalize_join_key":
            return _direct_normalize_join(tool_args)
        return _direct_diagnose_join(tool_args)

    if tool_name == "query_mongodb":
        logical = tool_args.get("db_name", "")
        mongo_cfg = connections.get("mongo", {}).get(logical)
        if _probe_mcp():
            result = _call_mcp(tool_name, tool_args)
            if result is not None:
                return result
            logger.warning("MCP failed for query_mongodb; using pymongo")
        if not mongo_cfg:
            return {"success": False, "error": f"Unknown MongoDB db_name '{logical}' (direct fallback)"}
        return execute_mongodb_query(tool_args, mongo_cfg["uri"], mongo_cfg["db_name"])

    if tool_name == "query_duckdb":
        logical = tool_args.get("db_name", "")
        path = connections.get("duckdb", {}).get(logical)
        if _probe_mcp():
            result = _call_mcp(tool_name, tool_args)
            if result is not None:
                return result
            logger.warning("MCP failed for query_duckdb; using duckdb driver")
        if not path:
            return {"success": False, "error": f"Unknown DuckDB db_name '{logical}' (direct fallback)"}
        return execute_duckdb_query(tool_args, path)

    if tool_name == "query_sqlite":
        logical = tool_args.get("db_name", "")
        path = connections.get("sqlite", {}).get(logical)
        if _probe_mcp():
            result = _call_mcp(tool_name, tool_args)
            if result is not None:
                return result
            logger.warning("MCP failed for query_sqlite; using sqlite3")
        if not path:
            return {"success": False, "error": f"Unknown SQLite db_name '{logical}' (direct fallback)"}
        return execute_sqlite_query(tool_args, path)

    if tool_name == "query_postgres":
        logical = tool_args.get("db_name", "")
        cfg = connections.get("postgres", {}).get(logical)
        if _probe_mcp():
            result = _call_mcp(tool_name, tool_args)
            if result is not None:
                return result
            logger.warning("MCP failed for query_postgres; using psycopg2")
        if not cfg:
            return {"success": False, "error": f"Unknown PostgreSQL db_name '{logical}' (direct fallback)"}
        return execute_postgres_query(tool_args, cfg)

    if tool_name == "lookup_kb":
        return _execute_lookup_kb(tool_args)

    return {"success": False, "error": f"Unknown tool: {tool_name}"}


def _tool_signature(tool_name: str, tool_args: dict) -> str:
    """Stable signature for loop-detection of repeated tool calls."""
    try:
        return f"{tool_name}:{json.dumps(tool_args, sort_keys=True, ensure_ascii=False)}"
    except Exception:  # noqa: BLE001
        return f"{tool_name}:{str(tool_args)}"


def _force_compact_final_answer(
    client: OpenAI,
    model: str,
    messages: list[dict[str, Any]],
    fallback: str,
) -> str:
    """
    Ask the model once (no tools) to synthesize a compact final answer from
    already gathered tool outputs. Prevents max-iteration dead loops.
    """
    try:
        synth_messages = messages + [{
            "role": "user",
            "content": (
                "Stop calling tools. Based only on the tool results above, return the final answer now. "
                "Output plain text only, no markdown, no explanation, no query trace. "
                "If the question requires a complete list, include every item from the aggregated result, not a partial sample. "
                "For single-winner questions, output only the winner. "
                "Do not output refusal text like 'cannot complete', 'insufficient data', or 'no answer possible' "
                "if evidence rows exist; return the best evidence-backed compact answer."
            ),
        }]
        resp = client.chat.completions.create(
            model=model,
            messages=synth_messages,
            temperature=0,
            max_tokens=512,
            timeout=90,
        )
        text = (resp.choices[0].message.content or "").strip()
        return text or fallback
    except Exception:  # noqa: BLE001
        return fallback


def _needs_compaction(answer: str) -> bool:
    """Heuristic: detect verbose narrative answers that often fail validators."""
    text = (answer or "").strip()
    if not text:
        return False
    if len(text) > 240:
        return True
    lowered = text.lower()
    narrative_markers = (
        "to answer this",
        "i will",
        "based on",
        "from the sample",
        "assuming",
        "therefore",
        "final answer:",
        "cannot complete",
        "insufficient data",
        "no answer possible",
        "not available",
        "cannot determine",
        "no state",
    )
    if any(m in lowered for m in narrative_markers):
        return True
    placeholder_values = {"none", "n/a", "na", "null", "unknown", "no answer"}
    return lowered in placeholder_values


def _has_usable_evidence(query_trace: list[dict[str, Any]]) -> bool:
    """True when at least one tool call succeeded with non-empty evidence."""
    for step in query_trace:
        if not step.get("success"):
            continue
        rows = step.get("rows")
        if isinstance(rows, int) and rows > 0:
            return True
        preview = str(step.get("preview", "")).strip().lower()
        if preview and preview not in {"[]", "none", "null"}:
            return True
    return False


# ── System prompt builder ─────────────────────────────────────────────────────

def _build_system_prompt(
    db_config_path: str, db_description: str, connections: dict | None = None
) -> str:
    """
    Assemble the full system prompt from five layers:
      1. AGENT.md           — generic ReAct protocol (dataset-agnostic)
      2. Corrections log    — kb/corrections/corrections-log.md (all past failures + fixes)
      3. Domain KB          — kb/domain/<dataset>.md if it exists
      4. Live schema        — dynamically introspected from each connected DB (SchemaIntrospector)
      5. DB description     — passed in from harness (human-written schema + hints)
    """
    parts: list[str] = []
    strict_no_leakage = os.getenv("ORACLE_FORGE_STRICT_NO_LEAKAGE", "").strip().lower() in {"1", "true", "yes", "on"}
    # Optional: allow strict mode to omit memory layers entirely (debugging).
    omit_kb_in_strict = os.getenv("ORACLE_FORGE_STRICT_OMIT_KB", "").strip().lower() in {"1", "true", "yes", "on"}

    def _truncate(label: str, text: str, max_chars: int) -> str:
        t = (text or "").strip()
        if len(t) <= max_chars:
            return t
        return t[: max_chars - 200] + f"\n\n[... truncated {label}: {len(t)} chars -> {max_chars} chars ...]\n"

    # 1. Generic agent protocol
    if AGENT_MD_PATH.exists():
        parts.append(_truncate("AGENT.md", AGENT_MD_PATH.read_text(encoding="utf-8"), 18000))

    # 1b. Critical rules — self-correction index + top-priority entries (compact, always fits)
    if not (strict_no_leakage and omit_kb_in_strict):
        if CRITICAL_RULES_LOG.exists():
            cr_raw = CRITICAL_RULES_LOG.read_text(encoding="utf-8")
            cr_text = _truncate("critical_rules", cr_raw, 10000)
            parts.append("---\n\n## CRITICAL RULES\n\n" + cr_text)
            if len(cr_text.strip()) < len(cr_raw.strip()):
                logger.warning("critical_rules.md was truncated — trim the file or increase budget")
        else:
            logger.warning("critical_rules.md not found: %s", CRITICAL_RULES_LOG)

    # 2. Core methodology KB (leakage-safe, dataset-agnostic)
    if not (strict_no_leakage and omit_kb_in_strict):
        core_kb_files = [
            KB_ROOT / "domain" / "dab_schemas.md",
            KB_ROOT / "domain" / "query_patterns.md",
            KB_ROOT / "domain" / "join_keys.md",
            KB_ROOT / "domain" / "unstructured_fields.md",
            KB_ROOT / "domain" / "domain_terms.md",
        ]
        core_chunks: list[str] = []
        for p in core_kb_files:
            if p.exists():
                core_chunks.append(p.read_text(encoding="utf-8"))
        if core_chunks:
            core_text = "\n\n---\n\n".join(core_chunks)
            parts.append("---\n\n## CORE KB (METHODOLOGY)\n\n" + _truncate("core_kb", core_text, 24000))

    # 3. Corrections log — allowed (leakage-linted), but can be omitted in strict if requested.
    if strict_no_leakage:
        parts.append(
            "---\n\n## STRICT MODE\n\n"
            "Final answers must follow only from tool results and reasoning — no post-hoc rewriting "
            "to match benchmark rubrics. Knowledge layers must remain leakage-safe.\n\n"
            "Before `return_answer`, re-check AGENT.md §3 (format), §12 (aggregation/ranking), and DOMAIN KNOWLEDGE "
            "for the active dataset."
        )
    if not (strict_no_leakage and omit_kb_in_strict):
        if CORRECTIONS_LOG.exists():
            parts.append("---\n\n## CORRECTIONS LOG\n\n" + _truncate("corrections-log", CORRECTIONS_LOG.read_text(encoding="utf-8"), 8000))
        else:
            logger.warning("Corrections log not found: %s", CORRECTIONS_LOG)

    # 4. Dataset-specific domain knowledge — allowed if leakage-safe; can be omitted in strict if requested.
    dataset_name = Path(db_config_path).parent.name.replace("query_", "")
    domain_file  = KB_ROOT / "domain" / f"{dataset_name}.md"
    if domain_file.exists() and not (strict_no_leakage and omit_kb_in_strict):
        parts.append(
            f"---\n\n## DOMAIN KNOWLEDGE ({dataset_name})\n\n"
            + _truncate(f"domain:{dataset_name}", domain_file.read_text(encoding="utf-8"), 12000)
        )

    # 5. Live schema — introspect each connected DB and format as markdown
    if _SCHEMA_INTROSPECTOR is not None and connections:
        schema_sections: list[str] = []

        for logical_name, cfg in connections.get("mongo", {}).items():
            try:
                schema = _SCHEMA_INTROSPECTOR.introspect(
                    "mongodb",
                    connection_string=cfg["uri"],
                    db_name=cfg["db_name"],
                )
                schema_sections.append(
                    f"### {logical_name} (MongoDB — {cfg['db_name']})\n"
                    + _truncate("live_schema_mongo", _SCHEMA_INTROSPECTOR.format_for_context(schema), _MAX_SCHEMA_SECTION_CHARS)
                )
            except Exception as exc:
                logger.warning("Schema introspection failed for %s: %s", logical_name, exc)

        for logical_name, db_path in connections.get("duckdb", {}).items():
            if Path(db_path).exists():
                try:
                    schema = _SCHEMA_INTROSPECTOR.introspect("duckdb", path=db_path)
                    schema_sections.append(
                        f"### {logical_name} (DuckDB — {Path(db_path).name})\n"
                        + _truncate("live_schema_duckdb", _SCHEMA_INTROSPECTOR.format_for_context(schema), _MAX_SCHEMA_SECTION_CHARS)
                    )
                except Exception as exc:
                    logger.warning("Schema introspection failed for %s: %s", logical_name, exc)

        for logical_name, db_path in connections.get("sqlite", {}).items():
            if Path(db_path).exists():
                try:
                    schema = _SCHEMA_INTROSPECTOR.introspect("sqlite", path=db_path)
                    schema_sections.append(
                        f"### {logical_name} (SQLite — {Path(db_path).name})\n"
                        + _truncate("live_schema_sqlite", _SCHEMA_INTROSPECTOR.format_for_context(schema), _MAX_SCHEMA_SECTION_CHARS)
                    )
                except Exception as exc:
                    logger.warning("Schema introspection failed for %s: %s", logical_name, exc)

        for logical_name, cfg in connections.get("postgres", {}).items():
            try:
                conn_str = (
                    f"postgresql://{cfg['user']}:{cfg['password']}"
                    f"@{cfg['host']}:{cfg['port']}/{cfg['db_name']}"
                )
                schema = _SCHEMA_INTROSPECTOR.introspect("postgresql", connection_string=conn_str)
                schema_sections.append(
                    f"### {logical_name} (PostgreSQL — {cfg['db_name']})\n"
                    + _truncate("live_schema_postgres", _SCHEMA_INTROSPECTOR.format_for_context(schema), _MAX_SCHEMA_SECTION_CHARS)
                )
            except Exception as exc:
                logger.warning("Schema introspection failed for %s: %s", logical_name, exc)

        if schema_sections:
            parts.append("---\n\n## LIVE SCHEMA\n\n" + "\n\n".join(schema_sections))

    # 6. Current dataset schema / DB description (human-written, always present)
    parts.append("---\n\n## DATABASE DESCRIPTION\n\n" + _truncate("db_description", db_description, _MAX_DB_DESC_CHARS))

    full = "\n\n".join(parts).strip()
    if os.getenv("ORACLE_FORGE_LOG_CONTEXT_LAYERS", "").strip().lower() in {"1", "true", "yes", "on"}:
        markers = [m for m in ("CRITICAL RULES", "CORE KB (METHODOLOGY)", "CORRECTIONS LOG", "DOMAIN KNOWLEDGE", "STRICT MODE", "LIVE SCHEMA", "DATABASE DESCRIPTION") if m in full]
        logger.info(
            "system_prompt layers: chars=%s strict_no_leakage=%s omit_kb_in_strict=%s markers=%s",
            len(full),
            strict_no_leakage,
            omit_kb_in_strict,
            markers,
        )
    return _truncate("system_prompt_total", full, _MAX_SYSTEM_PROMPT_CHARS)


# ── PostgreSQL loader ─────────────────────────────────────────────────────────

def ensure_postgres_loaded(db_config_path: str) -> None:
    """
    For each PostgreSQL entry in db_config.yaml, check if the database exists.
    If not and a sql_file is provided, load it via psql.
    Skips gracefully when the oracle_forge user lacks superuser privileges.
    """
    import subprocess
    config_path = Path(db_config_path).resolve()
    config      = yaml.safe_load(config_path.read_text())
    base_dir    = config_path.parent

    pg_user     = os.getenv("PG_USER",     "oracle_forge")
    pg_password = os.getenv("PG_PASSWORD", "oracle_forge_pw")
    pg_host     = os.getenv("PG_HOST",     "localhost")
    pg_port     = int(os.getenv("PG_PORT", "5432"))

    for logical_name, details in config.get("db_clients", {}).items():
        if details.get("db_type") not in ("postgres", "postgresql"):
            continue
        db_name  = details.get("db_name", "")
        sql_file = details.get("sql_file")
        if not db_name:
            continue

        # Check if database already exists
        try:
            conn = psycopg2.connect(
                dbname="postgres", user=pg_user, password=pg_password,
                host=pg_host, port=pg_port
            )
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            exists = cur.fetchone() is not None
            conn.close()
        except Exception as exc:
            logger.warning("Cannot check PostgreSQL for %s: %s", logical_name, exc)
            continue

        if exists:
            logger.info("PostgreSQL DB '%s' already exists — skipping load.", db_name)
            continue

        if not sql_file:
            logger.warning("PostgreSQL DB '%s' missing and no sql_file specified.", db_name)
            continue

        sql_path = base_dir / sql_file
        if not sql_path.exists():
            logger.warning("PostgreSQL sql_file not found: %s", sql_path)
            continue

        # Create DB then load
        try:
            conn = psycopg2.connect(
                dbname="postgres", user=pg_user, password=pg_password,
                host=pg_host, port=pg_port
            )
            conn.autocommit = True
            conn.cursor().execute(f'CREATE DATABASE "{db_name}"')
            conn.close()
        except Exception as exc:
            logger.warning("Could not create PostgreSQL DB '%s': %s — skipping.", db_name, exc)
            continue

        # Strip ownership transfer lines — oracle_forge cannot transfer ownership to
        # other roles (e.g. postgres), so filter them out before loading.
        # The tables will be owned by oracle_forge, which has full access.
        import tempfile
        with open(sql_path, encoding="utf-8") as _f:
            filtered_sql = "\n".join(
                line for line in _f
                if "OWNER TO" not in line and "SET ROLE" not in line
            )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sql", delete=False, encoding="utf-8"
        ) as _tmp:
            _tmp.write(filtered_sql)
            tmp_sql_path = _tmp.name

        env = os.environ.copy()
        env["PGPASSWORD"] = pg_password
        cmd = ["psql", "-h", pg_host, "-p", str(pg_port), "-U", pg_user, "-d", db_name, "-f", tmp_sql_path]
        logger.info("Loading PostgreSQL DB '%s' from %s (ownership lines stripped) ...", db_name, sql_path)
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        try:
            os.unlink(tmp_sql_path)
        except OSError:
            pass
        if result.returncode == 0:
            logger.info("PostgreSQL load OK for '%s'.", db_name)
        else:
            logger.error("PostgreSQL load failed for '%s': %s", db_name, result.stderr[-300:])


# ── Main agent ────────────────────────────────────────────────────────────────

def run_agent(query: str, db_config_path: str, db_description: str) -> str:
    """
    Run the ReAct-style data analytics agent.

    Args:
        query:          Natural language question to answer.
        db_config_path: Path to db_config.yaml for this dataset.
        db_description: Schema description text (contents of db_description.txt).

    Returns:
        dict with keys:
          - "answer" (str): the agent's final answer as plain text
          - "query_trace" (list): list of tool-call trace dicts, each with keys
            tool, args, success, rows, preview
        Note: agent_runner_child.py unpacks this dict; callers expecting a plain
        string should use result["answer"].
    """
    load_dotenv()

    # Restore MongoDB collections from dump (matches DAB scaffold behaviour)
    restore_mongodb(db_config_path)

    # Ensure PostgreSQL databases are loaded (skips gracefully if already present)
    ensure_postgres_loaded(db_config_path)

    # Load DB connections from config
    connections = load_db_config(db_config_path)

    # Build system prompt: AGENT.md + corrections log + domain KB + live schema + DB description
    system_prompt = _build_system_prompt(db_config_path, db_description, connections)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": query}
    ]

    query_trace  = []
    final_answer = None
    repeat_counts: dict[str, int] = {}
    forced_finalize = False

    def _result_for_llm(result: dict) -> dict:
        """Shrink tool results before adding them to the LLM conversation."""
        if not isinstance(result, dict):
            return {"success": False, "error": "non_dict_tool_result"}
        out = {k: result.get(k) for k in ("success", "rows", "error") if k in result}
        data = result.get("data")
        if isinstance(data, list):
            # Bounded sample for context; size tunable via ORACLE_FORGE_TOOL_PREVIEW_ROWS.
            keep = max(1, _TOOL_PREVIEW_ROWS)
            out["data"] = data[:keep]
            if len(data) > keep:
                out["data_truncated"] = {"kept": keep, "original_len": len(data)}
        elif isinstance(data, (str, int, float, bool)) or data is None:
            out["data"] = data
        else:
            out["data"] = str(data)[:2000]
        return out

    for iteration in range(MAX_ITERATIONS):
        logger.info("── Iteration %d/%d ──", iteration + 1, MAX_ITERATIONS)

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                temperature=0,
                max_tokens=4096,
                timeout=120
            )
        except Exception as exc:
            err_str = str(exc)
            logger.error("LLM call failed: %s", exc)
            # Surface billing/auth errors clearly so they don't look like agent failures
            if "402" in err_str or "Insufficient credits" in err_str:
                raise RuntimeError(f"LLM API billing error (402): {err_str[:200]}") from exc
            if "401" in err_str:
                raise RuntimeError(f"LLM API auth error (401) — check API key: {err_str[:200]}") from exc
            return {"answer": "The agent could not complete this request due to an upstream error. Retry later.", "query_trace": query_trace}

        msg = response.choices[0].message

        # No tool calls → model returned plain text instead of using a tool.
        # Push back up to 3 times to force tool usage; only accept on the 4th occurrence.
        if not msg.tool_calls:
            plain_text = (msg.content or "").strip()
            logger.info("Plain text (no tool call, iter %d): %s", iteration + 1, plain_text[:120])
            no_tool_count = sum(
                1 for m in messages if m.get("role") == "user"
                and "You must call a tool" in (m.get("content") or "")
            )
            if no_tool_count < 3:
                messages.append({"role": "assistant", "content": plain_text})
                messages.append({
                    "role": "user",
                    "content": (
                        "You must call a tool — do NOT return a text answer directly. "
                        "Call a database query tool (query_duckdb, query_sqlite, query_mongodb, query_postgres) "
                        "or lookup_kb() to gather evidence before answering. "
                        "Check the DATABASE DESCRIPTION for exact db_name values and table names."
                    ),
                })
                continue
            final_answer = plain_text
            break

        # Append assistant message with tool calls
        messages.append({
            "role":       "assistant",
            "tool_calls": [tc.model_dump() for tc in msg.tool_calls]
        })

        done = False
        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)
            signature = _tool_signature(tool_name, tool_args)
            repeat_counts[signature] = repeat_counts.get(signature, 0) + 1

            logger.info("Tool: %s | args: %s", tool_name, json.dumps(tool_args)[:300])
            result = dispatch_tool(tool_name, tool_args, connections)

            if tool_name == "return_answer":
                final_answer = tool_args.get("answer", "")
                logger.info("Answer: %s", final_answer)
                done = True
                break

            # Record to query trace
            preview_obj: Any
            if result.get("success") is False and result.get("error"):
                preview_obj = result.get("error")
            else:
                preview_obj = result.get("data") if "data" in result else result.get("error", result)
            query_trace.append({
                "tool":    tool_name,
                "args":    tool_args,
                "success": result.get("success"),
                "rows":    result.get("rows"),
                "preview": str(preview_obj)[:400]
            })

            # Append tool result for next iteration
            messages.append({
                "role":         "tool",
                "tool_call_id": tool_call.id,
                "name":         tool_name,
                "content":      json.dumps(_result_for_llm(result), ensure_ascii=False)
            })

            # Prevent pathological loops, but allow enough retries for hard queries.
            if repeat_counts[signature] >= 5 and not done:
                logger.warning("Detected repeated tool call (%s) x%d; forcing finalization.", tool_name, repeat_counts[signature])
                forced_finalize = True
                break

        if done:
            break
        if forced_finalize:
            break

    if final_answer is None:
        logger.warning("No final answer by tool call; synthesizing compact final answer.")
        if _DISABLE_FORCE_COMPACT:
            final_answer = ""
        else:
            final_answer = _force_compact_final_answer(client, model, messages, fallback="")
    elif (not _DISABLE_FORCE_COMPACT) and _needs_compaction(final_answer):
        logger.info("Compacting verbose final answer for validator compatibility.")
        final_answer = _force_compact_final_answer(client, model, messages, fallback=final_answer)

    # If we still have a placeholder/refusal answer but tool evidence exists, compact once more.
    if (not _DISABLE_FORCE_COMPACT) and _needs_compaction(final_answer) and _has_usable_evidence(query_trace):
        logger.info("Refusal/placeholder answer with usable evidence detected; forcing compact synthesis.")
        final_answer = _force_compact_final_answer(client, model, messages, fallback=final_answer)

    logger.info("Query trace (%d steps):\n%s", len(query_trace), json.dumps(query_trace, indent=2))
    return {"answer": final_answer, "query_trace": query_trace}

# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S"
    )

    parser = argparse.ArgumentParser(description="Oracle Forge Data Analytics Agent")
    parser.add_argument("--query",          required=True, help="Natural language question")
    parser.add_argument("--db_config",      required=True, help="Path to db_config.yaml")
    parser.add_argument("--db_description", required=True, help="Path to db_description.txt")
    parser.add_argument("--model", default=DEFAULT_MODEL,  help="OpenRouter model name")
    args = parser.parse_args()

    os.environ.setdefault("OPENROUTER_MODEL", args.model)

    db_description = Path(args.db_description).read_text()
    result = run_agent(
        query=args.query,
        db_config_path=args.db_config,
        db_description=db_description
    )

    print(f"\n{'─'*60}")
    print(f"Answer: {result['answer']}")
    print(f"Query trace ({len(result['query_trace'])} steps):")
    print(json.dumps(result['query_trace'], indent=2))
    print(f"{'─'*60}")
