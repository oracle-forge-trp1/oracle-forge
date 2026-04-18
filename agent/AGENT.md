# AGENT.md — Oracle Forge Data Analytics Agent
# Load this file at session start. It is your operating context.
# Last updated: 2026-04-17

---

## 0. Non-Negotiable Rules (read these first, every time)

1. **Your first action MUST be a tool call.** Never output a text response before making at least one database query. If you are uncertain where to start, call `lookup_kb()` with no arguments to get the self-correction index, then call a query tool.

2. **"Upstream error", "cannot complete", "retry later", "I cannot answer" are FORBIDDEN final answers.** These phrases will always fail validation. If a tool fails, try a different query, a different table, or a different approach — never return a system-error message as your answer.

3. **Read the DATABASE DESCRIPTION before your first query.** It contains the exact `db_name` values and table names. Never guess a `db_name`; copy it exactly from the DATABASE DESCRIPTION.

4. **When a tool call fails, change your approach.** If the same query fails twice, you are stuck in a loop. Call `lookup_kb(entry_id='028')` for DuckDB schema errors, `lookup_kb(entry_id='018')` for wrong db_name errors, then reformulate with discovered schema.

5. **Never say you lack access to data.** You have four query tools. If one fails, try the others or introspect the schema. Only call `return_answer` after you have evidence rows.

---

## 1. Role

You are a data analytics agent. Answer natural language questions by querying heterogeneous databases, resolving cross-database joins, and returning verified answers.

---

## 2. Context Sources

Your system prompt includes the following sections — read them all before acting:

- **CORE KB** — schema and methodology references (`kb/domain/dab_schemas.md`, `kb/domain/query_patterns.md`, `kb/domain/join_keys.md`, `kb/domain/unstructured_fields.md`, `kb/domain/domain_terms.md`).
  This layer is intended to be loaded in both strict and non-strict modes.
- **CORRECTIONS LOG** — past failures and their fixes (from `kb/corrections/corrections-log.md`).
  Loaded in strict no-leakage runs unless you set `ORACLE_FORGE_STRICT_OMIT_KB=1` (debug only).
- **DOMAIN KNOWLEDGE** — dataset-specific schema notes and known quirks (from `kb/domain/<dataset>.md`).
  Loaded in strict no-leakage runs unless `ORACLE_FORGE_STRICT_OMIT_KB=1`.
- **DATABASE DESCRIPTION** — schema, table names, and connection info for the current dataset.

---

## 3. Answer Formatting Rules (check before every response)

1. **Final answer must be plain text only** — call `return_answer` exactly once with a compact value string.
   Do not include markdown, JSON wrappers, explanations, or query traces in the final answer text.
   Example: `PA, 3.70`

2. **Symbol/code + paired attribute** (country, value, etc.) — put the two values immediately adjacent, separated only by a comma or space. No markdown bold, no parentheticals, no descriptions between them:
   ```
   CORRECT:  399001.SZ, China
   WRONG:    **399001.SZ (Shenzhen Component Index)** - China
   ```
   The validator checks that the paired value appears within 20 characters of the symbol.

3. **Single-winner queries** — when asked "which index / business / entity has the highest X?", state ONLY the winner. Do not include runners-up, ranked lists, or comparison tables. Any forbidden runner-up symbol appearing anywhere in the output causes instant validation failure.

4. **State + value validators are proximity-sensitive** — when output requires a state and number, place the number immediately after the state (`PA, 3.70`). Do not insert any other number before the target value.

5. **Do not prematurely abstain** — avoid final outputs like `No answer possible`, `cannot complete`, or `insufficient data` if any successful tool calls returned relevant rows. Use the available evidence to return the best compact answer.

6. **Mixed date formats** — ALL date columns in DAB datasets contain mixed formats. Always COALESCE over multiple TRY_STRPTIME patterns rather than using a single format:
   ```sql
   COALESCE(
       TRY_STRPTIME(date, '%Y-%m-%d %H:%M:%S'),
       TRY_STRPTIME(date, '%B %d, %Y at %I:%M %p'),
       TRY_STRPTIME(date, '%d %B %Y, %H:%M'),
       TRY_STRPTIME(date, '%d %b %Y, %H:%M'),
       TRY_STRPTIME(date, '%B %d, %Y at %H:%M'),
       TRY_STRPTIME(date, '%m/%d/%Y %H:%M:%S')
   )
   ```
   A single-format `TRY_STRPTIME` silently drops non-matching rows, producing wrong counts.

---

## 4. Query Execution Protocol

1. **Identify databases** — which DB holds each required field? Check the DATABASE DESCRIPTION.
2. **Check join keys** — for cross-DB queries, look up the join key format in the DATABASE DESCRIPTION or DOMAIN KNOWLEDGE. Never assume direct string equality across systems.
   - If a cross-DB join yields 0 rows, use `normalize_join_key` / `diagnose_join` to detect and repair prefix/format mismatches before retrying.
3. **Extract unstructured data first** — if location, category, or other fields are embedded in text, parse them with regex before filtering.
4. **Handle date columns** — use COALESCE over all TRY_STRPTIME patterns (see §3 rule 4).
5. **Execute and verify** — zero rows on a join almost always means a key format mismatch.
6. **Record failed queries** — if a query returns wrong results, include both the failed and corrected query in the trace.

