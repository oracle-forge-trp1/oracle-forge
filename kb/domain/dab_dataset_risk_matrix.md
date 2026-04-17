# DAB Dataset Risk Matrix (Leakage-Safe)

Source:
- Built from dataset topology and DB configuration under DataAgentBench.
- No query text, no expected answers, no ground-truth values.

Goals:
- Help routing/planning quality.
- Highlight likely failure classes per dataset.

---

## Summary

- Datasets: 12
- Query folders: 54
- DB type coverage:
  - sqlite: 12 logical clients
  - duckdb: 9 logical clients
  - postgres: 5 logical clients
  - mongo: 2 logical clients

Primary benchmark risks:
1. Cross-DB join normalization
2. Unstructured text extraction
3. Mixed/dirty data typing
4. Aggregation and ranking correctness
5. Output-shape validation sensitivity

---

## Dataset Matrix

| Dataset | Query Count | DB Types | Primary Risks | Recommended Safeguards |
|---|---:|---|---|---|
| agnews | 4 | mongo, sqlite | Text filtering drift, cross-store id mapping | normalize ids, keyword extraction sanity checks |
| bookreview | 3 | postgres, sqlite | Cross-DB key mismatch, text-derived year/category parsing | join-key normalization, regex fallback, date-window checks |
| crmarenapro | 13 | duckdb, postgres, sqlite | ID corruption, trailing whitespace, multi-store joins | canonical id cleaning, trim text keys, join cardinality audits |
| deps_dev_v1 | 2 | duckdb, sqlite | Package/version matching, sparse joins | strict key normalization, null-safe joins |
| github_repos | 4 | duckdb, sqlite | Large unstructured code/commit text, aggregation completeness | staged extraction, top-N after full aggregation |
| googlelocal | 4 | postgres, sqlite | Text-based business/review attributes, join precision | consistent key typing, text parsing with fallback |
| music_brainz_20k | 3 | duckdb, sqlite | Multi-entity aggregation and deduplication | dedupe entities before grouping, weighted aggregates |
| pancancer_atlas | 3 | duckdb, postgres | Bio/clinical join integrity, missing data handling | explicit null policy, cross-table key audits |
| patents | 3 | postgres, sqlite | Hierarchical code matching and text normalization | hierarchy-aware filters, prefix-safe matching |
| stockindex | 3 | duckdb, sqlite | Time-series parsing, winner-only output shape | robust date parsing, strict output compactness |
| stockmarket | 5 | duckdb, sqlite | Large-table cost and ranking consistency | early filters, bounded scans, deterministic ordering |
| yelp | 7 | duckdb, mongo | Unstructured attributes/location, cross-DB key prefixes | parser fallback, type normalization, row-level aggregation |

---

## Operational Guidance

1. Before query execution:
- Identify DB types involved.
- Confirm join key canonicalization strategy.
- Define null and type-cast policy.

2. During execution:
- Validate row counts at each stage.
- Use bounded result sets with deterministic ordering.
- Keep tool traces concise and reproducible.

3. Before final answer:
- Verify output shape matches expected validator style.
- Avoid extra entities for single-winner tasks.
- Prefer compact plain text output.
