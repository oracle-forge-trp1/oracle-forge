# MCP Toolbox Patterns — Oracle Forge

## What This Document Is

Working reference for how the Oracle Forge agent communicates with databases via the Model Context Protocol (MCP). Load this when the agent needs to understand why a tool call failed, how to structure a retry, or what happens when the MCP server is unreachable.

---

## Protocol Overview

The Oracle Forge MCP server (`mcp/toolbox_server.py`) implements JSON-RPC 2.0 over HTTP.

**Endpoint:** `POST http://127.0.0.1:5000/mcp`  
**Health check:** `GET http://127.0.0.1:5000/health` → returns 200 when ready  
**Start command:** `conda run -n dabench python mcp/toolbox_server.py`

Every request follows this envelope:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "<tool_name>",
    "arguments": { ... }
  }
}
```

Every response unpacks to an inner result dict via `result.content[0].text`:
```json
{ "success": true, "rows": 12, "data": [ ... ] }
```

On failure: `{ "success": false, "error": "<reason>", "rows": 0, "data": [] }`

---

## Four Tool Types (One Per Database)

| Tool name | Database | Query format |
|-----------|----------|--------------|
| `query_mongodb` | MongoDB | find (filter dict) or aggregate (pipeline array) |
| `query_duckdb` | DuckDB | SQL — supports CTEs, window functions, TRY_STRPTIME |
| `query_sqlite` | SQLite | SQL — standard only, no analytical extensions |
| `query_postgres` | PostgreSQL | SQL — full PostgreSQL dialect including JSONB |

**Tool scoping rule:** One tool per DB type. The agent selects by tool name, not by routing logic. If a question requires MongoDB and DuckDB, the agent calls both tools in sequence and joins the results in memory.

---

## Fallback Pattern

When the MCP server is not reachable (connection refused, timeout), `data_agent.py` falls back to direct Python drivers:

| Database | Direct driver | Import |
|----------|--------------|--------|
| MongoDB | pymongo | `pymongo.MongoClient(uri)` |
| DuckDB | duckdb | `duckdb.connect(path, read_only=True)` |
| PostgreSQL | psycopg2 | `psycopg2.connect(host, port, user, password, dbname)` |
| SQLite | sqlite3 | `sqlite3.connect(path)` |

The agent probes MCP availability once at startup with a `tools/list` call. If unavailable, all DB queries go through direct drivers for that session.

---

## MAX_ROWS Cap

Every tool executor caps results at **500 rows** before returning to the agent. This prevents LLM context overflow on large tables. If a query returns exactly 500 rows, assume the result is truncated — add a `LIMIT` clause or aggregate before returning.

---

## Two Diagnostic Tools

Beyond the four query tools, the MCP server also exposes:

- **`normalize_join_key`** — strips a cross-DB prefix and returns the canonical integer (e.g., `"businessid_42"` → `42`). Use when a cross-DB join returns 0 rows.
- **`diagnose_join`** — takes sample key values from both sides of a join and returns detected formats, mismatch type, and suggested fix. Use when you don't know which side has the prefix.

---

## Common Failure Modes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `"error": "Unknown db_name 'X'"` | db_name not in db_config.yaml | Use exact logical name from DATABASE DESCRIPTION |
| Cross-DB join returns 0 rows | Key format mismatch (businessid_N ≠ businessref_N) | Call `normalize_join_key` or `diagnose_join` |
| `"error": "Connection refused"` | MCP server not running | Start with `conda run -n dabench python mcp/toolbox_server.py` |
| Results truncated at 500 | MAX_ROWS cap hit | Add `LIMIT`/`$limit` or aggregate in the query |
