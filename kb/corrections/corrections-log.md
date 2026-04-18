# KB v3 — Corrections Log (Leakage-Safe)

Purpose: capture reusable failure patterns and fixes without storing benchmark answer keys.

Policy:
- Do not store exact benchmark questions.
- Do not store expected outputs, winner identities, forbidden-value lists, or ground-truth numbers.
- Keep entries procedural and dataset-agnostic where possible.

Format:
- Failure pattern
- Root cause
- Correct approach
- Verification note

Entry metadata (recommended for every new entry):
- `confidence`: low | medium | high
- `last_verified_run_id`: run id from score log where rule was last validated
- `datasets_seen`: list of datasets where the pattern was observed
- `owner`: person responsible for maintenance
- `expires_after_runs`: review threshold for freshness

---

## Entry 001 — Cross-DB Key Normalization

Metadata:
- confidence: high
- datasets_seen: yelp, bookreview, crmarenapro
- expires_after_runs: 20

Failure pattern:
- Cross-database joins return zero rows even though related entities exist.

Root cause:
- Equivalent IDs use different string prefixes across systems.

Correct approach:
- Normalize both IDs to a canonical key before joining (for example, extract numeric suffix).
- Validate join cardinality after normalization.

Verification note:
- Add a sanity check query that confirms at least one joined row before final aggregation.

---

## Entry 002 — Mixed Datetime Formats

Metadata:
- confidence: high
- datasets_seen: yelp, stockindex, stockmarket
- expires_after_runs: 20

Failure pattern:
- Time-filtered counts/aggregates are unexpectedly low.

Root cause:
- Single-format datetime parsing drops rows with alternative formats.

Correct approach:
- Use `COALESCE` over multiple `TRY_STRPTIME` patterns.
- For year-only filters, use regex extraction as fallback.

Verification note:
- Compare parsed row count vs total non-null date rows.

---

## Entry 003 — Unstructured Location Fields

Metadata:
- confidence: medium
- datasets_seen: yelp, googlelocal
- expires_after_runs: 20

Failure pattern:
- City/state filters produce empty or partial results.

Root cause:
- Location is embedded in free text rather than structured columns.

Correct approach:
- Parse location with regex/text functions before filtering.
- Add a fallback parser for alternative phrasing.

Verification note:
- Spot-check parsed state/city values on a random sample.

---

## Entry 004 — String-Typed Numeric/Boolean Fields

Metadata:
- confidence: high
- datasets_seen: yelp, crmarenapro
- expires_after_runs: 20

Failure pattern:
- Numeric comparisons or boolean logic behave incorrectly.

Root cause:
- Source values are stored as strings.

Correct approach:
- Cast numeric strings before arithmetic.
- Normalize boolean-like values (`"1"`, `"0"`, `"true"`, `"false"`) before filtering.

Verification note:
- Assert conversion success rate and log cast failures.

---

## Entry 005 — Serialized Nested Attributes

Metadata:
- confidence: high
- datasets_seen: yelp
- expires_after_runs: 20

Failure pattern:
- Attribute-based filters miss valid entities.

Root cause:
- Nested structures are serialized strings or mixed types.

Correct approach:
- Parse only the serialized nested field when needed.
- Do not parse already-materialized dictionaries.
- Use tolerant matching for value variants.

Verification note:
- Count entities matching each accepted variant.

---

## Entry 006 — Avoid Average-of-Averages

Metadata:
- confidence: high
- datasets_seen: yelp, stockmarket, bookreview
- expires_after_runs: 20

Failure pattern:
- Final averages are biased high/low.

Root cause:
- Averaging per-group averages instead of raw observations.

Correct approach:
- Aggregate directly over row-level measurements whenever the metric requires equal weight per row.

Verification note:
- Compare row-level average with grouped-average result and reject inconsistent method.

---

## Entry 007 — Output Formatting Compatibility

Metadata:
- confidence: high
- datasets_seen: stockindex, yelp, bookreview
- expires_after_runs: 20

Failure pattern:
- Semantically correct answer fails validation.

