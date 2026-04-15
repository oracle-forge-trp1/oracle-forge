# Score Summary — Oracle Forge DataAgentBench

## Current Status (2026-04-15)

- Latest completed real-data run: `2026-04-15-034` (`yelp`)
- Result: **4/7** passed (**57.14%**)
- Passing queries: Q1, Q3, Q5, Q6
- Failing queries: Q2, Q4, Q7

## Recent Yelp Run History

| Run ID | Pass@1 | Passed | Notes |
|---|---:|---:|---|
| 2026-04-15-032 | 71.43% | 5/7 | Best current Yelp run in this cycle |
| 2026-04-15-033 | 42.86% | 3/7 | Regression run |
| 2026-04-15-034 | 57.14% | 4/7 | Q5 recovered; Q2/Q4/Q7 still failing |

## Failure Focus (from run 2026-04-15-034)

- Q2: review-count/avg pipeline still incorrect and output formatting remains fragile.
- Q4: winning category average still wrong (`3.48` vs expected near `3.63`).
- Q7: weighted category aggregation still misses required `Shopping`.

## Non-Yelp Datasets (Current Blocker)

- `stockindex`: attempted run on 2026-04-15 but harness pre-check aborted with OpenRouter `403` (weekly limit exhausted).
- `bookreview`: not run yet in this session for the same API-limit reason.
- OpenRouter auth snapshot at failure time showed `limit_remaining: 0`.

## Artifacts

- Full run ledger: `eval/score_log.json`
- Corrections: `kb/corrections/corrections-log.md`
- Probe tracking: `probes/probes.md`
- Generated run reports: `results/run_reports/`
