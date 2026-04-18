# Known Query Patterns

## Pattern 1: Cross-Database Join (Application-Layer Merge)
Most DAB queries require data from two different database types. You CANNOT SQL JOIN across databases — merge in Python.

```
Step 1: Identify which databases contain the needed data
Step 2: Query each database independently
Step 3: Pull results into Python dicts/lists
Step 4: Normalize join keys (strip prefixes, trim whitespace, cast types)
Step 5: Merge in application layer (dict lookup or pandas merge)
Step 6: Apply final aggregation/filtering on merged result
```

**Example (yelp):** "Average rating for businesses with >100 check-ins"
- Query 1 (MongoDB): Get business_ids from checkin collection, count timestamps per business
- Query 2 (DuckDB): Get average rating from review table grouped by business_ref
- Normalize: `businessid_X` → `X`, `businessref_X` → `X`
- Merge: Match on normalized key, filter for >100 check-ins

## Pattern 2: MongoDB Queries
MongoDB does NOT use SQL. Use find() or aggregation pipelines.

```javascript
// Simple query
db.collection.find({ field: value }, { projection_field: 1 })

// Aggregation pipeline
db.collection.aggregate([
  { $match: { field: value } },
  { $group: { _id: "$group_field", total: { $sum: "$amount" } } },
  { $sort: { total: -1 } },
  { $limit: 10 }
])

// Unwind nested arrays
db.collection.aggregate([
  { $unwind: "$nested_array" },
  { $group: { _id: "$nested_array.key", count: { $sum: 1 } } }
])
```

**Common mistake:** Sending SQL syntax to MongoDB → immediate failure.
**DAB datasets with MongoDB:** agnews (articles), yelp (business, checkin).

## Pattern 3: DuckDB Analytical SQL
DuckDB supports advanced analytical SQL beyond standard PostgreSQL.

**Reserved names as columns:** If a table has a column literally named `FILTER` (common in mutation VCF-style data), compare with quotes: `"FILTER" = 'PASS'`.

```sql
-- Window functions for running totals
SELECT ticker, date,
       SUM(volume) OVER (PARTITION BY ticker ORDER BY date
                         ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as week_volume
FROM stock_trade;

-- PIVOT for cross-tabulation (DuckDB-specific)
PIVOT sales ON country USING SUM(revenue_usd) GROUP BY track_id;

-- List aggregation
SELECT track_id, LIST(DISTINCT country) as countries
FROM sales GROUP BY track_id;

-- Efficient CSV/Parquet reading (if needed)
SELECT * FROM read_csv_auto('file.csv');
```

**DAB datasets with DuckDB:** crmarenapro, deps_dev_v1, github_repos, music_brainz_20k, pancancer_atlas, stockindex, stockmarket, yelp.

## Pattern 4: PostgreSQL Queries
Standard SQL with PostgreSQL-specific features.

**Mixed-case / camelCase columns:** PostgreSQL lowercases unquoted identifiers. If a column was created as `titleFull`, `titlePart`, or `childGroups`, you **must** quote it in SQL:

```sql
SELECT symbol, "titleFull", "titlePart" FROM cpc_definition WHERE level = 4;
```

```sql
-- ILIKE for case-insensitive text search
WHERE description ILIKE '%keyword%'

-- JSON/JSONB field access (if present)
SELECT attributes->>'WiFi' FROM business;

-- Date arithmetic
WHERE order_date >= NOW() - INTERVAL '90 days'

-- Array operations (if arrays present)
WHERE 'value' = ANY(array_column)
```

**DAB datasets with PostgreSQL:** bookreview, crmarenapro, googlelocal, pancancer_atlas, patents.

## Pattern 5: SQLite Queries
Standard SQL with SQLite-specific limitations.

```sql
-- Case-insensitive search (no ILIKE in SQLite)
WHERE description LIKE '%keyword%' -- LIKE is case-insensitive for ASCII in SQLite

-- Date arithmetic (no INTERVAL in SQLite)
WHERE order_date >= date('now', '-90 days')

-- String operations
WHERE SUBSTR(ticker, 1, 3) = 'AAP'

-- No window functions in older SQLite — check version
```

**DAB datasets with SQLite:** agnews, bookreview, crmarenapro, deps_dev_v1, github_repos, googlelocal, music_brainz_20k, patents, stockindex, stockmarket.

## Pattern 6: CRM ID Corruption Handling (crmarenapro)
Before ANY query on crmarenapro, preprocess IDs.

