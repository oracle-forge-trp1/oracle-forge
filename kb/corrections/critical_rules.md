# KB — Critical Rules (Always-Present Layer)

This file is loaded with a guaranteed budget **before** the extended corrections log.
It contains the self-correction index and the 16 highest-priority rules.
Full entry archive: `kb/corrections/corrections-log.md`.

---

## Self-Correction Index

When a query fails or stalls, find your symptom and jump to the referenced entry below.

| Symptom | Entry |
|---------|-------|
| Cross-DB join returns zero rows | **001** |
| Date/time filter drops too many rows | **002** |
| Numeric comparison wrong on string data | **004** |
| Final average biased high or low | **006** |
| Correct answer but validator fails | **007**, **034** |
| Top-N list incomplete or wrong order | **009** |
| MongoDB find returns wrong max/min | **016** |
| SQL JOIN across different DB engines fails | **017** |
| Tool error: "Unknown db_name …" | **018** |
| PostgreSQL: `column "x" does not exist` | **025** |
| DuckDB: `Binder Error` / `Catalog Error` | **028** |
| Estimating counts from sample rows | **029** |
| Answer has narrative prose; validator misses value | **034** |
| Different runs return different winners | **036** |
| Agent abstains despite non-empty tool results | **046** |
| Final answer is None / null / N/A | **047** |
| `query_postgres()` / `query_duckdb()` called inside another engine's SQL | **048** |
| Column "x" does not exist — schema assumed not discovered | **049** |

---

## Entry 001 — Cross-DB Key Normalization

- confidence: high
- datasets_seen: yelp, bookreview, crmarenapro

**When:** Cross-database joins return zero rows despite related entities existing.
**Why:** Equivalent IDs use different string prefixes across systems.
**Fix:** Normalize both IDs to a canonical key (extract numeric suffix) before joining. Validate join cardinality after normalization — confirm at least one joined row exists before final aggregation.

---

## Entry 002 — Mixed Datetime Formats

- confidence: high
- datasets_seen: yelp, stockindex, stockmarket

**When:** Time-filtered counts or aggregates are unexpectedly low.
**Why:** Single-format datetime parsing silently drops rows with alternative formats.
**Fix:** Use `COALESCE` over multiple `TRY_STRPTIME` patterns. For year-only filters, regex extraction is the safest fallback. Compare parsed row count vs total non-null date rows to detect silent loss.

---

## Entry 004 — String-Typed Numeric/Boolean Fields

- confidence: high
- datasets_seen: yelp, crmarenapro

**When:** Numeric comparisons or boolean logic behave incorrectly.
**Why:** Source values are stored as strings even when semantically numeric or boolean.
**Fix:** Cast numeric strings before arithmetic. Normalize boolean-like values (`"1"`, `"0"`, `"true"`, `"false"`) before filtering.

---

## Entry 006 — Avoid Average-of-Averages

- confidence: high
- datasets_seen: yelp, stockmarket, bookreview

**When:** Final averages seem biased high or low.
**Why:** Averaging per-group averages instead of row-level observations produces a weighted distortion.
**Fix:** Aggregate directly over row-level measurements when equal weight per row is required (e.g. `AVG(rating)` over all review rows, not `AVG` of per-business averages).

---

## Entry 007 — Output Formatting Compatibility

- confidence: high
- datasets_seen: stockindex, yelp, bookreview

**When:** Semantically correct answer fails validation.
**Why:** Extra formatting, preamble text, or non-standard separators break validator parser assumptions.
**Fix:** Return compact plain text only. Keep paired values adjacent with minimal separators. No markdown, no bullet points, no reasoning text in the final answer string.

---

## Entry 009 — Top-N Aggregation Completeness

- confidence: high
- datasets_seen: yelp, github_repos, music_brainz_20k

**When:** Top categories or entities are incomplete or misordered.
**Why:** Aggregation was performed over a truncated intermediate subset.
**Fix:** Aggregate over the full eligible population before ranking. Apply `LIMIT N` only at the final ranking stage, never on intermediate subsets.

---

## Entry 016 — MongoDB Extrema Must Use Aggregation

- confidence: high
- datasets_seen: agnews, yelp, googlelocal

**When:** "largest / smallest / longest / shortest / max / min" questions fail or vary run-to-run.
**Why:** `find` returns only the first 500 docs — the true extremum may not be in that sample.
**Fix:** Use `query_mongodb` with `query_type='aggregate'`: `$match` eligible subset → `$project` a deterministic key (e.g. `$strLenCP` for length) → `$sort` desc/asc → `$limit: 1`. Confirm pipeline returns exactly 1 row with non-null projected key.

---

## Entry 017 — Cross-DB Joins: Compute Locally, Don't Fake SQL

- confidence: high
- datasets_seen: bookreview, deps_dev_v1, crmarenapro