Root cause:
- Output includes extra formatting/text that breaks parser assumptions.

Correct approach:
- Return compact plain text.
- Keep paired values adjacent (for example, code and country/value) with minimal separators.

Verification note:
- Run a local formatting check before returning final output.

---

## Entry 008 — Single-Winner Query Discipline

Metadata:
- confidence: medium
- datasets_seen: stockindex, stockmarket
- expires_after_runs: 20

Failure pattern:
- Correct winner is present but response still fails.

Root cause:
- Response includes extra alternatives, rankings, or commentary.

Correct approach:
- For single-winner prompts, return only the winning entity.
- Omit runner-up context unless explicitly requested.

Verification note:
- Enforce response-shape rule in post-processing.

---

## Entry 009 — Top-N Aggregation Completeness

Metadata:
- confidence: high
- datasets_seen: yelp, github_repos, music_brainz_20k
- expires_after_runs: 20

Failure pattern:
- Top categories/entities are incomplete or misordered.

Root cause:
- Aggregation was performed over truncated intermediate subsets.

Correct approach:
- Aggregate over full eligible population before ranking.
- Apply top-N only at the final ranking stage.

Verification note:
- Compare top-N from full run vs sampled/truncated run.

---

## Entry 010 — Required Identifier Emission

Metadata:
- confidence: high
- datasets_seen: crmarenapro, patents
- expires_after_runs: 20

Failure pattern:
- Validator rejects output due to missing required ID token (for example issue/article/record identifiers).

Root cause:
- Final answer is returned as narrative summary without explicitly emitting the identifier field.

Correct approach:
- Add an answer-contract check before finalize: if prompt intent asks for an identifier, output must include at least one ID-shaped token.
- Prefer explicit prefix style in final answer (for example `ID: <value>`), then optional explanation.

Verification note:
- Run regex assertion for required ID family before finalizing.

---

## Entry 011 — Exhaustive Set/List Coverage

Metadata:
- confidence: high
- datasets_seen: bookreview, yelp, agnews
- expires_after_runs: 20

Failure pattern:
- Output includes partial set/list where validator expects all qualifying items.

Root cause:
- Early truncation, premature finalize, or missing completeness check on grouped outputs.

Correct approach:
- Materialize full eligible set first, then render final list.
- Apply deterministic ordering and deduplicate before emitting values.

Verification note:
- Compare item_count in final output vs item_count from final aggregation table.

---

## Entry 012 — Policy Violation Contradiction Guard

Metadata:
- confidence: medium
- datasets_seen: crmarenapro
- expires_after_runs: 20

Failure pattern:
- Output states “no violation” while evidence rows indicate a violation class and related reference item.

Root cause:
- Decision statement not cross-checked against extracted evidence.

Correct approach:
- Force binary decision consistency check: if violation evidence rows are non-empty, final decision cannot be "no violation".
- Emit the supporting reference ID when violation evidence exists.

Verification note:
- Add pre-final invariant: `violation_detected == (evidence_count > 0)`.

---

## Entry 013 — Numeric Tolerance and Precision Discipline

Metadata:
- confidence: high
- datasets_seen: DEPS_DEV_V1, stockindex, yelp
- expires_after_runs: 20

Failure pattern:
- Numeric outputs fail validator tolerance checks despite near-correct intermediate calculations.

Root cause:
- Inconsistent rounding/formatting or omission of final numeric token.

Correct approach:
- Keep full precision internally; round only at final render according to prompt/validator expectation.
- Emit a single canonical numeric token in final answer.

Verification note:
- Run final numeric regex check and tolerance sanity check before response emission.

---

## Entry 014 — Taxonomy-Locked Classification Output

Metadata:
- confidence: medium
- datasets_seen: crmarenapro, agnews
- expires_after_runs: 20

Failure pattern:
- Classification label is semantically close but not one of accepted taxonomy labels.

Root cause:
- Free-form wording used instead of constrained label set.

Correct approach:
- Map evidence to a predefined allowed label set and emit exact canonical label text.
- Reject out-of-taxonomy labels in finalization step.

