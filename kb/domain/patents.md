# Patents Dataset — Domain Knowledge

This document is injected into the agent's Domain Knowledge context layer before any Patents query is answered. All facts here are specific to this dataset — do not assume they apply to other DAB datasets.

---

## Dataset Structure

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

## Join Key

`publicationinfo.cpc` contains CPC code strings. Match against `cpc_definition.symbol` to get the full title via `titleFull`.

The `cpc` field is a JSON-like string — parse it to extract individual code values before joining.

---

## Domain Rules

### Dates — Always Natural Language
All date fields (`publication_date`, `filing_date`, `grant_date`, `priority_date`) are stored as natural language strings e.g. `"March 15th, 2020"`. Use regex or string parsing — do not expect ISO date format.

### CPC Hierarchy
CPC codes are hierarchical. A query about a category may require matching at a parent level, not just exact symbol match. Use `level` and `parents` fields in `cpc_definition` to navigate up the hierarchy.

### Patent Key Identifiers
`Patents_info` is a natural language field — application number, publication number, assignee, and country code are embedded in the text, not separate columns. Use regex to extract them when needed.

### Citation Format
`citation` is a string list of cited works — both patent and non-patent literature. Parse as a list before counting or filtering.
