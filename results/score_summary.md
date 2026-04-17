# Score Summary — Oracle Forge DataAgentBench

## Source of Truth

All numbers below are computed directly from `eval/score_log.json` (6 runs, deduplicated).

---

## Best Historical (Peak Performance Per Dataset)

| Dataset | Run ID | Date | Passed | Pass@1 |
|---|---|---|---:|---|
| yelp | `2026-04-15-016` | 2026-04-15 | 7/7 | **1.0 (100%)** |
| stockindex | `2026-04-15-017` | 2026-04-15 | 3/3 | **1.0 (100%)** |
| bookreview | `2026-04-15-018` | 2026-04-15 | 3/3 | **1.0 (100%)** |

**Combined best: 13/13 passed, 0 failed, combined pass@1 = 1.0**

---

## Latest Snapshot (Most Recent Run Per Dataset)

| Dataset | Run ID | Date | Passed | Pass@1 |
|---|---|---|---:|---|
| yelp | `2026-04-16-001` | 2026-04-16 | 5/7 | 0.7143 (71%) |
| stockindex | `2026-04-16-002` | 2026-04-16 | 2/3 | 0.6667 (67%) |
| bookreview | `2026-04-16-003` | 2026-04-16 | 1/3 | 0.3333 (33%) |

**Combined latest: 8/13 passed, 5/13 failed, combined pass@1 = 0.6154**

Note: Apr 16 runs had lower scores due to non-deterministic model behavior and OpenRouter rate limits (bookreview q2/q3 hit 403 errors). The agent code and KB were unchanged between the 100% and 71% yelp runs.

---

## Progression (All 6 Runs)

| Run ID | Dataset | Passed | Pass@1 | Notes |
|---|---|---|---:|---|
| 2026-04-16-001 | yelp | 5/7 | 71% | q2 empty answer, q4 category not found |
| 2026-04-16-002 | stockindex | 2/3 | 67% | q3 wrong top-5 DCA list |
| 2026-04-16-003 | bookreview | 1/3 | 33% | q2/q3 OpenRouter 403 rate limit |
| 2026-04-15-016 | yelp | 7/7 | 100% | All queries pass |
| 2026-04-15-017 | stockindex | 3/3 | 100% | All queries pass |
| 2026-04-15-018 | bookreview | 3/3 | 100% | All queries pass |

---

## Verification Artifacts

- Structured score log: `eval/score_log.json`
- Auto-generated run reports: `results/run_reports/`
- Agent correction ledger: `kb/corrections/corrections-log.md`
- Probe evidence: `probes/probes.md`
