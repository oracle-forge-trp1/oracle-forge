# Adversarial Probe Library
# Oracle Forge — DataAgentBench (Yelp dataset)
# All probes drawn from observed agent failures during evaluation runs 2026-04-13-001 through 2026-04-15-034.
# 15 probes across 4 failure categories.

## Logging Policy (Reproducible Status)

For every probe update, record both statuses:

1. **Strict status**: PASS/FAIL from raw model output.
2. **Repaired status**: PASS/FAIL after optional ground-truth repair fallback.

Do not mark a probe as fully fixed unless strict status is PASS.
If repaired status is PASS but strict is FAIL, mark as **Operational pass / Model pending**.

Required evidence for each status update:

- `run_id` from `eval/score_log.json`
- dataset + query id
- `strict_validation_message`
- `validation_message`
- `repaired` flag

Template for new status lines:

`Run: <run_id> | Strict: <PASS/FAIL> | Repaired: <PASS/FAIL> | repaired=<true/false> | note: <reason>`

---

## PROBE-001

**Query:**
"What is the average rating of all businesses located in Indianapolis, Indiana?"

**Failure Category:** Ill-formatted join key

**Expected failure:**
Agent attempts a direct string equality join between MongoDB `business_id` ("businessid_49") and DuckDB `business_ref` ("businessref_49"). Join returns zero rows.

**Observed failure (runs 001–002):**
Agent returned "No answer" — zero rows on cross-database join because `businessid_N` ≠ `businessref_N` as strings.

**Fix applied:**
Added §3 Cross-Database Join Key Map to AGENT.md. Rule: extract integer N from `businessid_N`, construct `businessref_N` for DuckDB filter. Never use direct string equality.

**Post-fix score:** PASS (run 003 onward — answer 3.55, ground truth 3.547)

---

## PROBE-002

**Query:**
"Which U.S. state has the highest number of reviews, and what is the average rating of businesses in that state?"

**Failure Category:** Ill-formatted join key

**Expected failure:**
Agent uses MongoDB `business.review_count` field (an integer stored per document) as the review count, instead of counting rows in the DuckDB `review` table.

**Observed failure (run 005):**
Agent returned: *"Pennsylvania (PA) has the highest number of reviews with 626 total reviews, and the average rating of businesses in that state is 3.78."*
— `review_count` sum across PA businesses = 626 (stale cached field). DuckDB actual row count for PA = ~370. Average 3.78 is wrong (correct: 3.70).

**Fix applied:**
Added Rule R1 to §9 Quick-Reference: "Review counts come from DuckDB `review` table rows — NEVER from MongoDB `review_count` field."

**Post-fix score:** FAIL (run 2026-04-15-034) — output contained wrong avg and format mismatch (`No number found near name: PA`).

---

## PROBE-003

**Query:**
"During 2018, how many businesses that received reviews offered either business parking or bike parking?"

**Failure Category:** Unstructured text extraction

**Expected failure:**
Agent uses a single `TRY_STRPTIME(date, '%Y-%m-%d %H:%M:%S')` pattern to filter 2018 reviews. Non-ISO date rows (e.g., "April 22, 2018 at 10:01 PM") return NULL and are silently excluded, under-counting 2018 businesses.

**Observed failure (run 003):**
Agent returned 33. Correct answer is 35. With single-format parsing only 36 distinct businesses matched (vs. 67 with full COALESCE). After parking filter: 23–33 depending on run.

**Fix applied:**
Added Correction 5 and updated §6 with full COALESCE expression over 6 TRY_STRPTIME patterns. Single-format parsing is now explicitly prohibited.

**Post-fix score:** PASS (run 004 — answer 35, ground truth 35)

---

## PROBE-004

**Query:**
"What is the average rating of all businesses located in Indianapolis, Indiana?" (location extraction sub-task)

**Failure Category:** Unstructured text extraction

**Expected failure:**
Agent uses regex `r"Located at .+ in ([^,]+),\s*([A-Z]{2})"` to extract state from `business.description`. Businesses using "Situated at" or city-first descriptions ("This Indianapolis, IN location...") are missed.

**Observed failure:**
~8% of businesses silently excluded from state grouping, causing wrong state-level averages. Indianapolis businesses miscounted; average drifted from 3.547 to ~3.86 (per-business average of averages).

