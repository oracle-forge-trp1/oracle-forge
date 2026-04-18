# PanCancer Atlas Dataset — Domain Knowledge

This document is injected into the agent's Domain Knowledge context layer before any PanCancer Atlas query is answered. All facts here are specific to this dataset — do not assume they apply to other DAB datasets.

---

⚠️ **CRITICAL — READ BEFORE ANY QUERY:**

**1. Cross-DB joins are NOT SQL — query each DB separately, merge in Python.**
Do NOT write `FROM duckdb_table JOIN (SELECT ... FROM query_postgres(...))` — DuckDB has no `query_postgres()` function. This syntax is invalid and will always fail with a Parser Error. → **See Entry 017, Entry 048**

**2. `clinical_info` does NOT have a `gender` column.**
Confirmed absent in live runs. Available sex/demographic fields: `race`, `ethnicity`, `menopause_status`. To filter by biological sex, use `menopause_status` or introspect for an alternative. → **See Entry 049**

**3. Patient identifier column name varies — always introspect before joining.**
Run `SELECT * FROM clinical_info LIMIT 3` and `information_schema.columns` to discover actual column names in both databases before writing any join.
DuckDB column `FILTER` is a reserved word — always quote it: `"FILTER" = 'PASS'`.


## Dataset Overview

Two active databases. Clinical data lives in PostgreSQL; molecular data (mutations, expression) is served as **`molecular_database`** in the harness — the engine is **whatever `db_config.yaml` declares** (often DuckDB). Always follow the **DATABASE DESCRIPTION** for the active run.

| Database | Typical engine | What it contains |
|----------|----------------|------------------|
| `clinical_database` | PostgreSQL | Patient clinical metadata — demographics, cancer type, survival |
| `molecular_database` | Often DuckDB | Mutation data and RNA expression per patient |

---

## Schema Reference

### PostgreSQL — `clinical_database`

#### `clinical_info` table
| Field | Notes |
|-------|-------|
| Patient identifier column(s) | Name varies — use live introspection (`information_schema.columns` / sample `SELECT * LIMIT 3`) |
| Diagnosis / cancer cohort | Often stored under acronym or text fields — filter using values **present in the table** (e.g. project code in diagnosis fields) |
| Demographics, survival, histology | Column names vary; never assume `gender` or `ParticipantBarcode` exists without checking |

> Join keys to molecular `ParticipantBarcode` must be discovered from actual columns in **both** databases. If a query on assumed column names returns “column does not exist”, introspect and retry.

### Molecular database — `Mutation_Data` table
| Field | Type | Notes |
|-------|------|-------|
| `ParticipantBarcode` | str | Patient/sample barcode — align to clinical rows via introspected join rule |
| `Tumor_SampleBarcode` | str | Tumor sample identifier |
| `Tumor_AliquotBarcode` | str | Tumor aliquot identifier |
| `Normal_SampleBarcode` | str | Normal control sample identifier |
| `Normal_AliquotBarcode` | str | Normal control aliquot identifier |
| `Normal_SampleTypeLetterCode` | str | Sample type abbreviation |
| `Hugo_Symbol` | str | Gene symbol e.g. `TP53`, `CDH1` |
| `HGVSp_Short` | str | Protein-level mutation annotation |
| `Variant_Classification` | str | e.g. `Missense_Mutation`, `Nonsense_Mutation` |
| `HGVSc` | str | Coding DNA sequence mutation annotation |
| `CENTERS` | str | Contributing sequencing center |
| `FILTER` | str | `PASS` = reliable mutation call — in SQL use `"FILTER"` (quoted) because `FILTER` is a reserved word |

#### `RNASeq_Expression` table
| Field | Type | Notes |
|-------|------|-------|
| `ParticipantBarcode` | str | Patient/sample barcode — align to clinical rows via introspected join rule |
| `SampleBarcode` | str | Sample identifier |
| `AliquotBarcode` | str | Aliquot identifier |
| `SampleTypeLetterCode` | str | Sample type abbreviation |
| `SampleType` | str | Sample type description |
| `Symbol` | str | Gene symbol |
| `Entrez` | str | Entrez gene ID |
| `normalized_count` | float | Normalized RNA expression value |

