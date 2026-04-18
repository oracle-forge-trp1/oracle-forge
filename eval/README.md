# eval/

DataAgentBench evaluation harness and batch runners.

| File | Role |
|------|------|
| `harness.py` | Runs `queryN/query.json` through the agent, records **per-query tool traces**, validates with DAB `validate.py`, appends **numeric pass@1** to `score_log.json` (or `--score-log`). Adds `methodology_notes` per run for reproducibility. |
| `agent_runner_child.py` | Subprocess entrypoint (timeout isolation); forwards `MCP_URL` when set by harness. |
| `run_benchmark.py` | Batch driver for multi-trial artifacts under DAB folders. |
| `held_out_queries.json` | Defines held-out vs training query sets for reporting. |

Example:

```bash
python eval/harness.py --dataset yelp --agent-module agent.data_agent --dab-root /path/to/DataAgentBench
```

Regression / smoke tests for harness helpers live in `tests/` (pytest).
