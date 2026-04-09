# KB v1 — Architecture Knowledge Base

Documents in this directory provide the agent with working knowledge of:
- Claude Code three-layer memory system
- OpenAI data agent six-layer context architecture
- MCP Toolbox tool scoping patterns

## Injection Test Protocol
Every document here must pass this test:
1. Start a fresh LLM session with ONLY the document as context
2. Ask a question the document should answer
3. If the LLM cannot answer correctly → revise or remove the document

## Documents
- [ ] claude-code-memory.md (assigned to IO-1)
- [ ] openai-data-agent-context.md (assigned to IO-1)
- [ ] mcp-toolbox-patterns.md (assigned to IO-2)
