# Score Summary — Oracle Forge DataAgentBench

## Latest Combined Run (Sprint 2)

- **Date:** 2026-04-15
- **Datasets:** stockindex (3) + yelp (7)
- **Command:** `./run_bench.sh stockindex yelp --llm anthropic/claude-haiku-4-5 --iterations 30 --root-name run_0`
- **Logged in:** `eval/score_log.json`

### Reported score (post-repair)

- **Pass@1:** 100.00% (10/10)
- **Repaired queries:** 6/10

### Strict score (pre-repair)

- **Strict pass@1:** 40.00% (4/10)
- **Strict passes:** stockindex Q1,Q2 and yelp Q3,Q6

### Why both numbers matter

- Post-repair score measures operational reliability (fallback enabled).
- Strict score measures model-only quality and is the baseline for real benchmark claims.

---

## Best Run (Sprint 1)

- **Date:** 2026-04-13
- **Run IDs:** 2026-04-13-003, 2026-04-13-004
- **Dataset:** Yelp (7 queries)
- **Pass@1:** 42.86% (3/7) — tied across 2 runs
- **Agent module:** agent.data_agent
- **Model:** anthropic/claude-haiku-4.5 via OpenRouter

### Per-Query Results (best run: 2026-04-13-004)

| Query | Question (short) | Pass | Notes |
|-------|-----------------|------|-------|
| Q1 | Avg rating — Indianapolis | ✅ | Consistent PASS (3.55) |
| Q2 | State with most reviews + avg rating | ❌ | Timeout in run-004; PASS in run-003 (PA, 3.70) |
| Q3 | 2018 businesses with parking | ✅ | Passes with COALESCE date parsing (35) |
| Q4 | Category + credit cards + avg rating | ❌ | Agent gets 3.59; correct is 3.63 |
| Q5 | WiFi state + per-state avg rating | ❌ | Agent computes global avg (3.72) not PA-only avg (3.48) |
| Q6 | Highest rated business Jan–Jun 2016 | ✅ | Consistent PASS (Coffee House Too Cafe) |
| Q7 | Top 5 categories from 2016 users | ❌ | Category extraction misses "Breakfast & Brunch" or "American (New)" |

### Run History

| Run ID | Dataset | Pass@1 | Passed | Notes |
|--------|---------|--------|--------|-------|
| 2026-04-13-003 | yelp | 42.86% | 3/7 | Q1, Q2, Q6 pass |
| 2026-04-13-004 | yelp | 42.86% | 3/7 | Q1, Q3, Q6 pass |
| 2026-04-13-005 | yelp | 28.57% | 2/7 | Q1, Q6 pass; Q2 format fail |
| 2026-04-13-006 | yelp | 14.29% | 1/7 | Token exhaustion (OpenRouter 402/403) from Q2 onward |
| 2026-04-13-007 | yelp | 0.00%  | 0/7 | Full token exhaustion — all 403 errors, not logic failures |

> **Note:** Runs 006–007 are billing failures, not logic regressions. The API key's weekly limit
> was exhausted. Sprint 1 peak logic score is 3/7 = 42.86%.

---

## Sprint 2 Target

- **Yelp target:** ≥ 71% (5/7) after fix validation
- **Additional datasets:** ≥ 1 non-Yelp dataset benchmarked (stockindex being run next)
- **Submission deadline:** April 17, 2026

---

## Notes

- `results/dab_results.json` — DAB submission artifact (preliminary Yelp answers)
- `eval/score_log.json` — full per-query harness results (all runs)
- `kb/corrections/corrections-log.md` — 9 correction entries (Entries 001–009)
