"""
agent/data_agent.py — Oracle Forge Data Analytics Agent

ReAct-style agent: Think → Act (query DB) → Observe → Think → Answer
Uses Claude via OpenRouter. Connects directly to MongoDB and DuckDB.
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
from openai import OpenAI
from dotenv import load_dotenv

# ── Constants ────────────────────────────────────────────────────────────────

AGENT_MD_PATH = Path(__file__).parent / "AGENT.md"
DEFAULT_MODEL  = "anthropic/claude-haiku-4.5"
MAX_ITERATIONS = 30
MAX_RESULT_ROWS = 500   # cap rows returned to LLM to avoid context overflow

logger = logging.getLogger(__name__)

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

    for logical_name, details in config.get("db_clients", {}).items():
        db_type = details.get("db_type", "")
        if db_type == "mongo":
            mongo_dbs[logical_name] = {
                "db_name": details["db_name"],
                "uri":     os.getenv("MONGO_URI", "mongodb://localhost:27017/")
            }
        elif db_type == "duckdb":
            # db_path in yaml is relative to the config file's directory
            duckdb_paths[logical_name] = str(base_dir / details["db_path"])
        elif db_type in ("postgresql", "postgres"):
            # Future: add PostgreSQL support here
            logger.info("PostgreSQL connection for '%s' not yet implemented", logical_name)
        elif db_type == "sqlite":
            # Future: add SQLite support here
            logger.info("SQLite connection for '%s' not yet implemented", logical_name)

    logger.info("Loaded config — mongo: %s, duckdb: %s", list(mongo_dbs), list(duckdb_paths))
    return {"mongo": mongo_dbs, "duckdb": duckdb_paths}

# ── Tool dispatcher ───────────────────────────────────────────────────────────

def dispatch_tool(tool_name: str, tool_args: dict, connections: dict) -> dict:
    """Route a tool call to the correct database executor."""
    if tool_name == "query_mongodb":
        logical = tool_args["db_name"]
        if logical not in connections["mongo"]:
            available = list(connections["mongo"].keys())
            return {"success": False, "error": f"Unknown MongoDB db_name '{logical}'. Available: {available}"}
        cfg = connections["mongo"][logical]
        return execute_mongodb_query(tool_args, cfg["uri"], cfg["db_name"])

    elif tool_name == "query_duckdb":
        logical = tool_args["db_name"]
        if logical not in connections["duckdb"]:
            available = list(connections["duckdb"].keys())
            return {"success": False, "error": f"Unknown DuckDB db_name '{logical}'. Available: {available}"}
        return execute_duckdb_query(tool_args, connections["duckdb"][logical])

    elif tool_name == "return_answer":
        return {"success": True, "answer": tool_args.get("answer", "")}

    else:
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
            return f"Agent error: {exc}"

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
    return final_answer

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
    answer = run_agent(
        query=args.query,
        db_config_path=args.db_config,
        db_description=db_description
    )

    print(f"\n{'─'*60}")
    print(f"Answer: {answer}")
    print(f"{'─'*60}")