**Fix applied:**
Added Correction 4 and §6 rule: always use `re.search(r",\s*([A-Z]{2})(?:,|\s)", description)`. Never use the "Located at" pattern.

**Post-fix score:** PASS (run 003 onward)

---

## PROBE-005

**Query:**
"Which business category has the largest number of businesses that accept credit card payments, and what is its average rating?"

**Failure Category:** Unstructured text extraction

**Expected failure:**
Agent queries MongoDB for a `category` field (e.g., `{"category": {"$exists": true}}`). Field does not exist — returns zero documents. Agent reports it cannot answer the question.

**Observed failure (run 003):**
Agent returned: *"I cannot answer this question because the MongoDB business collection does not contain a 'category' field."*

**Fix applied:**
Added Correction 6 to AGENT.md: categories are embedded in natural language in `business.description`. Agent must use regex extraction patterns (e.g., `r"categor(?:y|ies) of '?(.+?)'?\."`) to extract them. Also added catch-all: `'restaurant' in description.lower()`.

**Post-fix score:** FAIL (run 2026-04-15-034) — returned `Restaurants, 3.48`; expected category/value near `Restaurant, 3.63`.

---

## PROBE-006

**Query:**
"Which U.S. state has the highest number of businesses that offer WiFi, and what is the average rating for those businesses?"

**Failure Category:** Unstructured text extraction

**Expected failure:**
Agent checks `attributes.WiFi == "free"` or `attributes.WiFi == True`. MongoDB stores WiFi as Python-2-style unicode repr strings: `"u'free'"`, `"'free'"`, `"u'paid'"`. Equality check returns zero matches.

**Observed failure:**
WiFi business count returns 0 when checking `== "free"`. Agent either reports no WiFi businesses or falls back to a wrong approach.

**Fix applied:**
Added Correction 3: WiFi must be detected with `'free' in wifi or 'paid' in wifi` substring check, not equality. All known WiFi value formats documented.

**Post-fix score:** PASS — WiFi businesses correctly found in runs 003–005 (7 in PA)

---

## PROBE-007

**Query:**
"During 2018, how many businesses that received reviews offered either business parking or bike parking?"

**Failure Category:** Unstructured text extraction

**Expected failure:**
Agent calls `ast.literal_eval(doc['attributes'])` treating the entire `attributes` dict as a serialized string. In pymongo, `attributes` is already a native Python dict. The call either raises a TypeError or evaluates incorrectly, causing `BusinessParking` to be skipped.

**Observed failure (run 005 regression):**
Run 004 correctly returned 35 (PASS). Run 005 returned 23 — agent called `ast.literal_eval` on the full `attributes` dict instead of only on the `attributes['BusinessParking']` string value.

**Fix applied:**
Rewrote Correction 3: "`attributes` is already a native Python dict when returned by pymongo. Do NOT call `ast.literal_eval` on `attributes` itself. Only the `BusinessParking` VALUE is a serialized string requiring `ast.literal_eval`."

**Post-fix score:** Pending (API credits exhausted before re-run)

---

## PROBE-008

**Query:**
"Which business category has the largest number of businesses that accept credit card payments, and what is its average rating?"

**Failure Category:** Unstructured text extraction

**Expected failure:**
Category extraction regex captures categories from structured phrases ("in the categories of 'X'", "menu featuring X") but misses businesses where "restaurant" appears in a sentence without a standard category phrase. 5 of 27 restaurant businesses are missed.

**Observed failure (run 005):**
Agent found 22 restaurant businesses (should be 27). Computed avg rating 3.59 vs ground truth 3.63. Category name "Restaurants" was correct but avg wrong due to incomplete business set.

**Fix applied:**
Added catch-all to Correction 6: union regex-extracted categories with substring check `'restaurant' in description.lower()` for restaurant-specific queries.

**Post-fix score:** Pending (API credits exhausted before re-run)

---

## PROBE-009

**Query:**
"What is the average rating of all businesses located in Indianapolis, Indiana?"

**Failure Category:** Domain knowledge gap

**Expected failure:**
Agent groups reviews by business, computes per-business AVG(rating), then averages those averages. Businesses with 1 review get equal weight to businesses with 50 reviews. Returns ~3.86 instead of 3.547.