Verification note:
- Validate output label membership against allowed taxonomy list.

---

## Entry 015 — Temporal Token Compliance

Metadata:
- confidence: medium
- datasets_seen: agnews, stockmarket, googlelocal
- expires_after_runs: 20

Failure pattern:
- Time-related answer fails because required temporal token format is missing (for example month-name form).

Root cause:
- Date normalized for computation but rendered in non-required textual format.

Correct approach:
- Separate compute format from render format.
- When prompt implies month-level wording, render explicit month-name token in final output.

Verification note:
- Run date-render regex check (month-name presence) before finalize.

---

## Entry 016 — MongoDB Extrema Must Use Aggregation

Metadata:
- confidence: high
- datasets_seen: agnews, yelp, googlelocal
- expires_after_runs: 20

Failure pattern:
- “largest / smallest / longest / shortest / max / min” questions fail or vary run-to-run.

Root cause:
- Using MongoDB `find` and reasoning over a truncated sample (e.g. first 500 docs) instead of the full eligible set.

Correct approach:
- Use `query_mongodb` with `query_type='aggregate'`:
  - `$match` to restrict to the eligible subset
  - `$project` a deterministic numeric key (e.g. text length via `$strLenCP`)
  - `$sort` descending/ascending
  - `$limit: 1`
- Only return the single winning document/field needed for the answer.

Verification note:
- Confirm the pipeline returns exactly 1 row and that the projected key is non-null.

---

## Entry 017 — Cross-DB Joins: Compute Locally, Don’t Fake SQL

Metadata:
- confidence: high
- datasets_seen: bookreview, deps_dev_v1, crmarenapro
- expires_after_runs: 20

Failure pattern:
- Agent attempts `JOIN` across different physical databases (e.g., PostgreSQL table joined to a SQLite table) and gets “relation does not exist” or empty results.

Root cause:
- Cross-database joins are not supported by the underlying DB engines; they require multi-step retrieval then merging.

Correct approach:
- Query each database separately for the minimal fields required.
- Normalize join keys (often by numeric suffix extraction).
- Merge in-memory (conceptually: hash join on normalized key).
- Only then compute group-bys / top-1 / filters.

Verification note:
- Log matched/unmatched join counts and ensure the join is non-empty before final aggregation.

---

## Entry 018 — Tool `db_name` vs SQL table name (DuckDB / SQLite)

Metadata:
- confidence: high
- datasets_seen: DEPS_DEV_V1, stockmarket, github_repos
- expires_after_runs: 20

Failure pattern:
- Tool calls fail with “Unknown DuckDB db_name …” or query the wrong file because `db_name` was set to a **table** or **file stem** instead of the configured logical database name.

Root cause:
- MCP / toolbox maps one connection string per logical `db_name` from `db_config.yaml`. Tables live *inside* that connection — they are not separate `db_name` values.

Correct approach:
- Read logical names from DATABASE DESCRIPTION / `db_config.yaml`.
- Use `query_duckdb(db_name="<logical>", sql="SELECT … FROM <table> …")` — never pass a table name as `db_name`.

Verification note:
- If the tool errors with “Available: […]”, pick only names from that list.

---

## Entry 019 — Validator imports (`common_scaffold`)

Metadata:
- confidence: high
- datasets_seen: GITHUB_REPOS, stockmarket, PATENTS, PANCANCER_ATLAS
- expires_after_runs: 20

Failure pattern:
- Harness raises `ModuleNotFoundError: common_scaffold` when loading `validate.py`.

Root cause:
- DataAgentBench validators import shared helpers from the `common_scaffold` package at the **repository root** of the DAB checkout. A partial copy of DAB or a wrong `--dab-root` breaks imports.

Correct approach:
- Keep a full `git clone` of `ucbepic/DataAgentBench` next to oracle-forge.
- Point `--dab-root` / `DATAAGENTBENCH_ROOT` at that directory (must contain `common_scaffold/`).

Verification note:
- `test -d "$DAB_ROOT/common_scaffold"` on the server before long benchmark runs.