**When:** SQL JOIN across different physical DB engines yields "relation does not exist" or empty results.
**Why:** Cross-database SQL joins are not supported — each engine only sees its own tables.
**Fix:** Query each DB separately for the minimal required fields. Normalize join keys (often by numeric suffix extraction). Merge in application layer. Log matched/unmatched join counts before final aggregation.

---

## Entry 018 — Tool `db_name` vs SQL Table Name

- confidence: high
- datasets_seen: deps_dev_v1, stockmarket, github_repos

**When:** Tool error: "Unknown DuckDB db_name …" or query hits the wrong file.
**Why:** `db_name` must be the logical connection label from `db_config.yaml`, not a table name or file stem. Tables are queried *inside* a connection.
**Fix:** Read logical names from DATABASE DESCRIPTION / `db_config.yaml`. Use `query_duckdb(db_name="<logical>", sql="SELECT … FROM <table> …")`. If tool lists "Available: [...]", pick *only* from that list.

---

## Entry 025 — PostgreSQL camelCase Columns

- confidence: high
- datasets_seen: patents, pancancer_atlas, crmarenapro

**When:** PostgreSQL error: `column "foo" does not exist` with HINT referencing a mixed-case name.
**Why:** Unquoted identifiers are folded to lowercase by the PostgreSQL parser.
**Fix:** Always double-quote mixed-case column names: `"titleFull"`, `"ParticipantBarcode"`, `"StageName"`, `"OwnerId"`.

---

## Entry 028 — DuckDB Binder/Catalog Errors: Schema-First

- confidence: high
- last_verified_run_id: 2026-04-18-001
- datasets_seen: deps_dev_v1, github_repos

**When:** `Binder Error: Referenced column … not found` or `Catalog Error: Table with name … does not exist`.
**Why:** Query guessed table/column names, or used the wrong `db_name` for a table that lives in a different engine.
**Fix:** Immediately run schema discovery: `SHOW TABLES;` then `DESCRIBE <table>;` (or `information_schema.columns`). Copy identifiers exactly. Treat "Candidate bindings" in the binder error as the authoritative column list. If table expected in SQLite errors in DuckDB, check `db_name`.

---

## Entry 029 — Never Estimate From Tool Previews

- confidence: high
- last_verified_run_id: 2026-04-18-005
- datasets_seen: agnews, github_repos, yelp, stockmarket

**When:** Computing counts, ratios, or averages — tempted to use the visible rows as the population.
**Why:** Tool results are capped (500 rows max); using the preview as the population yields biased results.
**Fix:** Design queries that compute answers in-database using `COUNT(*)`, `SUM(...)`, `AVG(...)`, `GROUP BY`, `ORDER BY … LIMIT` over the full eligible population. Never emit "approximately" or any extrapolated value.

---

## Entry 034 — Final Answer Must Be Compact (supersedes Entry 037)

- confidence: high
- last_verified_run_id: 2026-04-18-005
- datasets_seen: all datasets

**When:** Validator misses the correct value because it is wrapped in reasoning prose, policy text, or "I cannot determine" caveats.
**Why:** Model emits chain-of-thought style output instead of the expected compact answer shape.
**Fix:** Final answer contains *only* the required payload: single numeric value, single entity/token, or compact list in requested format. Strip analysis paragraphs, methodology notes, caveats about truncation, and meta-commentary. One compact line.

---

## Entry 036 — Deterministic Ordering Before LIMIT

- confidence: high
- last_verified_run_id: 2026-04-18-012
- datasets_seen: yelp, stockindex, stockmarket, github_repos

**When:** Different runs return different winners or top lists with the same model and data.
**Why:** `LIMIT` without a stable tie-breaker allows ties to resolve non-deterministically.
**Fix:** Every ranked query must use: primary metric `DESC`/`ASC` as required, *then* a stable secondary key (entity id or name `ASC`) to break ties, *before* `LIMIT`.

---

## Entry 046 — Avoid Premature Abstention

- confidence: high
- last_verified_run_id: 2026-04-18-012
- datasets_seen: patents, pancancer_atlas, yelp, crmarenapro

**When:** Final answer is a refusal (`No answer possible`, `cannot complete`, `insufficient data`) despite non-empty tool results in trace.
**Why:** Agent treats one failed subquery as terminal and ignores usable evidence from other successful calls.
**Fix:** Only abstain when *all* relevant evidence paths are empty or unavailable. If any successful evidence rows exist for the required fields, synthesize the best compact answer from those rows.

---

## Entry 047 — No Placeholder Outputs

- confidence: high
- last_verified_run_id: 2026-04-18-012
- datasets_seen: crmarenapro, yelp, patents, pancancer_atlas

**When:** Final answer is `None`, `null`, `N/A`, or similar placeholder when validator expects a concrete entity or value.
**Why:** Early termination or fallback formatting emits placeholders instead of selecting from available evidence.
**Fix:** Treat placeholders as invalid final output when the prompt requires concrete payload. If evidence rows exist, compact-synthesize a concrete answer from selected rows.
