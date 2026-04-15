# Changelog — kb/corrections

## 2026-04-09
- Initial directory created; corrections log format defined — [query failed] → [what was wrong] → [correct approach] per Karpathy KB method

## 2026-04-11
- `corrections-log.md` created with first 5 entries (Entries 001–005) covering Sprint 1 Day 3–4 failures:
  - Entry 001: Ill-formatted cross-DB join key (businessid_N ≠ businessref_N) — PASS after fix
  - Entry 002: Mixed date formats in DuckDB (three formats in one column) — PASS after COALESCE
  - Entry 003: Location extraction from unstructured MongoDB description field — PASS after regex fix
  - Entry 004: String type coercion for review_count and is_open — PASS after cast
  - Entry 005: Checkin date splitting (pipe-separated multi-date strings) — PASS after split logic

## 2026-04-12
- Entries 006–009 added from Sprint 1 evaluation runs (harness runs 003–005):
  - Entry 006: Stock index symbol + country code proximity pairing — PASS
  - Entry 007: Forbidden value contamination (query answer should not contain example values from question) — PASS
  - Entry 008: "Up day" domain definition (close > open, not close > previous close) — PASS
  - Entry 009: DCA vs. buy-and-hold compounding calculation — PASS
- Template for future entries added at bottom of log

## 2026-04-14
- Corrections log reviewed at Sprint 2 kickoff; 9 active entries, all confirmed correct
- Log is injected into agent system prompt at session start (data_agent.py line 388–389)
- Future entries to be added as Sprint 2 probe re-runs surface new failure patterns