---

## Entry 020 — Classification / taxonomy tokens must match storage

Metadata:
- confidence: high
- datasets_seen: yelp, agnews, patents
- expires_after_runs: 20

Failure pattern:
- Validator looks for a label token (category code, CPC symbol, histology code) that never appears in the answer.

Root cause:
- Free-form paraphrase or guessed label instead of the exact token shape present in the source row or reference table.

Correct approach:
- After computing the winning row(s), copy identifiers **verbatim** from query output (trim only outer whitespace).
- For hierarchical codes (e.g. CPC), join to the definition table and emit the same `symbol` string the schema stores.

Verification note:
- Grep the final answer for the identifier substring returned by the last successful query.

---

## Entry 021 — List / multi-entity answers: completeness vs truncation

Metadata:
- confidence: high
- datasets_seen: bookreview, yelp, stockmarket
- expires_after_runs: 20

Failure pattern:
- Validator reports a missing list item or title though the approach was directionally correct.

Root cause:
- Final answer finalized before merging the full eligible set, or LLM context truncation dropped rows needed to enumerate every item.

Correct approach:
- Compute the full result set in SQL/aggregation, then emit **all** required strings in one `return_answer`.
- If intermediate results are large, aggregate in the database first; avoid pasting huge raw dumps — but do not drop required entities from the final list.

Verification note:
- Count distinct required entities in the result set vs tokens in the final answer.

---

## Entry 022 — Ratio / fraction validators

Metadata:
- confidence: medium
- datasets_seen: GITHUB_REPOS, agnews
- expires_after_runs: 20

Failure pattern:
- “No value rounds to …” despite intermediate work.

Root cause:
- Wrong population for numerator/denominator, or rounding too early so no printed decimal matches the checker.

Correct approach:
- Define the counted sets explicitly, then divide; emit a decimal that matches the validator’s rounding rule (often two decimal places).

Verification note:
- Recompute ratio in one expression and print the same float you validated.

---

## Entry 023 — Geography-constrained single winner (indices / exchanges)

Metadata:
- confidence: medium
- datasets_seen: stockindex
- expires_after_runs: 20

Failure pattern:
- Winner fails with “forbidden value” or “missing target” when prompts narrow geography (e.g. region name).

Root cause:
- Ranking across **all** symbols without filtering metadata to the region implied by the question.

Correct approach:
- Restrict candidates using `index_info` (exchange, currency, other metadata) **before** `ORDER BY` on the trade table.
- For single-winner prompts, return only one symbol after the filter.

Verification note:
- Confirm every candidate symbol passes the geographic filter row in metadata.

---

## Entry 024 — MCP logical DB registry per dataset

Metadata:
- confidence: high
- datasets_seen: (all multi-engine DAB datasets)
- expires_after_runs: 20

Failure pattern:
- Queries hit the wrong SQLite/DuckDB file: “no such table” for tables that exist in the dataset docs, or `Available:` lists unrelated logical names.

Root cause:
- Multiple `db_config.yaml` files reuse the same logical `db_name` (e.g. `metadata_database`). Registering every config at once causes last-wins overwrites.

Correct approach:
- Run the MCP server with a **single** active `db_config.yaml` for the benchmark dataset (harness sets `ORACLE_FORGE_REGISTER_ONLY_DB_CONFIG` when starting MCP).

Verification note:
- After startup, `Available:` should only include connections for the current dataset.

---

## Entry 025 — PostgreSQL camelCase columns

Metadata:
- confidence: high
- datasets_seen: patents, pancancer_atlas, crmarenapro
- expires_after_runs: 20

Failure pattern:
- `column "foo" does not exist` with HINT referencing a mixed-case name.

Root cause:
- Unquoted identifiers are folded to lowercase.

Correct approach:
- Use double-quoted identifiers in SQL: `"titleFull"`, `"titlePart"`.

Verification note:
- Re-run the same query with quotes; column should resolve.

---

## Entry 026 — DuckDB `FILTER` column vs keyword

Metadata:
- confidence: high
- datasets_seen: pancancer_atlas
- expires_after_runs: 20