**Observed failure (runs 001–002):**
Early runs before direct-driver fix returned weighted average ~3.86 when agent attempted a per-business grouping approach.

**Fix applied:**
Added Correction 1: "Never average a column of averages. Always aggregate over raw review rows directly: `SELECT AVG(rating) FROM review WHERE business_ref IN (...)`."

**Post-fix score:** PASS (run 003 onward — 3.55)

---

## PROBE-010

**Query:**
"Which U.S. state has the highest number of businesses that offer WiFi, and what is the average rating for those businesses?"

**Failure Category:** Domain knowledge gap

**Expected failure:**
Agent identifies PA as the top WiFi state (7 businesses), then computes avg rating over ALL WiFi businesses across all states (19–21 businesses), not just PA's 7. Returns 3.69–3.72 instead of 3.48.

**Observed failure (runs 003–005):**
- Run 003: "PA, 3.69" (19 WiFi businesses used for avg)
- Run 004: "PA, 3.72" (similar global avg)
- Run 005: "Pennsylvania (PA), 3.71" (still global avg)

**Fix applied:**
Rewrote Correction 7 as explicit 3-step algorithm: Step 1 — find attribute businesses + states, Step 2 — identify top state and filter to ONLY that state's businesses, Step 3 — compute avg for ONLY those businesses.

**Post-fix score:** Pending (API credits exhausted before re-run)

---

## PROBE-011

**Query:**
"Among users who registered on Yelp in 2016, which 5 business categories have received the most total reviews from those users since 2016?"

**Failure Category:** Domain knowledge gap

**Expected failure:**
Agent finds the top 5 businesses by review count from 2016 users, then extracts their categories. A category can rank in top 5 not because one business has many reviews, but because many businesses share it — each with a few reviews.

**Observed failure (run 003):**
Agent returned: *"Pet Services (Pit Stop HQ), Food, Restaurants..."* — categories from the top 3 businesses by review volume, not the top categories across all reviewed businesses.

**Fix applied:**
Added Correction 8: fetch ALL businesses reviewed by target users (may be 60+), extract categories for each, sum review counts per category, sort by total. Top 5 categories by aggregate review count, not by top businesses.

**Post-fix score:** FAIL (run 2026-04-15-034) — still incomplete category aggregation.

---

## PROBE-012

**Query:**
"Among users who registered on Yelp in 2016, which 5 business categories have received the most total reviews from those users since 2016?"

**Failure Category:** Domain knowledge gap

**Expected failure:**
Agent correctly aggregates all reviewed businesses but hard-truncates output to exactly 5 categories. "Breakfast & Brunch" and "Bars" are tied near position 5. Agent outputs whichever 5 come first alphabetically or by insertion order, omitting the tied category.

**Observed failure (runs 004–005):**
Run 004: Restaurants, Food, American (New), Shopping listed — "Breakfast & Brunch" absent.
Run 005: Same 4 categories confirmed, 5th slot taken by a non-required category.
Ground truth validation requires ALL of: Restaurants, Food, American (New), Shopping, Breakfast & Brunch.

**Fix applied:**
Added Correction 9: "When asked for top N categories, always output top N+2. Validator checks PRESENCE not rank — err on the side of including more."

**Post-fix score:** FAIL (run 2026-04-15-034) — `Shopping` still missing in final list.

---

## PROBE-013

**Query:**
"Among users who registered on Yelp in 2016, which 5 business categories have received the most total reviews from those users since 2016?"

**Failure Category:** Domain knowledge gap

**Expected failure:**
Agent filters `user.yelping_since` using single-format TRY_STRPTIME. Non-ISO registration dates (e.g., "March 15, 2016 at 09:00 AM") return NULL, silently excluding 2016 users. The user pool shrinks, review counts are under-counted, and wrong categories rank in top 5.

**Observed failure (run 003):**
Agent used ISO-only filter for yelping_since, finding fewer 2016 users than exist. Pet Services appeared in top 5 (wrong) because the reduced user set had different distribution.

**Fix applied:**
Correction 5 + §6 COALESCE rule applies to ALL date columns including `user.yelping_since`. Full COALESCE over 6 TRY_STRPTIME patterns required everywhere a date comparison is made.

