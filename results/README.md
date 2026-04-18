# results/

Benchmark artifacts, score summaries, and **DataAgentBench submission** outputs.

## Files

| File | Purpose |
|------|---------|
| `dab_results.json` | DAB PR submission payload (`dataset`, `query`, `run`, `answer` per row). **Committed as `[]` by default** so we do not store benchmark ground-truth answers in git. Populate after official runs. |
| `build_results_json.py` | Builds `dab_results.json` from `DataAgentBench/**/data_agent/run_*/final_agent.json` (see script `--help`). |
| `dab_pr_link.txt` | Paste the GitHub PR URL to `ucbepic/DataAgentBench` when opened. |
| `score_summary.md` / `score_summary_strict_no_leakage.md` | Human-readable pass@1 summaries (generated). |
| `run_reports/` | Optional narrative run reports. |

## No data leakage

Do not hand-edit `dab_results.json` with validator target strings. Generate from harness / `run_benchmark.py` outputs only.