Failure pattern:
- Syntax errors or wrong filter when comparing mutation quality.

Root cause:
- Column named `FILTER` clashes with SQL keyword.

Correct approach:
- Quote the column: `"FILTER" = 'PASS'`.

Verification note:
- Predicate applies without parser errors.

---

## Entry 027 — Final answer shape: titles not only IDs

Metadata:
- confidence: high
- datasets_seen: music_brainz_20k, bookreview, patents
- expires_after_runs: 20

Failure pattern:
- Validator expects a natural-language title or label; output only numeric IDs.

Root cause:
- Aggregation stopped at surrogate keys.

Correct approach:
- After computing the winning id(s), join or lookup to emit the required **title/name/label** string from the catalog table.

Verification note:
- Final string contains human-readable tokens from the source row.

---

## Entry 028 — DuckDB binder/catalog errors: schema-first, don’t guess identifiers

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-18-001
- datasets_seen: deps_dev_v1, github_repos
- expires_after_runs: 20

Failure pattern:
- DuckDB queries fail with `Binder Error: Referenced column ... not found` or `Catalog Error: Table with name ... does not exist`.

Root cause:
- The query guessed table/column names or queried the wrong database connection (DuckDB vs SQLite).

Correct approach:
- When you see a binder/catalog error, immediately switch to schema discovery:
  - For DuckDB: `SHOW TABLES;` then `DESCRIBE <table>;` (or query `information_schema.columns`) and copy identifiers exactly.
  - If a table is expected to be in SQLite (metadata) but errors in DuckDB (artifacts), re-check the correct `db_name` and re-run in the right engine.
- Treat “Candidate bindings” in the binder error as the authoritative list of available columns.

Verification note:
- The corrected query runs without binder/catalog errors and returns non-empty results for a sanity `LIMIT 5`.

---

## Entry 029 — Never estimate from tool previews (no sampling for exact metrics)

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-18-005
- datasets_seen: agnews, github_repos, yelp, stockmarket
- expires_after_runs: 20

Failure pattern:
- Numeric outputs (counts, ratios, averages) fail validation when the agent “samples” a subset (e.g. first 80/500 rows) and extrapolates.

Root cause:
- Tool results are capped for context safety; using the preview as the population yields biased results.

Correct approach:
- For **exact** metrics, design queries that compute the answer in-database:
  - Use `COUNT(*)`, `SUM(...)`, `AVG(...)`, `GROUP BY`, `ORDER BY ... LIMIT` on the full eligible population.
  - If classification is required (e.g. from text), compute the exact eligible ID set first, then classify **all** of those IDs (or implement deterministic keyword rules with full coverage), and count precisely.
- Never emit “approximately”, “assuming representative”, or any extrapolated value.

Verification note:
- The final number is derived from exact counts over the complete eligible set (with explicit denominators).

---

## Entry 030 — Permission denied (PostgreSQL): treat as environment failure, pivot or fail fast

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-18-007
- datasets_seen: crmarenapro
- expires_after_runs: 20

Failure pattern:
- PostgreSQL queries fail with `permission denied for table ...` and the agent loops or fabricates an answer.

Root cause:
- The configured DB role lacks SELECT privileges on required tables (server-side setup issue), not an agent reasoning problem.

Correct approach:
- Do not retry the same query repeatedly.
- Pivot to alternative sources if the question can be answered from other databases/tables that are accessible.
- Otherwise, return a concise “cannot complete due to database permissions” answer rather than hallucinating.

Verification note:
- Trace shows a single permission error, a pivot attempt (if applicable), and no fabricated values.

---

## Entry 031 — SQLite `db_name` shows `Available: []`: config was not loaded / wrong dataset wiring

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-18-004
- datasets_seen: patents
- expires_after_runs: 20

Failure pattern:
- Tool error: `Unknown SQLite db_name 'X'. Available: []` (empty available list).

Root cause:
- The dataset `db_config.yaml` was not registered/loaded for the current run, or the agent is not receiving the correct dataset config path/description.

