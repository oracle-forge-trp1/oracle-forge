# Evaluation Score Log

Tracks harness score progression from first run to final benchmark submission.
Minimum two data points required.

## Score Entry Template:

**Date:** YYYY-MM-DD
**Run #:** 1
**Queries tested:** X / 54
**Pass@1:** X%
**DB types covered:** [ ] PostgreSQL [ ] SQLite [ ] MongoDB [ ] DuckDB
**Notes:**
[what changed since the last run]

---

## Run #1 — Baseline (dummy agent)

**Date:** 2026-04-13
**Run #:** 1
**Queries tested:** 7 / 54 (Yelp dataset)
**Pass@1:** 0.0% (0/7)
**DB types covered:** [ ] PostgreSQL [ ] SQLite [x] MongoDB [x] DuckDB
**Agent:** dummy (stub returning "No answer")
**Notes:**
First harness run. Establishes baseline infrastructure — dummy agent confirms
that all 7 Yelp query files are discoverable, all 7 validate.py files load
correctly, and the harness writes to eval/score_log.json. Zero passes expected
since dummy agent returns "No answer" for every query. Real agent runs pending
OpenRouter credit top-up.

---

## Run #2 — Real agent (partial, 3/7 queries)

**Date:** 2026-04-13
**Run #:** 2
**Queries tested:** 3 / 7 (Yelp dataset — credit limit hit at Q4)
**Pass@1:** 66.7% (2/3 completed queries passed; Q4–Q7 blocked by credit limit)
**DB types covered:** [ ] PostgreSQL [ ] SQLite [x] MongoDB [x] DuckDB
**Agent:** agent.data_agent (ReAct, claude-haiku-4.5, temperature=0)
**Notes:**
Q1 (Indianapolis avg rating): PASS — returned 3.55 ✓ (GT: 3.547)
Q2 (highest review state + avg): FAIL — returned PA, 3.65 (GT: PA, 3.70)
  → Root cause: location regex missed 2/27 PA businesses; fixed in same session
Q3 (parking/bike 2018): PASS — returned 35 ✓ (GT: 35)
Q4–Q7: blocked by OpenRouter weekly credit limit (403).
Correction 4 (location regex fix) committed but not yet re-verified via agent.

---
