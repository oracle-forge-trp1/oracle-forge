# MCP Toolbox Patterns for Multi-Database Agents

## What MCP Toolbox Does
MCP Toolbox for Databases (by Google, v0.30.0, March 2026) provides an MCP server that connects AI agents to databases through a standard protocol. A single `tools.yaml` defines all database connections and tools. The agent calls tools via JSON-RPC instead of writing raw database drivers.

## Why We Built a Custom MCP Server
Google's binary (`genai-toolbox`) natively supports PostgreSQL, MySQL, SQL Server, Cloud SQL, AlloyDB, Spanner, and Bigtable. It does **NOT** support MongoDB, DuckDB, or SQLite — three of the four database types DAB requires. Our Python MCP server (`mcp/toolbox_server.py`) implements the same JSON-RPC 2.0 protocol but adds support for all four DAB types.

## tools.yaml Configuration Pattern

The config has three sections: **sources** (database connections), **tools** (operations), and **toolsets** (grouped tools per use case).

```yaml
sources:
  mongo-yelp:
    kind: mongodb
    uri: "mongodb://localhost:27017/"
    database: yelp_db

  duckdb-yelp:
    kind: duckdb
    database: "/path/to/yelp_user.db"

tools:
  query_mongodb:
    source: mongo-yelp
    parameters:
      - name: collection
      - name: query_type    # find or aggregate
      - name: query          # JSON string

  query_duckdb:
    source: duckdb-yelp
    parameters:
      - name: sql

toolsets:
  oracle-forge:
    tools: [query_mongodb, query_duckdb, query_postgres, query_sqlite]
```

## Key Patterns for Oracle Forge

### Pattern 1 — One Tool Per Database Type
Each database type gets its own tool (`query_mongodb`, `query_duckdb`, `query_sqlite`, `query_postgres`). The agent decides which tool to call based on the dataset's `db_config.yaml`. This mirrors Claude Code's tool scoping — discrete, permission-gated capabilities.

### Pattern 2 — Logical Name Resolution
The agent refers to databases by logical name (e.g., `businessinfo_database`) from the dataset's `db_config.yaml`. The MCP server resolves this to the physical connection. The agent never sees connection strings.

### Pattern 3 — Dataset-Driven Auto-Registration
Our MCP server reads `db_config.yaml` at startup and auto-registers all databases found. When switching datasets, restart the server with a new config — no code changes needed.

### Pattern 4 — Result Capping
Results are capped at 500 rows (`MAX_ROWS`) to prevent context overflow. The agent receives a `rows` count in every response so it knows if results were truncated.

### Pattern 5 — MongoDB Requires Two Query Modes
MongoDB needs both `find` (filter + projection) and `aggregate` (pipeline). The `query_type` parameter lets the agent choose. SQL databases only need a `sql` parameter.

## Protocol
- **Endpoint:** `http://localhost:5000/mcp` (POST)
- **Health:** `http://localhost:5000/health` (GET)
- **Methods:** `initialize`, `tools/list`, `tools/call`
- **Format:** JSON-RPC 2.0 over HTTP

## What This Means for the Agent
The agent doesn't import `pymongo` or `duckdb` directly. It sends JSON-RPC tool calls to the MCP server. This means the agent code is database-agnostic — adding a new database type requires only a new tool in tools.yaml and a handler in the MCP server, not changes to the agent.
