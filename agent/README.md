# agent/

Production data-agent code and session context.

| File | Role |
|------|------|
| `AGENT.md` | Loaded into the system prompt: roles, formatting rules, ReAct protocol, multi-DB patterns. |
| `data_agent.py` | OpenAI/OpenRouter client, tool dispatch (MCP + direct-driver fallback), `run_agent()`, query trace. |
| `requirements.txt` | Python dependencies (`pip install -r agent/requirements.txt`). |

Run locally (requires `.env` API keys + DBs + optional MCP):

```bash
python agent/data_agent.py --query "..." --db_config <path>/db_config.yaml --db_description <path>/db_description.txt
```