```sql
-- In SQL: strip leading # from IDs
SELECT REPLACE(LTRIM(Id, '#'), '#', '') as clean_id FROM table;

-- In Python after pulling results
clean_id = raw_id.strip().lstrip('#')
clean_name = raw_name.strip()  -- remove trailing whitespace
```

**Always apply to:** Id, AccountId, ContactId, Name, Email, Subject, Status fields.

## Pattern 7: Hierarchical Lookup (patents)
CPC codes are hierarchical — queries may ask for patents in a category at any level.

```sql
-- Find all patents in a CPC section
SELECT * FROM publicationinfo WHERE cpc LIKE 'H04%';

-- Join with CPC definitions for human-readable names
SELECT p.*, c.definition
FROM publicationinfo p
JOIN cpc_definition c ON p.cpc = c.code;

-- Parent category lookup
SELECT * FROM cpc_definition WHERE code IN ('H', 'H04', 'H04L');
```

## Pattern 8: Text Field Extraction
For queries requiring structured answers from free-text fields.

```
1. IDENTIFY: Which text field(s) does the query need?
2. CLASSIFY: What extraction type?
   - Simple: SQL LIKE/ILIKE/regex
   - Medium: Python regex on pulled data
   - Complex: LLM classification on pulled data
3. EXTRACT: Apply the appropriate method
4. STRUCTURE: Convert to structured column/value
5. QUERY: Use structured result in final aggregation
```

**Example (bookreview):** "How many reviews mention 'disappointing ending'?"
```sql
-- Simple approach
SELECT COUNT(*) FROM review WHERE text LIKE '%disappointing%ending%';
```

## Pattern 9: Null Handling
Always account for NULLs — they cause silent wrong answers.

```sql
-- Wrong: misses NULL values
SELECT COUNT(*) FROM table WHERE status != 'active'

-- Correct: explicitly handles NULLs
SELECT COUNT(*) FROM table WHERE status != 'active' OR status IS NULL

-- Count NULLs explicitly when relevant
SELECT COUNT(*) - COUNT(column) as null_count FROM table;
```

## Pattern 10: Large Table Queries (stockmarket)
stockmarket has 2,754 securities with daily price data — potentially millions of rows.

```sql
-- Always filter early
SELECT * FROM stock_trade WHERE ticker = 'AAPL' AND date >= '2023-01-01';

-- Use DuckDB's columnar storage efficiently
SELECT ticker, AVG(close) FROM stock_trade
WHERE date BETWEEN '2023-01-01' AND '2023-12-31'
GROUP BY ticker;

-- Avoid SELECT * on large tables
```

## Pattern 11: Deterministic Top-N Ranking
Ranking outputs can drift across runs when ties are unresolved.

```sql
-- Prefer deterministic ordering with tie-breakers
ORDER BY metric DESC, entity_id ASC
```

Use stable tie-breakers before LIMIT to avoid non-deterministic winners.

## Pattern 12: Pagination Under Result Caps
Tool responses are capped for context safety. Design queries to avoid silent truncation bias.

```sql
-- Prefer bounded projections and iterative windows
SELECT id, metric
FROM big_table
WHERE <filters>
ORDER BY id
LIMIT 500 OFFSET 0;
```

When full coverage is required, iterate over pages and aggregate in application layer.

## Pattern 13: Join Cardinality Audit
Cross-DB joins should include a cardinality check before final aggregation.

```
1. Count left-side keys
2. Count right-side keys
3. Count matched keys after normalization
4. If match rate is unexpectedly low, diagnose key format/type mismatch
```

This prevents silent zero/low-match failures.

## Pattern 14: Runtime Health-Gated Execution
Before expensive multi-step plans, run a quick health query per required tool/database.

```
1. Probe tool availability
2. Execute a lightweight COUNT or LIMIT 1 query
3. Abort early with explicit trace note on connectivity/auth failures
```

This reduces wasted iterations under MCP/API instability.

## Pattern 15: Final Answer Contract Checks
Before returning final text, enforce query-intent-specific output contracts.

```
1. Infer expected output type (single id, label, list, numeric, pair)
2. Run format checks for that type
3. If check fails, revise final response once before return
```

Typical checks:
- Identifier queries: at least one ID token present
- Single-winner queries: one entity only
- Pair queries: required values adjacent
- Numeric queries: one canonical numeric token

