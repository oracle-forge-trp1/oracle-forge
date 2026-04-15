# Domain KB — Injection Test Results

## Test Protocol
Fresh LLM session with only the document as context. Ask a question it should answer. Grade pass/fail.

---

## Test 1: dab_schemas.md (multi-DB structure)

**Question:** "How many databases does the crmarenapro dataset use, and what are their types?"

**Expected:** 6 databases: core_crm (SQLite), sales_pipeline (DuckDB), support (PostgreSQL), products_orders (SQLite), activities (DuckDB), territory (SQLite).

**Result:** PASS — LLM correctly identified all 6 databases with exact types.

**Date:** 2026-04-09

---

## Test 2: dab_schemas.md (cross-DB key)

**Question:** "In the yelp dataset, what is the join key mismatch between MongoDB and DuckDB?"

**Expected:** business_id in MongoDB uses prefix `businessid_X`, while DuckDB uses `business_ref` with prefix `businessref_X`. Must strip prefixes to match.

**Result:** PASS — LLM correctly identified both column names, prefix formats, and the need to strip prefixes.

**Date:** 2026-04-09

---

## Test 3: query_patterns.md (MongoDB pattern)

**Question:** "If I need to count items grouped by a field in a MongoDB collection, what query pattern should I use? Show an example."

**Expected:** Use MongoDB aggregation pipeline with $match, $group (with $sum), $sort. NOT SQL. Example: `db.collection.aggregate([{$group: {_id: "$group_field", total: {$sum: 1}}}, {$sort: {total: -1}}])`.

**Result:** PASS — LLM produced correct aggregation pipeline syntax from Pattern 2 in the document.

**Date:** 2026-04-09

---

## Test 4: join_keys.md (CRM corruption)

**Question:** "What data quality issues affect join keys in the crmarenapro dataset?"

**Expected:** ~25% of ID fields have leading `#` prefix (e.g., `#001Wt00000PFj4zIAD`). ~20% of text fields have trailing whitespace. Must strip `#` and trim whitespace before any joins. Affected fields: Id, AccountId, ContactId, Name, FirstName, LastName, Email, Subject, Status.

**Result:** PASS — LLM correctly identified both corruption types, percentages, resolution steps, and all affected fields.

**Date:** 2026-04-09

---

## Test 5: unstructured_fields.md (complexity ranking)

**Question:** "Which dataset has the highest unstructured text complexity and what are its key text fields?"

**Expected:** github_repos (High complexity). Key fields: contents.content (file content), commits.message (commit messages), commits.difference (file change diffs) — all in DuckDB.

**Result:** PASS — LLM identified github_repos as rank 1 with all three key fields correctly.

**Date:** 2026-04-09

---

## Test 6: domain_terms.md (CRM terms)

**Question:** "What is the difference between a Lead and an Opportunity in the crmarenapro dataset?"

**Expected:** A Lead is a potential customer who has expressed interest but not yet converted (Status: Open, Qualified, Converted, Closed). An Opportunity is a qualified sales deal in the pipeline with an estimated close date and amount — further down the funnel than a lead.

**Result:** PASS — LLM accurately distinguished both terms with all key attributes.

**Date:** 2026-04-09

---

## Test 7: domain_terms.md (biomedical)

**Question:** "What is a Variant_Classification of Missense_Mutation in the pancancer_atlas dataset?"

**Expected:** A point mutation that changes the amino acid. When filtering for "damaging" mutations, typically exclude Silent variants. Found in the Mutation_Data table in the molecular_database (DuckDB).

**Result:** PASS (after fix) — Initial test FAILED because location info was missing from doc. Added "Location: Mutation_Data table in molecular_database (DuckDB)" to domain_terms.md. Re-test confirms LLM now produces complete answer.

**Date:** 2026-04-09

---

## Summary
- **Total tests:** 7
- **Passed:** 7 (1 after doc fix)
- **Failed:** 0
- **Test 3 redesigned:** Original question required cross-document knowledge (agnews region field location). Replaced with a question answerable from query_patterns.md alone.
- **Test 7 fix applied:** Added table/database location to Variant_Classification entry in domain_terms.md.
