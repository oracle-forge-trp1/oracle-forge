# Domain KB — Changelog

## 2026-04-09 — v2.0 Complete Rewrite (Corrected to Real DAB Datasets)

### Critical Fix
- **v1.0 contained fabricated datasets** (Retail, Telecom, Healthcare, Finance/AML) that do not exist in DataAgentBench
- All 5 documents rewritten from scratch using actual DAB repository data (db_config.yaml + db_description.txt for each of the 12 real datasets)

### Changed — dab_schemas.md
- Removed 4 fabricated datasets (Retail, Telecom, Healthcare, Finance/AML)
- Added all 12 real DAB datasets: agnews, bookreview, crmarenapro, deps_dev_v1, github_repos, googlelocal, music_brainz_20k, pancancer_atlas, patents, stockindex, stockmarket, yelp
- Each dataset: domain, DB types, tables/collections, columns, cross-DB join keys, known issues
- Added DB type distribution summary
- Source: raw db_config.yaml and db_description.txt from github.com/ucbepic/DataAgentBench

### Changed — join_keys.md
- Removed generic format examples (integer vs prefixed string patterns)
- Added dataset-specific real mismatches: yelp business_id/business_ref prefix mismatch, bookreview book_id/purchase_id name mismatch, crmarenapro leading `#` corruption and trailing whitespace
- Added patents hierarchical CPC lookup pattern
- Listed datasets with clean keys (no mismatch)
- Source: db_description_withhint.txt files from DAB repo

### Changed — unstructured_fields.md
- Rewrote for all 12 real datasets
- Added complexity ranking by dataset
- Identified github_repos and crmarenapro as highest complexity
- Noted datasets with no significant text fields (music_brainz, stockindex)
- Added per-dataset extraction approaches

### Changed — domain_terms.md
- Removed fabricated terms (Telecom churn, Healthcare ICD, AML structuring definitions)
- Added real dataset-specific terms: CRM (Lead, Opportunity, Case, Account/Contact, Territory), Finance/Stock (OHLC, Adjusted Close, Market Category), Biomedical (ParticipantBarcode, Hugo_Symbol, Variant_Classification, Cancer Type Acronyms), Patents (CPC hierarchy, citations), Software (package ecosystem, security advisory, license SPDX)
- Added cross-dataset temporal terms and data currency notes

### Changed — query_patterns.md
- Updated cross-database join example to use real yelp dataset
- Updated MongoDB examples for real agnews/yelp collections
- Added CRM ID corruption handling pattern (crmarenapro)
- Added hierarchical CPC lookup pattern (patents)
- Added large table query pattern (stockmarket 2,754 securities)
- Updated DB type lists per pattern with real dataset names

### Injection Tests
- 7 new tests designed for v2.0 documents
- All marked PENDING — must be re-run before final commit

### Sources
- DataAgentBench repository: github.com/ucbepic/DataAgentBench
- db_config.yaml files for all 12 datasets (raw GitHub)
- db_description.txt files for all 12 datasets (raw GitHub)
- db_description_withhint.txt for crmarenapro and yelp

---

## 2026-04-09 — v1.0 Initial Release (SUPERSEDED)

### Added
- dab_schemas.md — Schema descriptions for 5 fabricated datasets
- query_patterns.md — 6 query patterns
- join_keys.md — Generic format mismatch glossary
- unstructured_fields.md — Text fields for fabricated datasets
- domain_terms.md — Terms for fabricated datasets

### Notes
- **This version was incorrect.** It contained fabricated dataset schemas not present in DAB. Fully replaced by v2.0.