## Pattern 16: Evidence-Decision Consistency Guard
Classification and policy answers should not contradict extracted evidence.

```
if evidence_count > 0 and decision == "no_violation":
  decision = "violation"
```

General rule: final decision must be mechanically consistent with evidence table outputs.

## Pattern 17: Exhaustive List Rendering
When validator expects complete sets/lists, avoid partial outputs.

```
1. Build full eligible set
2. Deduplicate
3. Deterministically sort
4. Render all required items in compact format
```

Do not finalize from sampled intermediate rows.

## Pattern 18: Precision-Then-Round Numeric Output
Maintain precision through computation and round only at render time.

```
value = compute_full_precision()
final = round(value, required_decimals)
```

Emit one canonical numeric value in the final answer to reduce parser ambiguity.

## Pattern 19: Taxonomy-Constrained Labels
For stage/category/class outputs, emit canonical labels only from allowed set.

```
if predicted_label not in allowed_labels:
  predicted_label = map_to_nearest_allowed(predicted_label)
```

Avoid free-form synonyms in final output when strict validators are used.

## Pattern 20: Compute/Render Date Separation
Date parsing for computation and date wording for output should be separate steps.

```
dt = parse_any_supported_format(raw_date)
render = format_required_token(dt)  # e.g., month-name token
```

This prevents correct computation with validator-incompatible final text.

## Pattern 21: Two-stage rank-then-restrict
Many prompts implicitly chain two objectives: (A) find the group or entity that **maximizes a count or coverage**, then (B) compute a **different statistic** for that winner only.

```
1. On the full eligible population, compute the ranking metric for each group (state, category bucket, etc.).
2. Identify the single winning group (break ties with a stable secondary key).
3. Restrict all data for step (B) to rows/documents belonging to that winning group only.
4. Emit the step (B) result — do not mix in global aggregates.
```

Skipping step 3 is a common source of plausible but wrong numeric answers.

## Pattern 22: Schema-first recovery from DuckDB binder/catalog errors
When a DuckDB query fails with `Binder Error` or `Catalog Error`, stop guessing and do schema discovery.

```sql
-- Discover tables
SHOW TABLES;

-- Inspect columns (copy identifiers exactly; quote mixed-case names)
DESCRIBE some_table;

-- Alternative: list columns via information_schema
SELECT table_name, column_name
FROM information_schema.columns
WHERE table_schema = 'main'
ORDER BY table_name, ordinal_position;
```

Rules:
- Treat “Candidate bindings” in binder errors as the authoritative list of usable columns.
- If the table should be in SQLite but fails in DuckDB, you’re in the wrong `db_name` (engine mismatch).

## Pattern 23: Exact metrics only (never extrapolate from capped previews)
Tool outputs may be capped; never compute “approximate” answers from partial previews.

```
If validator expects an exact value:
  - compute it with COUNT/SUM/AVG over the full eligible set, or
  - materialize the full eligible ID set, classify all of it, then count exactly.
Never:
  - “sample 80 rows”, “assume representative”, “estimate from preview”.
```

## Pattern 24: Engine mismatch detection (SQLite vs DuckDB vs Postgres vs Mongo)
Many failures are simply the right SQL sent to the wrong engine/database.

Heuristic:
- If you see `Binder Error` / `Catalog Error` → DuckDB.
- If you see `no such table` / `near "ILIKE"` → SQLite.
- If you see `permission denied` / `relation ... does not exist` → PostgreSQL.
- If you see JSON parsing / pipeline operator errors → MongoDB.

Correction:
- Re-check the dataset’s DATABASE DESCRIPTION for the correct logical `db_name`.
- Run a tiny sanity query (`SELECT 1`, `SHOW TABLES`, `LIMIT 1`) before the full query.

## Pattern 25: Final output should be value-first, not explanation-first
Many strict validator misses come from verbose narrative responses.

```
Before return_answer:
1. Identify expected shape: scalar | token | list | pair.
2. Keep only the final payload in output text.
3. Remove analysis, caveats, and "based on sample" commentary.
```

If uncertainty remains, still return the best evidence-backed compact value instead of a long refusal paragraph.

## Pattern 26: Exact token copy for labels/codes
For entity names, taxonomy labels, repo paths, CPC/histology codes, and IDs, token fidelity matters.

```
1. Select winner rows via SQL/aggregation.
2. Render output tokens by direct copy from selected row fields.
3. Do not normalize punctuation/case/pluralization in final render.
```
