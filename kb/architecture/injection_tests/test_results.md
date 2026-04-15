# Architecture KB — Injection Test Results

## Test Protocol
Fresh LLM session with only the document as context. Ask a question it should answer. Grade pass/fail.

---

## Test 1: claude-code-memory.md

**Question:** "How does Claude Code persist knowledge across sessions?"

**Expected:** File-based memory hierarchy — Project CLAUDE.md at repo root loaded at startup, User ~/.claude/CLAUDE.md loaded across all projects, extractMemories for automatic fact extraction, SessionMemory for in-session state.

**Result:** PASS — LLM correctly identified all three layers and the autoDream consolidation process.

**Date:** 2026-04-15

---

## Test 2: openai-data-agent-context.md

**Question:** "What are the six context layers in OpenAI's data agent and what does each do?"

**Expected:** Layer 1 schema metadata, Layer 2 Codex enrichment (table enrichment pipeline), Layer 3 curated expert descriptions, Layer 4 institutional knowledge (Slack/Docs/Notion), Layer 5 learning memory (corrections), Layer 6 live query fallback.

**Result:** PASS — LLM enumerated all six layers with correct descriptions and noted that Layer 5 is the self-learning loop.

**Date:** 2026-04-15

---

## Test 3: mcp-toolbox-patterns.md

**Question:** "Why did the Oracle Forge team build a custom MCP server instead of using Google's genai-toolbox binary?"

**Expected:** Google's binary does not support MongoDB, DuckDB, or SQLite — three of the four database types DAB requires. The custom Python server implements the same JSON-RPC 2.0 protocol but adds support for all four DAB types.

**Result:** PASS — LLM correctly identified the three missing DB types and the protocol compatibility.

**Date:** 2026-04-15

---

## Summary
- **Total tests:** 3
- **Passed:** 3
- **Failed:** 0
