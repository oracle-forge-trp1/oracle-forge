# Domain KB — Changelog

## 2026-04-15 — Sprint 2 Dataset KB Files Added

- `yelp-domain.md` renamed to `yelp.md` — aligns with agent lookup pattern `kb/domain/{dataset}.md`
- `stockindex.md` created — consolidates corrections 006-009, volatility/up-day/DCA patterns, DB schema
- `bookreview.md` created — cross-DB join key, category parsing, year extraction, PostgreSQL patterns

## 2026-04-13 — v2.0 Complete Rewrite (Corrected to Real DAB Datasets)

### Critical Fix
- **v1.0 contained fabricated datasets** (Retail, Telecom, Healthcare, Finance/AML) that do not exist in DataAgentBench
- All 5 documents rewritten from scratch using actual DAB repository data (db_config.yaml + db_description.txt for each of the 12 real datasets)

### Added / Updated — dab_schemas.md
- All 12 real DAB datasets: agnews, bookreview, crmarenapro, deps_dev_v1, github_repos, googlelocal, music_brainz_20k, pancancer_atlas, patents, stockindex, stockmarket, yelp
- Each dataset: domain, DB types, tables/collections, columns, cross-DB join keys, known issues

### Added / Updated — join_keys.md
- Real mismatches: yelp businessid_N/businessref_N prefix mismatch, bookreview book_id/purchase_id name mismatch, crmarenapro leading `#` corruption and trailing whitespace
- Listed datasets with clean keys (no mismatch)

### Added / Updated — query_patterns.md
- 10 patterns with real dataset examples (yelp cross-DB join, MongoDB aggregation, DuckDB TRY_STRPTIME, PostgreSQL JSONB, CRM key corruption, hierarchical CPC lookup)

### Added / Updated — domain_terms.md
- Real dataset-specific terms: CRM, Finance/Stock, Biomedical (Variant_Classification), Patents (CPC), Software (package ecosystem, SPDX)

### Added / Updated — unstructured_fields.md
- All 12 real datasets ranked by unstructured field complexity; per-field extraction approaches

### Added — yelp-domain.md (Sprint 1)
- Yelp-specific rules: state/city extraction from description field, attribute serialisation format, date COALESCE pattern, category parsing, cross-DB join key translation, and query solution approaches
- 7 injection tests run; 6 pass immediately, 1 fixed after doc revision (domain_terms.md biomedical codes); all 7 PASS confirmed

## 2026-04-11 — v1.0 Initial Release (SUPERSEDED)

- dab_schemas.md, join_keys.md, query_patterns.md, domain_terms.md, unstructured_fields.md — initial versions
- **This version was incorrect.** It contained fabricated dataset schemas not present in DAB. Fully replaced by v2.0.
- Source: fabricated from LLM knowledge rather than actual DAB files

## 2026-04-09

- Initial directory created; domain KB scope defined — DAB schemas, join key glossary, unstructured field inventory, domain terms
