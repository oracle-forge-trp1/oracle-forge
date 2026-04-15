# KB v1 — Architecture Knowledge Base

Documents in this directory provide the agent with working knowledge of:

- Claude Code three-layer memory system
- OpenAI data agent six-layer context architecture
- MCP Toolbox tool scoping patterns

## Injection Test Protocol

Every document here must pass this test:

1. Start a fresh LLM session with ONLY the document as context
2. Ask a question the document should answer
3. If the LLM cannot answer correctly, revise or remove the document

## Documents

- [x] claude-code-memory.md — Three-layer memory, autoDream, context compression, tool scoping
- [x] openai-data-agent-context.md — Six-layer context, retrieval strategy, self-correction
- [x] mcp-toolbox-patterns.md — MCP Toolbox config, custom server rationale, 5 patterns

## Injection Test Results

See `injection_tests/test_results.md` — 3/3 PASS
