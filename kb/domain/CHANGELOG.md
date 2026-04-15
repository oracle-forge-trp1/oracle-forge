# Changelog — kb/domain

## 2026-04-09
- Initial directory created; domain KB scope defined — DAB schemas, join key glossary, unstructured field inventory, domain terms

## 2026-04-10
- `dab_schemas.md` drafted — all 12 DAB datasets documented with DB types (PostgreSQL, MongoDB, SQLite, DuckDB), table structures, and primary join key formats
- `join_keys.md` drafted — cross-database join key format mismatches catalogued for 7 datasets; includes yelp businessid_N ↔ businessref_N map, CRM # corruption pattern, and normalization code
- `query_patterns.md` drafted — 10 patterns documented: cross-DB join (Pattern 1), MongoDB aggregation (Pattern 2), DuckDB TRY_STRPTIME mixed dates (Pattern 3), PostgreSQL JSONB (Pattern 4), SQLite (Pattern 5), CRM key corruption (Pattern 6), hierarchy flattening (Pattern 7), unstructured text extraction (Pattern 8), null handling (Pattern 9), large table pagination (Pattern 10)

## 2026-04-11
- `domain_terms.md` drafted — CRM lead/opportunity/pipeline definitions, finance position/drawdown/alpha terms, biomedical variant classification codes, patent CPC codes, software dependency scoping, review sentiment terms, music ISRC/ISWC formats, news category codes
- `unstructured_fields.md` drafted — all 12 datasets ranked by unstructured field complexity; extraction approach documented per field type (regex, NLP, structured parsing)
- `yelp-domain.md` drafted — Yelp-specific rules: state/city extraction from unstructured description field, attribute serialisation format (u'value' strings), date COALESCE pattern for three mixed formats, category parsing, cross-DB join key translation, 7 DAB queries with ground truth answers and solution approaches
- Yonas committed all domain documents at Day 4 mob session

## 2026-04-13
- 7 injection tests run against domain KB documents; 6 pass on first attempt
- `domain_terms.md` Test 7 (biomedical Variant_Classification) initially failed — document revised to include explicit code table; re-test passed
- All injection test results documented in `injection_tests/test_results.md`
- `README.md` updated to reflect actual document list (6 docs, not 3 originally planned)