Correct approach:
- Treat this as a **run configuration** failure, not a query failure.
- Fail fast with an explicit note that the logical DB registry is empty, and avoid further tool calls that will repeat the same error.

Verification note:
- On a fixed run configuration, `Available:` includes the expected dataset logical DB names and queries succeed.

---

## Entry 032 — Category/name outputs must come from canonical fields (not inferred from descriptions)

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-18-012
- datasets_seen: yelp, googlelocal
- expires_after_runs: 20

Failure pattern:
- Validator says “Missing category: …” or “Missing name: …” even though the answer contains a plausible category/name.

Root cause:
- The agent inferred categories from free-text `description` (or omitted the `categories` field in projections) and returned an incomplete or non-canonical label.

Correct approach:
- When a question asks for a business/category label, **read it from the canonical field**:
  - Use the dataset’s `categories` (or equivalent taxonomy/list field) when available.
  - Always include that field in MongoDB projections (`{"name": 1, "categories": 1, ...}`).
- Only fall back to description-based inference if the canonical field is missing/null, and then return the closest exact token found in source text.

Verification note:
- The returned category/name string is a direct substring/value from the retrieved row/document (trim whitespace only).

---

## Entry 033 — Category token fidelity (parentheses/plurals/case are semantic)

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-18-012
- datasets_seen: yelp, googlelocal
- expires_after_runs: 20

Failure pattern:
- Validator reports missing category tokens such as `restaurants` or `american (new)` despite a semantically similar output.

Root cause:
- Final answer normalizes or paraphrases category labels (title-casing, singularization, punctuation stripping) instead of preserving canonical tokens.

Correct approach:
- Emit category labels exactly as stored in source category fields:
  - Preserve parentheses, ampersands, slashes, and punctuation.
  - Preserve stored casing and pluralization.
- If multiple category tokens are required, split/normalize only for counting, then render the exact canonical tokens for output.

Verification note:
- Every output category token can be matched directly to a token extracted from source `categories` values.

---

## Entry 034 — Final answer must be compact value output (no long reasoning)

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-18-005
- datasets_seen: agnews, pancancer_atlas, stockmarket
- expires_after_runs: 20

Failure pattern:
- Validator misses obvious values because the answer is wrapped in a long narrative, policy explanation, or “I cannot determine” preface.

Root cause:
- The model emits chain-of-thought style prose instead of the expected compact answer shape.

Correct approach:
- Final answer should contain only the required payload:
  - single numeric value, or
  - single entity/token, or
  - compact list in requested format.
- Remove analysis paragraphs, caveats about truncation, and methodological notes from final output.

Verification note:
- A human can parse the answer in one line and map it directly to validator target type.

---

## Entry 035 — Exact-token fidelity for identifiers and taxonomy labels

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-18-004
- datasets_seen: patents, pancancer_atlas, github_repos, deps_dev_v1
- expires_after_runs: 20

Failure pattern:
- Fuzzy/near-match failures for expected codes, names, histology labels, or repo paths.

Root cause:
- Output tokens are normalized, truncated, or paraphrased instead of copied verbatim from source rows.

Correct approach:
- For code/name/label outputs, emit exact source tokens:
  - preserve punctuation (`;`, `/`, `-`, parentheses),
  - preserve case,
  - avoid shortening or “cleaning” technical labels.
- If selecting top-N, compute first, then render each selected token exactly as stored.

Verification note:
- Every output token can be traced to an exact string in query results.

---

## Entry 036 — Run-to-run stability: deterministic ordering before LIMIT

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-18-012
- datasets_seen: yelp, stockindex, stockmarket, github_repos
- expires_after_runs: 20

Failure pattern:
- Different runs return different winners/top lists even with same model and prompt.

Root cause:
- Queries apply `LIMIT` without a stable tie-breaker or use partially ordered outputs, so ties can flip.

Correct approach:
- Any ranked query must use deterministic ordering:
  - primary metric DESC/ASC as required,
  - stable secondary key (entity id/name) to break ties before `LIMIT`.
