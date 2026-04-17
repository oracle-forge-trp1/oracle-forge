# Domain KB — Injection Test Results

## Test Protocol

Fresh LLM session with only the document as context. Ask a question it should answer. Grade pass/fail.

---

## Test 1: dab_schemas.md (multi-DB structure)

**Question:** "How many databases does the crmarenapro dataset use, and what are their types?"

**Expected:** 6 databases: core_crm (SQLite), sales_pipeline (DuckDB), support (PostgreSQL), products_orders (SQLite), activities (DuckDB), territory (SQLite).

**Result:** PASS — LLM correctly identified all 6 databases with exact types.

**Date:** 2026-04-15

---

## Test 2: dab_schemas.md (cross-DB key)

**Question:** "In the yelp dataset, what is the join key mismatch between MongoDB and DuckDB?"

**Expected:** business_id in MongoDB uses prefix `businessid_X`, while DuckDB uses `business_ref` with prefix `businessref_X`. Must strip prefixes to match.

**Result:** PASS — LLM correctly identified both column names, prefix formats, and the need to strip prefixes.

**Date:** 2026-04-15

---

## Test 3: query_patterns.md (MongoDB pattern)

**Question:** "If I need to count items grouped by a field in a MongoDB collection, what query pattern should I use?"

**Expected:** Use MongoDB aggregation pipeline with $match, $group (with $sum), $sort. NOT SQL.

**Result:** PASS — LLM produced correct aggregation pipeline syntax.

**Date:** 2026-04-15

---

## Test 4: join_keys.md (CRM corruption)

**Question:** "What data quality issues affect join keys in the crmarenapro dataset?"

**Expected:** ~25% of ID fields have leading `#` prefix. ~20% of text fields have trailing whitespace. Must strip `#` and trim whitespace before joins. Affected fields: Id, AccountId, ContactId, Name, FirstName, LastName, Email, Subject, Status.

**Result:** PASS — LLM correctly identified both corruption types, percentages, and all affected fields.

**Date:** 2026-04-15

---

## Test 5: unstructured_fields.md (complexity ranking)

**Question:** "Which dataset has the highest unstructured text complexity and what are its key text fields?"

**Expected:** github_repos (High complexity). Key fields: contents.content (file content), commits.message (commit messages), commits.difference (file change diffs) — all in DuckDB.

**Result:** PASS — LLM identified github_repos as rank 1 with all three key fields correctly.

**Date:** 2026-04-15

---

## Test 6: domain_terms.md (CRM terms)

**Question:** "What is the difference between a Lead and an Opportunity in the crmarenapro dataset?"

**Expected:** A Lead is a potential customer who has expressed interest but not yet converted. An Opportunity is a qualified sales deal in the pipeline — further down the funnel than a lead.

**Result:** PASS — LLM accurately distinguished both terms.

**Date:** 2026-04-15

---

## Test 7: yelp-domain.md (Yelp-specific)

**Question:** "How do you extract the state from a Yelp business record, and why can't you just query a state field?"

**Expected:** MongoDB business collection has no `city`, `state`, or `address` fields. Location is embedded in the `description` text field. Extract using regex `r"Located at .+? in (.+?),\s*([A-Z]{2})"`. In MongoDB aggregation, use `$regexFind` on `description`.

**Result:** PASS — LLM correctly explained the missing structured fields and provided the regex extraction approach.

**Date:** 2026-04-15

---

## Test 8: crmarenapro.md (data corruption)

**Question:** "What data corruption issues exist in the crmarenapro dataset and how should you handle them before joining?"

**Expected:** ~25% ID fields have leading `#` prefix, ~20% text fields have trailing whitespace, must strip `#` and `.strip()` before joins, affects Id/AccountId/ContactId/Name/Email/Subject/Status.

**Result:** PASS — LLM identified both corruption types with percentages, normalization code, and all affected fields.

**Date:** 2026-04-17

---

## Test 9: agnews.md (categories)

**Question:** "What are the 4 article categories in the agnews dataset and where is category information stored?"

**Expected:** World, Sports, Business, Science/Technology. Categories determined from title and description content — may require text analysis/classification.

**Result:** PASS — LLM listed all 4 categories and correctly stated they must be determined from article content, not a structured field.

**Date:** 2026-04-17

---

## Test 10: googlelocal.md (join key + timeframe)

**Question:** "What is the join key between the two databases in the googlelocal dataset and what is the data timeframe?"

**Expected:** gmap_id links PostgreSQL business_description to SQLite review, consistent format (no mismatch), data through September 2021.

**Result:** PASS — LLM identified gmap_id, confirmed no prefix mismatch, and stated September 2021 timeframe.

**Date:** 2026-04-17

---

## Test 11: stockmarket.md (scale + performance)

**Question:** "How many securities does the stockmarket dataset contain and what is the key performance concern when querying it?"

**Expected:** 2,754 securities with daily price data, potentially millions of rows, must always filter by ticker and/or date early to avoid full table scans.

**Result:** PASS — LLM stated 2,754 securities, millions of rows, and the need for early filtering with correct GOOD/BAD query examples.

**Date:** 2026-04-17

---

## Test 12: music_brainz_20k.md (entity resolution)

**Question:** "Why can't you just use COUNT(DISTINCT track_id) to count unique tracks in the music_brainz_20k dataset?"

**Expected:** Different track_ids can represent the same real-world track (duplicates from different sources), must perform entity resolution by comparing title+artist, deduplication required before counting.

**Result:** PASS — LLM explained duplicate track_ids, entity resolution requirement, and recommended deduplication by (title, artist).

**Date:** 2026-04-17

---

## Summary

- **Total tests:** 12
- **Passed:** 12
- **Failed:** 0
