# Changelog — kb/evaluation

## 2026-04-15 — v1.0 Benchmark and Failure Mode Docs Added

- `dab_benchmark.md` created — DAB overview, leaderboard scores, scoring method, four hard requirements
- `dab_failure_modes.md` created — five failure modes with percentages, mapped to Yelp probes and corrections log
- Created `injection_tests/test_results.md` — 3 tests, all PASS
- Sources: DAB paper (arxiv.org/html/2603.20576), DAB leaderboard, eval/score_log.json

## 2026-04-13

- Document reviewed at Day 5 mob session; confirmed sufficient for injection as agent context
- Failure categories in §2 cross-referenced with probes/probes.md — each probe maps to one of the 4 categories
- Reproducibility checklist (§4) cross-checked against eval/harness.py — all steps confirmed accurate

## 2026-04-11

- `evaluation-methodology.md` drafted — covers: (1) harness execution flow (MCP startup, subprocess isolation, query loop, validation, score aggregation), (2) validator architecture with 4 failure categories, (3) pass@1 scoring with strict vs. repaired variants, (4) reproducibility checklist, (5) harness CLI usage, (6) known gaps and limitations

## 2026-04-09

- Initial directory created; evaluation KB scope defined — DAB query format, scoring methodology, harness schema, failure categories
