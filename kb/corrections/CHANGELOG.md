# Changelog — kb/corrections

## 2026-04-14

- Corrections log reviewed at Sprint 2 kickoff; 9 active entries, all confirmed correct
- Log is injected into agent system prompt at session start (data_agent.py line 388–389)
- Future entries to be added as Sprint 2 probe re-runs surface new failure patterns

## 2026-04-13 — v1.0 Initial Corrections from Yelp + StockIndex Runs

- `corrections-log.md` populated with 9 entries from evaluation runs 003-009
- **Entries 001–005 (Yelp):**
  - Entry 001: Cross-DB join key mismatch (businessid_N vs businessref_N)
  - Entry 002: Mixed date format parsing (3 formats in same column)
  - Entry 003: Location extraction from description field (no city/state columns)
  - Entry 004: String-typed numeric/boolean fields in MongoDB
  - Entry 005: Comma-separated checkin dates (not single datetime)
- **Entries 006–009 (StockIndex):**
  - Entry 006: Stock index symbol + country code proximity formatting
  - Entry 007: Forbidden value contamination (single winner, no runners-up)
  - Entry 008: "Up day" domain definition (close > open, not close > previous close)
  - Entry 009: DCA vs. buy-and-hold compounding calculation
- All entries derived from real agent failures documented in eval/score_log.json
- Categories covered: ill-formatted join key, unstructured text extraction, domain knowledge gap

## 2026-04-09

- Initial directory created; corrections log format defined — [query failed] → [what was wrong] → [correct approach] per Karpathy KB method
