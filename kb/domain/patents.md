# Patents Dataset — Domain Knowledge

This document is injected into the agent's Domain Knowledge context layer before any Patents query is answered. All facts here are specific to this dataset — do not assume they apply to other DAB datasets.

---

## Dataset Overview

Two active databases. Patent publication records live in SQLite, CPC classification definitions live in PostgreSQL.

| Database | Format | What it contains |
|----------|--------|-----------------|
| `publication_database` | SQLite | Patent publication metadata — titles, abstracts, dates, CPC codes, citations |
| `CPCDefinition_database` | PostgreSQL | Hierarchical CPC code definitions and titles |

---

## Schema Reference

### SQLite — `publication_database`

#### `publicationinfo` table
| Field | Type | Notes |
|-------|------|-------|
| `Patents_info` | str | Natural language summary — includes application number, publication number, assignee, country code |
| `kind_code` | str | Publication kind (e.g. type of document issued) |
| `application_kind` | str | e.g. "utility patent application" |
| `pct_number` | str | Patent Cooperation Treaty number if applicable |
| `family_id` | str | Links related patents in the same family |
| `title_localized` | str | Patent title |
| `abstract_localized` | str | Patent abstract |
| `claims_localized_html` | str | Claims section in HTML |
| `description_localized_html` | str | Description section in HTML |
| `publication_date` | str | Natural language format e.g. "March 15th, 2020" |
| `filing_date` | str | Natural language format |
| `grant_date` | str | Natural language format |
| `priority_date` | str | Natural language format |
| `priority_claim` | str | List of priority applications |
| `inventor_harmonized` | str | Harmonized inventor list |
| `examiner` | str | USPTO examiner |
| `uspc` | str | US Patent Classification codes |
| `ipc` | str | International Patent Classification codes |
| `cpc` | str | JSON-like list of CPC entries — each has a code and metadata |
| `citation` | str | Cited patents and non-patent literature |
| `parent` | str | Parent patent applications |
| `child` | str | Child patent applications |
| `entity_status` | str | e.g. "small entity", "large entity" |
| `art_unit` | str | USPTO art unit |

### PostgreSQL — `CPCDefinition_database`

#### `cpc_definition` table
| Field | Type | Notes |
|-------|------|-------|
| `symbol` | str | CPC classification code — links to codes in `publicationinfo.cpc` |
| `titleFull` | str | Full descriptive title of the CPC code |
| `titlePart` | str | Abbreviated title |
| `level` | int | Hierarchy level 1–5 |
| `parents` | str | JSON-like list of parent CPC symbols |
| `childGroups` | str | JSON-like list of child symbols |
| `definition` | str | Full definition |
| `status` | str | "active" or "deleted" |
| `dateRevised` | str | Natural language revision date |

---

## Cross-Database Join Keys

`publicationinfo.cpc` contains CPC code strings. Match against `cpc_definition.symbol` to get the full title via `titleFull`.

The `cpc` field is a JSON-like string — parse it to extract individual code values before joining.

---

## Data Semantics

### Dates — Always Natural Language
All date fields (`publication_date`, `filing_date`, `grant_date`, `priority_date`) are stored as natural language strings e.g. `"March 15th, 2020"`. Use regex or string parsing — do not expect ISO date format.

### CPC Hierarchy
CPC codes are hierarchical. A query about a category may require matching at a parent level, not just exact symbol match. Use `level` and `parents` fields in `cpc_definition` to navigate up the hierarchy.

### Patent Key Identifiers
`Patents_info` is a natural language field — application number, publication number, assignee, and country code are embedded in the text, not separate columns. Use regex to extract them when needed.

### Citation Format
`citation` is a string list of cited works — both patent and non-patent literature. Parse as a list before counting or filtering.

---

## Query Strategy Playbook

### 1) CPC-focused analysis (category or technology theme)
1. Parse `publicationinfo.cpc` into normalized CPC symbols (trim whitespace and punctuation noise).
2. Left-join parsed symbols to `cpc_definition.symbol`.
3. Prefer `titleFull` for semantic grouping; use `level` to control granularity.
4. Keep unmatched symbols in diagnostics output to detect definition-table gaps.

### 2) Time-window analysis (filing/publication/grant)
1. Normalize date strings with deterministic parsing (month-name + ordinal support).
2. Build a canonical date column in a CTE before filtering or grouping.
3. Apply date predicates only after successful parse checks.
4. Report parse-failure count to avoid silent row loss.

### 3) Assignee / identifier extraction
1. Extract candidate fields from `Patents_info` via regex (application, publication, assignee, country).
2. Materialize extraction results as temporary structured columns.
3. Validate extraction coverage before computing aggregates.

---

## Common Pitfalls

- Treating `cpc` as a scalar string instead of a list of symbols.
- Joining on CPC title text instead of canonical symbol.
- Mixing `filing_date`, `publication_date`, and `grant_date` in one metric without explicit definition.
- Using strict inner joins to CPC definitions and unintentionally dropping patents with unknown/deleted symbols.
- Counting raw citation string length rather than parsed citation entries.

---

## Validation Checklist

- Date quality: parse success rate and null-rate after normalization.
- CPC coverage: percentage of parsed symbols matched to `cpc_definition`.
- Join inflation: compare distinct patent count pre/post CPC explode+join.
- Metric consistency: verify denominator (patents vs CPC assignments vs citations).
- Spot-check: manually inspect a few rows with extreme values (top cited, oldest, newest).

---

## Leakage-Safe Policy

- Do not store or encode benchmark expected outputs, constants, or final numeric answers.
- Keep this KB methodology-first: schema semantics, parsing rules, joins, and validation only.
- If prior run outcomes are referenced, they must remain generic process lessons (no query-specific targets).
