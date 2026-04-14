"""
agent/data_agent.py — Oracle Forge Data Analytics Agent

ReAct-style agent: Think → Act (query DB) → Observe → Think → Answer
Uses Claude via OpenRouter. Database access routes through the Oracle Forge
MCP server (mcp/toolbox_server.py) when available; falls back to direct
Python drivers (pymongo, duckdb) if the MCP server is not running.
Loads AGENT.md as system context at startup.
"""

import os
import json
import logging
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

# ── Constants ────────────────────────────────────────────────────────────────

AGENT_MD_PATH = Path(__file__).parent / "AGENT.md"
DEFAULT_MODEL  = "anthropic/claude-haiku-4.5"
MAX_ITERATIONS = 30
MAX_RESULT_ROWS = 500   # cap rows returned to LLM to avoid context overflow
MCP_URL        = os.getenv("MCP_URL", "http://127.0.0.1:5000/mcp")

logger = logging.getLogger(__name__)

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
                "Use query_type='find' for simple filters, 'aggregate' for pipelines. "
                "Returns a list of matching documents."
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
                "Supports analytical SQL including TRY_STRPTIME, window functions, CTEs."
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
                "Supports standard SQL and PostgreSQL-specific functions."
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
            "name": "return_answer",
            "description": "Return the final verified answer. Call this exactly once when you have the answer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string",
                        "description": "Final answer as a plain text string"
                    }
                },
                "required": ["answer"]
            }
        }
    }
]

# ── Serialization helper ──────────────────────────────────────────────────────

def _make_json_serializable(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable types (ObjectId, datetime, etc.) to str."""
    if isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_json_serializable(i) for i in obj]
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)

# ── Database executors ────────────────────────────────────────────────────────

def execute_mongodb_query(args: dict, uri: str, db_name: str) -> dict:
    """Execute a MongoDB find or aggregate query. Returns {success, rows, data}."""
    try:
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
        db     = client[db_name]
        coll   = db[args["collection"]]
        query  = json.loads(args["query"])

        if args["query_type"] == "find":
            proj = json.loads(args["projection"]) if args.get("projection") else None
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

# ── Tool dispatcher ───────────────────────────────────────────────────────────

def dispatch_tool(tool_name: str, tool_args: dict, connections: dict) -> dict:
    """Route a tool call through the MCP server (required)."""
    if tool_name == "return_answer":
        return {"success": True, "answer": tool_args.get("answer", "")}

    if tool_name in ("query_mongodb", "query_duckdb", "query_sqlite", "query_postgres"):
        if not _probe_mcp():
            return {"success": False, "error": "MCP server is not available — harness should have started it"}
        result = _call_mcp(tool_name, tool_args)
        if result is None:
            return {"success": False, "error": f"MCP call to {tool_name} failed"}
        return result

    return {"success": False, "error": f"Unknown tool: {tool_name}"}

# ── Main agent ────────────────────────────────────────────────────────────────

def run_agent(query: str, db_config_path: str, db_description: str) -> str:
    """
    Run the ReAct-style data analytics agent.

    Args:
        query:          Natural language question to answer.
        db_config_path: Path to db_config.yaml for this dataset.
        db_description: Schema description text (contents of db_description.txt).

    Returns:
        Agent's answer as a plain text string.
    """
    load_dotenv()

    # Restore MongoDB collections from dump (matches DAB scaffold behaviour)
    restore_mongodb(db_config_path)

    # Load DB connections from config
    connections = load_db_config(db_config_path)

    # Build system prompt: AGENT.md + current dataset description
    agent_context = AGENT_MD_PATH.read_text() if AGENT_MD_PATH.exists() else ""
    system_prompt = (
        f"{agent_context}\n\n"
        f"---\n\n"
        f"## DATABASE DESCRIPTION\n\n{db_description}"
    ).strip()

    # Init LLM client (OpenRouter)
    client = OpenAI(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        base_url="https://openrouter.ai/api/v1"
    )
    model = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
    logger.info("Model: %s", model)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": query}
    ]

    query_trace  = []
    final_answer = None

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
            logger.error("LLM call failed: %s", exc)
            return {"answer": f"Agent error: {exc}", "query_trace": query_trace}

        msg = response.choices[0].message

        # No tool calls → agent produced a plain text answer (fallback)
        if not msg.tool_calls:
            final_answer = msg.content or ""
            logger.info("Plain text answer (no tool call): %s", final_answer)
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

            logger.info("Tool: %s | args: %s", tool_name, json.dumps(tool_args)[:300])
            result = dispatch_tool(tool_name, tool_args, connections)

            if tool_name == "return_answer":
                final_answer = tool_args.get("answer", "")
                logger.info("Answer: %s", final_answer)
                done = True
                break

            # Record to query trace
            query_trace.append({
                "tool":    tool_name,
                "args":    tool_args,
                "success": result.get("success"),
                "rows":    result.get("rows"),
                "preview": str(result.get("data", result.get("error", "")))[:400]
            })

            # Append tool result for next iteration
            messages.append({
                "role":         "tool",
                "tool_call_id": tool_call.id,
                "name":         tool_name,
                "content":      json.dumps(result)
            })

        if done:
            break

    if final_answer is None:
        logger.warning("Max iterations (%d) reached without answer", MAX_ITERATIONS)
        final_answer = ""

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