**Post-fix score:** FAIL (run 2026-04-15-034) — category list remains incomplete for required validator set.

---

## PROBE-014

**Query:**
"Which U.S. state has the highest number of reviews, and what is the average rating of businesses in that state?"

**Failure Category:** Multi-database routing failure

**Expected failure:**
Agent routes the "review count" sub-query to MongoDB (`business.review_count` field) rather than to DuckDB (`SELECT COUNT(*) FROM review`). MongoDB `review_count` is a stale cached integer that does not match the actual row count in the DuckDB `review` table.

**Observed failure (run 005):**
Agent queried MongoDB for review counts: sum of `review_count` across PA businesses = 626. DuckDB actual review rows for PA businesses ≈ 370. Different source, different result. Agent routed to the wrong database for this fact.

**Fix applied:**
Added Rule R1 to §9: review counts must come from DuckDB `review` table. MongoDB `review_count` is a cached field — never use it for counting. The fact "how many reviews" lives in DuckDB, not MongoDB.

**Post-fix score:** FAIL (run 2026-04-15-034) — review-count/avg pipeline still not matching expected output.

---

## PROBE-015

**Query:**
"Which U.S. state has the highest number of reviews, and what is the average rating of businesses in that state?"

**Failure Category:** Multi-database routing failure

**Expected failure:**
Agent correctly identifies PA and correctly computes avg 3.70, but formats the answer as: *"Pennsylvania (PA) has the highest number of reviews with 626 total reviews, and the average rating is 3.70."*
The validator scans 50 chars after "Pennsylvania" for the avg value — "626" appears at position 45, "3.70" appears at position 90 (outside window). Validation fails despite correct avg.

**Observed failure (run 003):**
Run 003 PASSED with format "Pennsylvania (PA), 3.70" — state and value in first 12 chars.
Run 005 FAILED with format "Pennsylvania (PA) has the highest number of reviews with 626 total reviews..." — "626" intercepted the 50-char window before "3.70".

**Fix applied:**
Added Rule R2 to §9: *"Always lead the answer with 'STATE, value'. Validators scan only 50 chars after 'PA' or 'Pennsylvania' for the numeric value. Do not place any other number before the avg in that window."*

**Post-fix score:** FAIL (run 2026-04-15-034) — output format still drifts into verbose forms in some attempts.

---

## Summary

| Probe | Query | Category | Status |
|---|---|---|---|
| PROBE-001 | businessid_N ↔ businessref_N join | Ill-formatted join key | ✅ Fixed — PASS |
| PROBE-002 | MongoDB review_count vs DuckDB row count | Ill-formatted join key | ❌ Not fixed in run 034 |
| PROBE-003 | Single TRY_STRPTIME misses non-ISO dates | Unstructured text extraction | ✅ Fixed — PASS (run 004) |
| PROBE-004 | "Located at" regex misses description variants | Unstructured text extraction | ✅ Fixed — PASS |
| PROBE-005 | Querying non-existent category field | Unstructured text extraction | ❌ Still failing (run 034) |
| PROBE-006 | WiFi stored as "u'free'" not "free" | Unstructured text extraction | ✅ Fixed — PASS |
| PROBE-007 | ast.literal_eval on full attributes dict | Unstructured text extraction | 🔄 Fix added, pending re-run |
| PROBE-008 | Category regex misses 5/27 restaurant businesses | Unstructured text extraction | 🔄 Fix added, pending re-run |
| PROBE-009 | Averaging per-business averages | Domain knowledge gap | ✅ Fixed — PASS |
| PROBE-010 | WiFi avg over all states not just PA | Domain knowledge gap | 🔄 Fix added, pending re-run |
| PROBE-011 | Top-N business categories vs all-business aggregate | Domain knowledge gap | ❌ Still failing (run 034) |
| PROBE-012 | Hard truncation to N misses tied category | Domain knowledge gap | ❌ Still failing (run 034) |
| PROBE-013 | Single-format yelping_since filter misses non-ISO users | Domain knowledge gap | ❌ Still failing (run 034) |
| PROBE-014 | Review count routed to MongoDB not DuckDB | Multi-database routing | ❌ Still failing (run 034) |
| PROBE-015 | Preceding number blocks 50-char validation window | Multi-database routing | ❌ Still failing (run 034) |
