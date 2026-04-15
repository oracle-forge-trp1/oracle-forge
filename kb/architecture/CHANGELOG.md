# Changelog — kb/architecture

## 2026-04-09
- Initial directory created; architecture KB scope defined at Day 3 mob session

## 2026-04-10
- `claude-code-memory.md` drafted — covers three-layer memory system (project CLAUDE.md, user ~/.claude/CLAUDE.md, session/extracted memory), autoDream background consolidation pattern, and tool scoping philosophy (40+ tools with tight domain boundaries)
- `openai-data-agent-context.md` drafted — covers six-layer context architecture (raw schema, enriched schema, query history, institutional knowledge, user preferences, live data), Codex-powered table enrichment, and closed-loop self-correction pattern

## 2026-04-11
- Both architecture documents reviewed at Day 4 mob session
- Atnabon merged both documents into the repository
- `mcp-toolbox-patterns.md` identified as third required document; deferred to April 15 Sprint 2 work

## 2026-04-13
- Injection tests for architecture documents due; documented in kb/architecture/injection_tests/
- Day 5 mob: injection test results confirmed both documents answer their target questions correctly from context alone

## 2026-04-15
- `mcp-toolbox-patterns.md` created — covers MCP JSON-RPC 2.0 protocol, tool scoping, fallback pattern, and MAX_ROWS cap
- `injection_tests/test_results.md` created with 3 tests (2 existing docs + mcp-toolbox-patterns), all PASS
