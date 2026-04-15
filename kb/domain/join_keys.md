# Ill-Formatted Join Key Glossary

## The Problem
The same real-world entity has different ID formats or column names across databases within a single DAB dataset. Direct equality joins fail silently — returning zero rows instead of an error.

---

## Known Cross-DB Key Mismatches in DAB

### yelp — business_id prefix mismatch
| Database | Column | Format | Example |
|---|---|---|---|
| MongoDB (businessinfo) | `business_id` | Prefixed string | `businessid_1` |
| DuckDB (user) | `business_ref` | Different prefix | `businessref_1` |

**Resolution:** Strip prefix (`businessid_` / `businessref_`), compare numeric suffix.
```python
def normalize_yelp_business_key(key):
    """Strip businessid_ or businessref_ prefix."""
    for prefix in ['businessid_', 'businessref_']:
        if str(key).startswith(prefix):
            return str(key)[len(prefix):]
    return str(key)
```

### bookreview — column name mismatch
| Database | Column | Notes |
|---|---|---|
| PostgreSQL (books_info) | `book_id` | Primary key for books |
| SQLite (review) | `purchase_id` | References the same book entity |

**Resolution:** Join on `books_info.book_id = review.purchase_id` — same values, different column names.

### crmarenapro — ID corruption (~25% of records)
| Issue | Format | Example |
|---|---|---|
| Clean ID | Standard Salesforce ID | `001Wt00000PFj4zIAD` |
| Corrupted ID | Leading `#` prefix | `#001Wt00000PFj4zIAD` |

**Resolution:** Strip leading `#` from all ID fields before joining.
```python
def normalize_crm_id(raw_id):
    """Strip leading # from corrupted Salesforce IDs."""
    s = str(raw_id).strip()
    return s.lstrip('#')
```
**Affected fields:** Id, AccountId, ContactId across all 6 CRM databases.

### crmarenapro — text field trailing whitespace (~20%)
| Issue | Example |
|---|---|
| Clean value | `"Company Name"` |
| Corrupted value | `"Company Name   "` |

**Resolution:** `.strip()` all string fields before comparison or join.
**Affected fields:** Name, FirstName, LastName, Email, Subject, Status.

### patents — hierarchical CPC code lookup
| Database | Column | Format | Example |
|---|---|---|---|
| SQLite (publicationinfo) | CPC field | Full CPC code | `H04L67/10` |
| PostgreSQL (cpc_definition) | code | Hierarchical codes | `H`, `H04`, `H04L`, `H04L67/10` |

**Resolution:** Match publication CPC codes against the hierarchical tree. May need prefix matching for parent categories.

### github_repos — owner/repo format
| Database | Column | Format |
|---|---|---|
| SQLite (repos, languages, licenses) | repo name | `owner/repo` string |
| DuckDB (commits, contents, files) | repo name | `owner/repo` string |

**Resolution:** Format is consistent, but matching requires exact string match including case sensitivity.

### pancancer_atlas — ParticipantBarcode
| Database | Column | Format | Example |
|---|---|---|---|
| PostgreSQL (clinical_info) | ParticipantBarcode | TCGA barcode | `TCGA-XX-XXXX` |
| DuckDB (Mutation_Data) | ParticipantBarcode | TCGA barcode | `TCGA-XX-XXXX` |
| DuckDB (RNASeq_Expression) | ParticipantBarcode | TCGA barcode | `TCGA-XX-XXXX` |

**Resolution:** Format is consistent across databases. Main challenge is that molecular tables have sample-level barcodes that may need truncation to patient-level.

---

## Datasets with Clean Keys (no known mismatch)
- **agnews** — `article_id` consistent between MongoDB and SQLite
- **googlelocal** — `gmap_id` consistent between PostgreSQL and SQLite
- **music_brainz_20k** — `track_id` consistent between SQLite and DuckDB
- **stockindex** — index symbol consistent between SQLite and DuckDB
- **stockmarket** — ticker symbol consistent between SQLite and DuckDB
- **deps_dev_v1** — package identifiers consistent between SQLite and DuckDB

---

## General Detection Heuristic
If a cross-database JOIN returns 0 rows but both individual queries return data:
1. Check column names — are they actually different names for the same key?
2. Check for prefix/suffix differences in values
3. Check for leading `#` or trailing whitespace corruption
4. Check type differences (int vs string)
5. Check case sensitivity
6. Sample 5 keys from each side and visually compare

## General Normalization Pattern
```python
def normalize_key(raw_key, dataset):
    """Universal key normalizer."""
    s = str(raw_key).strip()
    s = s.lstrip('#')
    if dataset == 'yelp':
        for prefix in ['businessid_', 'businessref_']:
            if s.startswith(prefix):
                s = s[len(prefix):]
    return s
```