---

## Cross-Database Join Keys

1. List clinical identifier columns and molecular `ParticipantBarcode` samples.
2. Define the mapping rule (exact match, substring, or normalized barcode) from **observed** values.
3. Query each engine separately; merge cohorts in your reasoning — **no cross-engine SQL JOIN**.

---

## Data Semantics

### Gene Expression — Log Transform
Use the transform the **question** specifies. If it asks for `log10(normalized_count)` without `+1`, follow the prompt; if values can be zero, handle zeros explicitly. When in doubt, match the prompt wording exactly.

### Chi-Square Statistic
```
χ² = Σ (Oij - Eij)² / Eij
Eij = (row_total × col_total) / grand_total
```
When the question asks for the statistic, the **final answer must be a single numeric value** (and any requested ancillary labels), not a long narrative table of intermediate counts.

### Cancer Type Acronyms
| Acronym | Full Name |
|---------|-----------|
| LGG | Brain Lower Grade Glioma |
| BRCA | Breast Invasive Carcinoma |

Use these when filtering by cancer type — the `clinical_info` table stores the acronym form.

### Histology / morphology / coded classification

Some questions reference standardized histology or morphology **codes** (for example ICD-O style tokens). Column names vary — use **live schema introspection** on `clinical_info` to locate the fields that store histology/morphology text or codes. When emitting an answer that must repeat such a code, copy the token **verbatim** from the selected row.

For text labels with parenthetical qualifiers (for example `Mixed Histology (please specify)`), keep the full label exactly as stored; do not shorten to a base phrase.
For code outputs (for example `9382/3` style tokens), preserve separators and punctuation exactly; do not normalize or strip characters.

### Mutation Filter
Only use reliable mutation rows where the quality column equals `PASS` unless the query asks otherwise. In SQL: `"FILTER" = 'PASS'`.

---

## Query Strategy Playbook

### 1) Clinical ↔ molecular cohort joins
1. Start with a patient cohort in `clinical_info`.
2. Join to `Mutation_Data` and/or `RNASeq_Expression` by `ParticipantBarcode`.
3. Use distinct patient counts when combining mutation and expression tables to avoid duplicate inflation.

### 2) Gene-level association queries
1. Normalize gene symbol comparisons (`UPPER(TRIM(...))`).
2. For mutation-based analyses, filter `FILTER = 'PASS'` by default.
3. Separate mutation presence (binary) from mutation burden (count) depending on question intent.

### 3) Expression summaries by subgroup
1. Build subgroup definitions from clinical variables first.
2. Compute per-patient expression summaries before group aggregates when multiple samples exist.
3. Use `mean(log10(normalized_count + 1))` consistently for transformed comparisons.

---

## Common Pitfalls

- Joining mutation and expression tables directly without patient-level de-duplication. → **See Entry 017**
- Mixing tumor-level and patient-level units in one statistic.
- Forgetting `+1` before log transform on zero-valued expression.
- Assuming `ParticipantBarcode` column name without introspecting the actual clinical_info schema. → **See Entry 028**
- Forgetting to quote `"FILTER"` column in DuckDB SQL. → **See Entry 026** (extended corrections log)
- Comparing cancer types using free-text assumptions instead of acronym values stored in clinical data.
- Ignoring quality filter (`FILTER`) in mutation analyses.

---

## Validation Checklist

- Cohort integrity: patient count before and after joins.
- Duplicate control: verify distinct patient vs distinct sample totals.
- Symbol sanity: check `%` of rows with null/empty gene symbols.
- Transform sanity: confirm no invalid log inputs and no NaN aggregates.
- Cross-check directionality: sample a few patient records to confirm subgroup assignment and joined molecular values.

---

## Leakage-Safe Policy

- No benchmark answer keys, no target numbers, no query-by-query outcomes.
- Retain only reusable biological-data handling patterns and quality controls.
- Any historical notes must be phrased as general failure-mode prevention, not expected-result hints.