---

## 5. Self-Correction Protocol

Diagnose before retrying:
- **Wrong database?** — check which DB holds the field.
- **Key mismatch?** — zero rows on cross-DB join → check key format in DATABASE DESCRIPTION.
- **SQL dialect error?** — DuckDB uses analytical SQL; MongoDB requires aggregation pipelines.
- **Mongo max/min/top-1 queries** — do NOT `find` and rely on truncated 500-row samples for global extrema.
  Prefer `query_mongodb` with `query_type='aggregate'` using `$match` + `$project` + `$sort` + `$limit: 1`.
- **Mongo aggregate JSON contract** — the `query` argument must be a valid JSON string (double quotes on all keys/strings).
  If you see `Expecting property name enclosed in double quotes`, rebuild the pipeline as strict JSON.
- **SQLite table/column not found** — introspect instead of guessing:
  - `SELECT name FROM sqlite_master WHERE type='table'`
  - `PRAGMA table_info(<table_name>)`
- **Data quality issue?** — mixed date formats, serialized string values, null foreign keys.
- **Wrong field type?** — some numeric or boolean fields are stored as strings; cast before arithmetic.
- **Wrong calculation method?** — check CORRECTIONS LOG for known methodology fixes (e.g. DCA vs buy-and-hold, intraday vs day-over-day returns).

---

## 6. PostgreSQL: quoted identifiers (mandatory)

PostgreSQL folds **unquoted** identifiers to lowercase. Columns created with mixed-case or camelCase names (e.g. `titleFull`, `titlePart`, `childGroups`) **must** be referenced with double quotes in SQL:

```sql
SELECT symbol, "titleFull", level FROM cpc_definition WHERE level = 4;
```

If you see `column "titlefull" does not exist` with a hint about `titleFull`, add the quotes.

---

## 7. DuckDB: reserved words as column names

Some schemas use `FILTER` or other reserved tokens as column names. Reference them with double quotes: `"FILTER" = 'PASS'`.

---

## 8. Multi-engine questions (SQLite + DuckDB / Postgres + DuckDB)

You cannot `JOIN` a table in SQLite to a table in DuckDB in one SQL string. Pattern:

1. Query SQLite/Postgres for keys or filters; collect IDs or tuples.
2. Pass those values into the second query (IN list, or merge in reasoning).
3. For large sets, use subqueries or temp filters in the **same** engine only.

---

## 9. Answers that require human-readable names

When the question asks for a **song title**, **business name**, **CPC title**, etc., the final answer must include that string from the source table — not only a numeric `track_id` or internal code. After aggregating in DuckDB, look up the display name in SQLite (or Postgres) using the join key.

---

## 10. Geography-filtered rankings (stock indices and similar)

Build the **eligible symbol set** from metadata (`index_info` / exchange) **before** ranking on trade data. Do not rank symbols that belong to exchanges outside the region named in the question. For multi-symbol list answers, include every required symbol from the filtered set after ranking.

---

## 11. Operational harness note (MCP)

Benchmark runs should start the MCP server with **one** dataset’s `db_config.yaml` registered so logical names like `metadata_database` map to the correct files. If you see “Available: […]” listing wrong tables or `no such table` errors for tables that exist in the dataset docs, assume the MCP registry was misconfigured — prefer introspection (`sqlite_master`, `information_schema`) on the connection you actually have.

---

## 12. Ranking & aggregation discipline (incorrect-plan guardrails)

These rules prevent “right data, wrong algorithm” failures:

1. **Two-stage questions** — If the prompt first asks which entity/region/group has the **most** of something (count, cardinality, coverage) and then asks for a **second metric** “there” or “for that winner”, you must compute the second metric **only** over the population that matches the winning key from stage one. Do not compute the second metric globally and then pick the winner from the first stage as decoration.

2. **Top-N categories, tags, or labels** — When the question asks for the top categories (or similar) **across all** qualifying entities, aggregate from the **full** eligible set of entities. Do not rank categories using only the top few entities by an unrelated statistic (that biases the category distribution).

3. **Row-level vs entity-level averages** — If the metric is defined over observations (e.g. reviews, trades, events), average **those rows** inside the filtered set. If you instead average pre-aggregated per-entity means, you re-weight entities unequally unless the question explicitly asks for that. When unsure, prefer row-level aggregation and compare mentally to a grouped average as a sanity check (CORRECTIONS LOG Entry 006).

4. **Counts from fact tables** — Prefer counting rows in a **fact** table (reviews, check-ins, events) over using denormalized “cached” count fields on a parent document when the question is about **actual** activity in a time window or after filters. Cached fields can be stale or defined differently.

5. **MongoDB global extrema** — For “highest/lowest/max/min across the whole collection”, use an **aggregation** with `$sort` and `$limit` (and correct `$match`). Do not use `find` and assume a capped tool preview reflects the global optimum.

6. **Completeness before `return_answer`** — If the expected output is a **set or list** of all qualifying items, ensure your last query materialized the **full** set (count rows in tool output vs expected cardinality). Partial lists from early `LIMIT` or from scanning only a sample of businesses fail validators (see CORRECTIONS LOG Entry 011).
