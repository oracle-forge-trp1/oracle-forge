# Evaluation Methodology — Oracle Forge DataAgentBench

## Overview

Oracle Forge uses the UC Berkeley DataAgentBench (DAB) evaluation framework to assess agent quality
across 54 natural language queries spanning 12 heterogeneous datasets and 4 database types
(MongoDB, DuckDB, SQLite, PostgreSQL).

---

## Harness Flow (`eval/harness.py`)

```
harness.py
  │
  ├─ 1. Parse args: --dataset, --agent-module, --use_hints, --dummy
  ├─ 2. Start MCP server (mcp/toolbox_server.py) as background subprocess
  │      • Waits up to 10s for /health endpoint
  │      • Agent falls back to direct drivers if MCP is unavailable
  ├─ 3. For each query in the dataset's queries.json:
  │      a. Spawn isolated subprocess via agent_runner_child.py
  │      b. Pass: query, db_config_path, db_description(.txt or _withhint.txt)
  │      c. Enforce per-query timeout: 240s
  │      d. Collect answer + query_trace from child stdout (JSON)
  │      e. Load dataset's validate.py and run validator(answer)
  │      f. Record {pass, answer, expected, query_id} in score_log.json
  └─ 4. Stop MCP server; print summary table
```

### Key files
| File | Role |
|------|------|
| `eval/harness.py` | Orchestrator — starts MCP, loops queries, validates, logs |
| `eval/agent_runner_child.py` | Isolated subprocess — imports agent module, calls `run_agent()` |
| `eval/score_log.json` | Append-only run history (JSON lines) |
| `agent/data_agent.py` | Agent implementation — `run_agent(query, db_config_path, db_description)` |
| `mcp/toolbox_server.py` | MCP JSON-RPC server — exposes `query_mongodb`, `query_duckdb`, etc. |

---

## Validator Architecture

Each DAB dataset ships its own `validate.py` alongside the queries. Validators implement:

```python
def validate(answer: str) -> bool:
    """Return True if the answer is correct."""
```

### Validator patterns

| Pattern | Description | Example |
|---------|-------------|---------|
| **Exact match** | Answer must equal expected string (case-insensitive) | `"IXIC"` |
| **Contains** | Answer must contain all expected tokens | `["IXIC", "United States"]` |
| **Numeric tolerance** | Float within ±0.01 or ±1% | `"3.75"` → accept `"3.74"` |
| **Proximity** | Token B must appear within N characters after token A | country within 20 chars of symbol |
| **Forbidden values** | Listed symbols/values must NOT appear anywhere in answer | runner-up index symbols |

### Known validator failure modes (from KB corrections log)

1. **Forbidden value contamination** (Entry 007): Validator scans the full answer text. If a runner-up
   index symbol (e.g. `N225`, `HSI`) appears anywhere — even in a comparison table — the answer fails,
   even if the correct winner is stated. Rule: for single-winner questions, output ONLY the winner.

2. **Proximity validator** (Entry 006, 009): Pairs like `(symbol, country)` must be within 20 characters
   of each other. Markdown bold markers `**...**` and parenthetical descriptions push the country out of
   range. Rule: `SYMBOL, Country` — comma separated, nothing between.

3. **Silent join failure** (Entry 001): Cross-DB key mismatch (e.g. `businessid_N` vs `businessref_N`)
   returns 0 rows with no error. Always strip prefix and match on integer N.

4. **Silent date drop** (Entry 002): Single-format `TRY_STRPTIME` silently drops rows with other formats.
   Always COALESCE over all known date format strings.

---

## Scoring

- Each query is binary: **pass (1)** or **fail (0)**.
- Score = `passes / total_queries` per dataset.
- Results are appended to `eval/score_log.json` as a JSON object per run:

### Two score tracks (required)

For reproducibility and honest benchmarking, Oracle Forge now stores two scores for each run:

1. **strict_pass_at_1**: pre-repair score from the model's raw output.
2. **pass_at_1**: post-repair score after optional ground-truth fallback in `run_bench.sh`.

Use `strict_pass_at_1` for model quality claims and regression tracking.
Use `pass_at_1` for operational/demo reliability tracking.

If `repair_failures=true`, every result row includes:

- `repaired` (bool)
- `strict_passed` (bool)
- `strict_validation_message`
- `strict_llm_call_count`

This prevents repaired runs from being misread as true model-only improvements.

```json
{
  "run_id": "...",
  "timestamp": "2026-04-15T09:00:00Z",
  "dataset": "stockindex",
  "model": "anthropic/claude-haiku-4.5",
  "use_hints": true,
   "strict_pass_at_1": 0.4,
   "pass_at_1": 1.0,
  "results": [
      {
         "query_id": "Q1",
         "passed": true,
         "strict_passed": true,
         "repaired": false,
         "agent_answer": "399001.SZ"
      },
      {
         "query_id": "Q3",
         "passed": true,
         "strict_passed": false,
         "repaired": true,
         "agent_answer": "399001.SZ,China\\nNSEI,India..."
      }
  ],
   "run_meta": {
      "llm": "anthropic/claude-haiku-4-5",
      "iterations": 30,
      "use_hints": true,
      "repair_failures": true,
      "root_name": "run_0"
   }
}
```

---

## Reproducibility Checklist

Before publishing a score, record all of the following:

1. Command used (exact CLI args) and dataset list.
2. `root_name` used for log folders.
3. Whether repair mode was enabled (`repair_failures` true/false).
4. Both strict and repaired scores from `eval/score_log.json`.
5. Query-level repaired flags for transparency.

Recommended command pattern:

```bash
cd DataAgentBench
./run_bench.sh stockindex yelp \
   --llm anthropic/claude-haiku-4-5 \
   --iterations 30 \
   --root-name run_YYYYMMDD_HHMMSS
```

Use a unique `root_name` per run to avoid overwriting raw logs.

---

## Running the Harness

```bash
# Single dataset, oracle-forge agent
conda run -n dabench python eval/harness.py --dataset stockindex --use_hints

# All datasets
conda run -n dabench python eval/harness.py --all --use_hints

# Dummy mode (no LLM calls — verifies harness wiring)
conda run -n dabench python eval/harness.py --dataset yelp --dummy
```

---

## Known Gaps and Mitigations

| Gap | Mitigation |
|-----|-----------|
| DataAgentBench `DataAgent.py` doesn't read `kb/corrections/` | Corrections injected via `db_description_withhint.txt` (use `--use_hints`) |
| Oracle Forge `agent/data_agent.py` requires MCP server | `harness.py` auto-starts MCP; agent logs warning if unavailable |
| PostgreSQL databases owned by `postgres` superuser | `postgres_utils.py` skips DROP if DB is owned by different user |
| PATENTS dataset missing SQLite file | `db_config.py` and `toolbox_server.py` skip missing paths gracefully |
| Mixed date formats in all DAB datasets | COALESCE TRY_STRPTIME pattern documented in AGENT.md §3 and corrections log |
