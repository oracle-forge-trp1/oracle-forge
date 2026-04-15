# Changelog — kb/corrections

## 2026-04-09

- Initial directory created

## 2026-04-13 — v1.0 Initial Corrections from Yelp Runs

- `corrections-log.md` populated with 5 entries from evaluation runs 003-005
- Entry 001: Cross-DB join key mismatch (businessid_N vs businessref_N)
- Entry 002: Mixed date format parsing (3 formats in same column)
- Entry 003: Location extraction from description field (no city/state columns)
- Entry 004: String-typed numeric/boolean fields in MongoDB
- Entry 005: Comma-separated checkin dates (not single datetime)
- All entries derived from real agent failures documented in eval/score_log.json
- Categories covered: ill-formatted join key, unstructured text extraction, domain knowledge gap

## 2026-04-09

- Initial directory created