- Apply ordering at the final ranking step (after all required filters/aggregations).

Verification note:
- Re-running the same query on unchanged data yields identical top rows.

---

## Entry 037 — Compact final output over narrative explanations

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-18-005
- datasets_seen: agnews, yelp, crmarenapro
- expires_after_runs: 20

Failure pattern:
- Answer contains long reasoning text; validator fails to detect required token/number even when reasoning suggests the right direction.

Root cause:
- The model returns analysis prose instead of the expected final payload format.

Correct approach:
- Return only final payload text (single value/token/list as requested).
- Strip meta commentary like “from sample”, “I cannot determine”, or methodology notes from final line.

Verification note:
- Final answer fits in one compact line and directly matches validator target type.

---

## Entry 038 — Required list cardinality contract (Top-N must return N)

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-18-012
- datasets_seen: deps_dev_v1, github_repos, googlelocal, yelp
- expires_after_runs: 20

Failure pattern:
- Validator reports missing names/items when output includes only a subset of required entities.

Root cause:
- Final answer was produced from partial intermediate results or early-stop reasoning before all required rows were rendered.

Correct approach:
- If prompt asks for `top N`, enforce this contract before final output:
  - final ranked result must contain at least N entities after dedupe,
  - deterministic ordering with tie-breaker,
  - render exactly N entities unless prompt says “up to N”.
- If fewer than N exist, state all available entities only when explicitly allowed by the question.

Verification note:
- Output entity count matches requested cardinality and each token maps to final ranked rows.

---

## Entry 039 — Exact-value output, never ratio reformats unless requested

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-18-005
- datasets_seen: agnews, stockmarket, yelp
- expires_after_runs: 20

Failure pattern:
- Numeric checks fail when output uses transformed representation (`23/111`, rounded integer, or reformatted unit) instead of expected numeric literal.

Root cause:
- Post-processing rewrote computed values to alternate formats not accepted by validators.

Correct approach:
- Emit one canonical numeric literal consistent with computation result.
- Do not convert decimal to fraction, percentage, or rounded integer unless prompt explicitly requests that format.
- Keep numeric precision sufficient for tolerance-based matching.

Verification note:
- The numeric token in output equals the computed metric representation used for validation.

---

## Entry 040 — Candidate filtering must precede winner selection (avoid wrong entity IDs)

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-18-007
- datasets_seen: crmarenapro, stockindex, stockmarket, yelp
- expires_after_runs: 20

Failure pattern:
- Output returns plausible but wrong ID/entity (wrong agent, wrong state, wrong symbol).

Root cause:
- Winner selected from a superset before applying all constraints (time window, status, geography, policy condition).

Correct approach:
- Apply full eligibility filters first, then rank/select winner.
- For ID outputs, verify the selected row still satisfies all predicates in the final filtered set.

Verification note:
- Re-running the final filtered query with `LIMIT 3` shows winner row at top and predicates satisfied.

---

## Entry 041 — Copy canonical taxonomy labels exactly (including qualifiers)

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-18-003
- datasets_seen: pancancer_atlas, patents, yelp
- expires_after_runs: 20

Failure pattern:
- Fuzzy/label misses for values with qualifiers or punctuation (parentheticals, semicolons, mixed case).

Root cause:
- Final output used normalized synonyms or truncated labels instead of canonical label text.

Correct approach:
- Render labels exactly from source fields selected in final result rows.
- Preserve punctuation and qualifiers (for example parenthetical suffixes and semicolon-separated facets).

Verification note:
- Every emitted label is an exact substring from selected source rows.

---

## Entry 042 — Yelp state token must be explicit and non-null

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-18-012
- datasets_seen: yelp
- expires_after_runs: 20

Failure pattern:
- Output contains `null`/missing state (`PA`/`Pennsylvania`) while numeric part is present.

Root cause:
- Business/state lookup omitted the `state` field or relied on records where state was missing after join/filter.

Correct approach:
- For any state-conditioned answer, include `state` in retrieval projection and require non-null state before finalization.
- If both abbreviation and full name appear in data/docs, emit at least one accepted token exactly (`PA` or `Pennsylvania`) adjacent to its paired value when needed.

