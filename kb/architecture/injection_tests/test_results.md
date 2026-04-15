# Architecture KB — Injection Test Results

Injection tests verify that each KB document, when used as the **sole context**, produces correct answers to targeted questions. Method: fresh LLM session, document text only, no additional context. Pass = correct answer derivable from document alone.

All tests run using `utils/injection_tester.py`.

---

## Test 1 — `claude-code-memory.md`

**Date:** 2026-04-13  
**Document injected:** `kb/architecture/claude-code-memory.md` (full text, 375 words)  
**Test question:** "Describe how Claude Code persists knowledge across sessions and explain what the autoDream task does."  
**Expected answer elements:**
- Three-layer memory: project CLAUDE.md (root), user ~/.claude/CLAUDE.md, extracted/session memory
- autoDream / DreamTask runs as a background process
- DreamTask consolidates patterns from recent interactions into durable memory
- Process is automatic — no user intervention required

**Observed answer (from injection test):**
> Claude Code uses a three-layer file-based memory system. Layer 1 is project memory via CLAUDE.md at the project root, loaded at startup with project-specific conventions. Layer 2 is user memory at ~/.claude/CLAUDE.md for cross-project preferences. Layer 3 includes extractMemories (auto-extracts facts from conversations), SessionMemory (maintains within-session state), and teamMemorySync. The autoDream consolidation runs as a background DreamTask that converts ephemeral session observations into structured durable memory — analogous to sleep consolidating learning — without user intervention.

**Result:** ✅ PASS — All expected elements present. Cross-session persistence and autoDream mechanism correctly described from document alone.

---

## Test 2 — `openai-data-agent-context.md`

**Date:** 2026-04-13  
**Document injected:** `kb/architecture/openai-data-agent-context.md` (full text, 361 words)  
**Test question:** "What is Layer 4 in OpenAI's data agent context architecture, and where does it source its information?"  
**Expected answer elements:**
- Layer 4 is Institutional Knowledge
- Sources: Slack, Google Docs, Notion
- Captures business term definitions, metric ownership, team conventions

**Observed answer (from injection test):**
> Layer 4 is Institutional Knowledge. It is sourced by mining internal communication and documentation tools — specifically Slack, Google Docs, and Notion. This layer captures information that does not appear in schema metadata: business term definitions (what "revenue" means in this organisation's context), which team owns which metrics, and team conventions for query patterns.

**Result:** ✅ PASS — Layer identity, source systems, and content type all correctly identified from document alone.

---

## Test 3 — `mcp-toolbox-patterns.md`

**Date:** 2026-04-15  
**Document injected:** `kb/architecture/mcp-toolbox-patterns.md` (full text, 398 words)  
**Test question:** "What HTTP endpoint does the Oracle Forge MCP server expose for tool calls, and what happens to database queries if the MCP server is unavailable?"  
**Expected answer elements:**
- Tool call endpoint: POST http://127.0.0.1:5000/mcp (JSON-RPC 2.0)
- Health check: GET http://127.0.0.1:5000/health
- Fallback to direct Python drivers: pymongo, duckdb, psycopg2, sqlite3
- Agent probes MCP availability once at startup via tools/list call

**Observed answer (from injection test):**
> The Oracle Forge MCP server exposes tool calls via POST to http://127.0.0.1:5000/mcp using JSON-RPC 2.0. A health check is available at GET /health. If the server is unavailable (connection refused or timeout), the agent falls back to direct Python database drivers: pymongo for MongoDB, duckdb for DuckDB, psycopg2 for PostgreSQL, and sqlite3 for SQLite. The availability is probed once at session startup using a tools/list call — if that fails, all database queries in that session go through direct drivers.

**Result:** ✅ PASS — Endpoint, protocol, fallback drivers, and probe mechanism all correctly identified from document alone.

---

## Summary

| Document | Test date | Result | Notes |
|----------|-----------|--------|-------|
| `claude-code-memory.md` | 2026-04-13 | ✅ PASS | All 4 expected elements present |
| `openai-data-agent-context.md` | 2026-04-13 | ✅ PASS | Layer 4 identity + sources correct |
| `mcp-toolbox-patterns.md` | 2026-04-15 | ✅ PASS | Endpoint, fallback, probe all correct |

**Architecture KB injection test coverage: 3/3 ✅**
