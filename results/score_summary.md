# Score Summary — Oracle Forge DataAgentBench

## Source Of Truth

All numbers below are computed directly from `eval/score_log.json`.

## Terminology Alignment (with `results/run_reports/`)

- **Final pass@1 (post-repair)** in run reports corresponds to the `passed/total_queries` and `pass_at_1` fields in `eval/score_log.json`.
- **Strict pass@1 (pre-repair)** and **Repaired queries** are reported per run-report file, but are not consistently materialized as dataset-level aggregates in `score_log.json` for this summary.
- This file therefore reports **latest** and **best-historical** views using score-log fields only, while preserving the same metric label wording.

## Latest Snapshot (Most Recent Run Per Dataset)

| Dataset | Run ID | Date | Final pass@1 (post-repair) | Failed |
|---|---|---|---:|---:|
| yelp | `2026-04-16-001` | 2026-04-16 | 5/7 (0.7143) | 2/7 |
| stockindex | `2026-04-16-002` | 2026-04-16 | 2/3 (0.6667) | 1/3 |
| bookreview | `2026-04-16-003` | 2026-04-16 | 1/3 (0.3333) | 2/3 |

Combined latest: **8/13 passed, 5/13 failed, combined pass@1 = 0.6154**.


## Data Notes

- `eval/score_log.json` currently contains duplicate entries for run IDs `2026-04-15-016`, `2026-04-15-017`, and `2026-04-15-018`.
- This summary de-duplicates by `(dataset, run_id)` when reporting best-historical and latest snapshots.

## Verification Artifacts

- Structured score log: `eval/score_log.json`
- Auto-generated run reports: `results/run_reports/`
- Agent correction ledger: `kb/corrections/corrections-log.md`
- Probe evidence: `probes/probes.md`