Verification note:
- Final output contains a non-null state token copied from selected result rows.

---

## Entry 043 — Yelp category answers: include required canonical token set

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-18-012
- datasets_seen: yelp
- expires_after_runs: 20

Failure pattern:
- Category output misses expected tokens (e.g., `restaurants`, `food`) despite related categories being present.

Root cause:
- Category rendering used partial category subset or inferred “primary” category without preserving full canonical category evidence.

Correct approach:
- Build category output from canonical `business.categories` values over the fully filtered candidate set.
- Preserve exact tokens and include all required top-ranked categories for the requested cardinality.

Verification note:
- Every emitted category token maps directly to canonical category fields from selected businesses.

---

## Entry 044 — CRM ID-required prompts: never return `None`/permission text as final

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-18-007
- datasets_seen: crmarenapro
- expires_after_runs: 20

Failure pattern:
- Final answer is `None` or “Cannot complete due to permissions” while validator expects a concrete CRM ID (knowledge/article/agent/issue).

Root cause:
- Agent exits early on one failing source instead of finishing selection from available eligible records.

Correct approach:
- If prompt requires an ID token, final output must be an ID from the final filtered candidate set.
- Permission errors in one table are not sufficient to output `None` if alternate required data remains queryable; continue with accessible evidence.

Verification note:
- Final output matches expected ID shape and appears in selected candidate rows.

---

## Entry 045 — CRM winner-ID selection must use full filters + deterministic tie-break

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-18-007
- datasets_seen: crmarenapro
- expires_after_runs: 20

Failure pattern:
- Returned agent/product ID is close but wrong.

Root cause:
- Ranking selected from partially filtered rows or unstable tie ordering.

Correct approach:
- Apply all query predicates before ranking (time window, stage/status, ownership constraints).
- Use deterministic ordering for ties (metric DESC/ASC then stable ID ASC) before `LIMIT 1`.

Verification note:
- Re-running the same filtered query returns the same winning ID.

---

## Entry 046 — Avoid premature abstention when evidence exists

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-18-012
- datasets_seen: patents, pancancer_atlas, yelp, crmarenapro
- expires_after_runs: 20

Failure pattern:
- Final answer is a refusal (`No answer possible`, `cannot complete`, `insufficient data`) despite non-empty tool results in trace.

Root cause:
- The agent treats one failed subquery as terminal and ignores usable evidence from other successful calls.

Correct approach:
- Only abstain when **all** relevant evidence paths are empty/unavailable.
- If any successful evidence rows exist for required fields, synthesize the best compact answer from those rows.
- Keep refusal text out of final answer unless trace shows no usable rows at all.

Verification note:
- Query trace includes at least one successful evidence call and final answer is non-refusal payload.

---

## Entry 047 — Placeholder outputs (`None`/`null`/`N/A`) are invalid when answer shape expects entity/value

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-18-012
- datasets_seen: crmarenapro, yelp, patents, pancancer_atlas
- expires_after_runs: 20

Failure pattern:
- Final answer is `None`, `null`, `N/A`, or similar placeholder while validators expect concrete IDs/names/categories/numbers.

Root cause:
- Early termination or fallback formatting emits placeholders instead of selecting from available evidence.

Correct approach:
- Treat placeholders as invalid final output when prompt requires concrete payload.
- If any evidence rows exist, compact/synthesize a concrete answer from selected rows.

Verification note:
- Final output contains expected payload token type (ID/name/category/value), never placeholder-only text.

---

## Template

Metadata:
- confidence:
- last_verified_run_id:
- datasets_seen:
- owner:
- expires_after_runs:

Failure pattern:
- 

Root cause:
- 

Correct approach:
- 

Verification note:
- 

Promotion checklist (before marking a new rule as trusted):
- Rule validated in at least 2 independent runs.
- Rule improves strict pass behavior, not only repaired behavior.
- Rule is phrased as reusable method, not query-specific hint.
- Rule passes leakage lint checks.
