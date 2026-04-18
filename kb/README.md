# kb/

LLM knowledge base (Karpathy-style): **architecture**, **domain**, **evaluation**, **corrections**.

Each subdirectory has a `CHANGELOG.md` for rubric traceability.

| Subdir | Version | Content |
|--------|---------|---------|
| `architecture/` | KB v1 | Claude Code memory / OpenAI data-agent context patterns; injection test notes. |
| `domain/` | KB v2 | DAB schemas, query patterns, join keys, domain terms, per-dataset leakage-safe notes. |
| `evaluation/` | — | Benchmark methodology, failure-mode taxonomy. |
| `corrections/` | KB v3 | `corrections-log.md` — procedural failure → fix entries (no benchmark answer keys). |

Injection / integrity:

```bash
python scripts/lint_kb_no_leakage.py --strict
python scripts/check_kb_integrity.py --strict
python scripts/verify_agent_context.py --strict
```
