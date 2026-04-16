# PanCancer Atlas Dataset — Domain Knowledge

This document is injected into the agent's Domain Knowledge context layer before any PanCancer Atlas query is answered. All facts here are specific to this dataset — do not assume they apply to other DAB datasets.

---

## Dataset Structure

Two active databases. Clinical data lives in PostgreSQL, molecular profiling data lives in SQLite.

| Database | Format | What it contains |
|----------|--------|-----------------|
| `clinical_database` | PostgreSQL | Patient clinical metadata — demographics, cancer type, survival |
| `molecular_database` | SQLite | Mutation data and RNA expression per patient |

---

## Schema Reference

### PostgreSQL — `clinical_database`

#### `clinical_info` table
| Field | Notes |
|-------|-------|
| `Patient_description` | Patient identifier — links to `ParticipantBarcode` in molecular tables |
| 100+ other attributes | Cancer type acronym, demographics, diagnosis, treatment outcomes, survival status |

> The full field list is not enumerated in the schema. Use `Patient_description` as the join key to molecular data.

### SQLite — `molecular_database`

#### `Mutation_Data` table
| Field | Type | Notes |
|-------|------|-------|
| `ParticipantBarcode` | str | Patient identifier — links to `clinical_info.Patient_description` |
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
| `FILTER` | str | `PASS` = reliable mutation call |

#### `RNASeq_Expression` table
| Field | Type | Notes |
|-------|------|-------|
| `ParticipantBarcode` | str | Patient identifier — links to `clinical_info.Patient_description` |
| `SampleBarcode` | str | Sample identifier |
| `AliquotBarcode` | str | Aliquot identifier |
| `SampleTypeLetterCode` | str | Sample type abbreviation |
| `SampleType` | str | Sample type description |
| `Symbol` | str | Gene symbol |
| `Entrez` | str | Entrez gene ID |
| `normalized_count` | float | Normalized RNA expression value |

---

## Join Key

`clinical_info.Patient_description` ↔ `Mutation_Data.ParticipantBarcode` ↔ `RNASeq_Expression.ParticipantBarcode`

All three refer to the same patient. Match directly by value.

---

## Domain Rules

### Gene Expression — Log Transform
Average log10-transformed expression is computed as:
```
mean(log10(normalized_count + 1))
```
The `+1` is mandatory — `normalized_count` can be 0, and `log10(0)` is undefined.

### Chi-Square Statistic
```
χ² = Σ (Oij - Eij)² / Eij
Eij = (row_total × col_total) / grand_total
```

### Cancer Type Acronyms
| Acronym | Full Name |
|---------|-----------|
| LGG | Brain Lower Grade Glioma |
| BRCA | Breast Invasive Carcinoma |

Use these when filtering by cancer type — the `clinical_info` table stores the acronym form.

### Mutation Filter
Only use mutations where `FILTER = 'PASS'` unless the query explicitly asks for all mutations.
