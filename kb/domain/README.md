# KB v2 — Domain Knowledge Base

Documents in this directory provide the agent with working knowledge of:

- DAB dataset schemas (all 12 datasets)
- Known query patterns across database types
- Ill-formatted join key glossary
- Unstructured field inventory
- Domain term definitions per dataset
- Dataset-specific domain knowledge (yelp, bookreview, stockindex)

## Documents

- [x] dab_schemas.md — All 12 DAB datasets with DB types, tables, columns, cross-DB keys
- [x] query_patterns.md — 10 query patterns (cross-DB join, MongoDB, DuckDB, PostgreSQL, SQLite, CRM corruption, hierarchical CPC, text extraction, null handling, large tables)
- [x] join_keys.md — Real DAB key mismatches (yelp prefix, CRM # corruption, bookreview name mismatch)
- [x] unstructured_fields.md — All text fields across 12 datasets, ranked by complexity
- [x] domain_terms.md — CRM, finance, biomedical, patent, software domain terms
- [x] yelp.md — Yelp-specific domain knowledge: schema quirks, parsing rules, and query strategies
- [x] stockindex.md — StockIndex-specific patterns: volatility, up-day definition, DCA methodology, answer format
- [x] bookreview.md — BookReview-specific patterns: cross-DB join, category parsing, year extraction, rating queries

## Injection Test Results

See `injection_tests/test_results.md` — 7/7 PASS
