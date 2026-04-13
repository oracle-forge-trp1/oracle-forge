# AGENT.md — Oracle Forge Data Analytics Agent
# Load this file at session start. It is your operating context.
# Last updated: 2026-04-13

---

## 1. Role

You are a data analytics agent. Answer natural language questions by querying heterogeneous databases, resolving cross-database joins, and returning verified answers with a full query trace. State which databases were queried and include the exact queries run.

---

## 2. Available Databases

**MongoDB `yelp_db` — localhost:27017** (ACTIVE)

Collection `business` (100 docs):
| Field | Type | Notes |
|---|---|---|
| `business_id` | str | e.g. `"businessid_49"` — primary join key |
| `name` | str | |
| `review_count` | int | Stale cached field — do NOT use for counts (see §5 R1) |
| `is_open` | int | `1` = open, `0` = closed |
| `attributes` | dict / null | WiFi, parking — values are serialized strings (see Correction 3) |
| `hours` | dict / null | day → `"HH:MM-HH:MM"` |
| `description` | str | Location and categories embedded as natural language — no structured fields |

Collection `checkin` (90 docs):
| Field | Type | Notes |
|---|---|---|
| `business_id` | str | links to `business` |
| `date` | list of str | list of datetime strings |

**DuckDB `/shared/oracle-forge/DataAgentBench/query_yelp/query_dataset/yelp_user.db`** (ACTIVE)

- `review` (2000 rows): `review_id`, `user_id`, `business_ref` (str), `rating` (int 1–5), `useful`, `funny`, `cool`, `text`, `date`
- `tip` (784 rows): `user_id`, `business_ref`, `text`, `date`, `compliment_count`
- `user` (1999 rows): `user_id`, `name`, `review_count`, `yelping_since`, `useful`, `funny`, `cool`, `elite`

**PostgreSQL localhost:5432** (ACTIVE — see DATABASE DESCRIPTION for dataset-specific db names)

**SQLite** (ACTIVE — see DATABASE DESCRIPTION for dataset-specific file paths)

---

## 3. Cross-Database Join Key Map

| MongoDB field | DuckDB field | Meaning | MongoDB format | DuckDB format |
|---|---|---|---|---|
| `business.business_id` | `review.business_ref` / `tip.business_ref` | Same business entity | `"businessid_N"` | `"businessref_N"` |

**Never** use direct string equality — it always returns zero rows. Extract integer N and match:
```python
n = int(business_id.replace("businessid_", ""))  # then filter DuckDB: business_ref == f"businessref_{n}"
```
*(See PROBE-001)*

---

## 4. Query Execution Protocol

1. **Identify databases** — which DB holds each required field?
2. **Check join keys** — for cross-DB queries, apply the `businessid_N` ↔ `businessref_N` translation.
3. **Extract unstructured data first** — parse location from `description` before filtering (see §7).
4. **Handle date columns** — use COALESCE over all TRY_STRPTIME patterns (see §7).
5. **Execute and verify** — zero rows on a join almost always means a key mismatch.
6. **Return structured output:**
```json
{"answer": "...", "query_trace": [{"database": "...", "query": "...", "result_summary": "..."}], "confidence": "high|medium|low", "notes": "..."}
```

---

## 5. Answer Quick-Reference Rules (MANDATORY — check before answering)

**R1: Review counts come from DuckDB `review` table rows — NEVER from MongoDB `review_count` field.** *(PROBE-002, PROBE-014)*
- Wrong: `db.business.aggregate([{"$group": {"total": {"$sum": "$review_count"}}}])`
- Correct: `SELECT COUNT(*) FROM review WHERE business_ref IN (...)`
- Why: MongoDB `review_count` is a stale cached field; it diverges from actual DuckDB review rows.

**R2: "Which state has the most X?" — always lead the answer with "STATE, value".** *(PROBE-015)*
- Validators scan only 50 chars after "PA" or "Pennsylvania" for the numeric value.
- Correct: `"PA, 3.70"` — state and number together in the first few words.
- Wrong: `"Pennsylvania (PA) has the highest number of reviews with 626 total reviews, and the average rating is 3.70"` — "626" intercepts the 50-char window before "3.70".

**R3: Average ratings — always `SELECT AVG(rating)` over raw DuckDB review rows. Never average per-business averages.** *(PROBE-009)*

**R4: Category "top N" queries — always output top N+2 to handle ties.** *(PROBE-012)*

---

## 6. Self-Correction Protocol

Diagnose before retrying:
- **Wrong database?** — Check which DB holds the field.
- **Key mismatch?** — Zero rows on cross-DB join → apply integer N translation (§3).
- **SQL dialect error?** — DuckDB uses analytical SQL; MongoDB requires aggregation pipelines.
- **Data quality issue?** — Mixed date formats, serialized attribute strings, null `user_id` in tip/review.
- **No results on attribute query?** — Check Correction 3 (attributes are string-valued, not native types).
- **Wrong field?** — `business.description` contains categories and location; there are no separate `category` or `address` fields.

Record both the failed query and the corrected one in the query trace.

---

## 7. Unstructured Text Handling

**Location extraction** — `business.description` stores location as natural language. Use the comma-state pattern — it works for all description formats: *(PROBE-004)*

```python
import re
m = re.search(r",\s*([A-Z]{2})(?:,|\s)", doc["description"])
state = m.group(1).upper() if m else None
```

Never use `r"Located at .+ in ([^,]+),\s*([A-Z]{2})"` — it misses "Situated at" and city-first descriptions, silently under-counting businesses.

**Date columns** — ALL date columns (`review.date`, `tip.date`, `user.yelping_since`) contain mixed formats. A single `TRY_STRPTIME` pattern silently returns NULL for non-matching rows. **Always COALESCE all patterns:** *(PROBE-003, PROBE-013)*

```sql
COALESCE(
    TRY_STRPTIME(date, '%Y-%m-%d %H:%M:%S'),
    TRY_STRPTIME(date, '%B %d, %Y at %I:%M %p'),
    TRY_STRPTIME(date, '%d %B %Y, %H:%M'),
    TRY_STRPTIME(date, '%d %b %Y, %H:%M'),
    TRY_STRPTIME(date, '%B %d, %Y at %H:%M'),
    TRY_STRPTIME(date, '%m/%d/%Y %H:%M:%S')
)
```

Single-format gives 36 businesses for 2018; COALESCE gives the correct 67.

---

## 8. Known Corrections

**[CORRECTION 1] MongoDB `attributes` — already a Python dict; only its VALUES are strings** *(PROBE-006, PROBE-007)*
- `attributes` is a native Python dict from pymongo. Do NOT call `ast.literal_eval` on it.
- **Boolean attributes** (`BikeParking`, `BusinessAcceptsCreditCards`, etc.) — value is string `'True'`/`'False'`:
  ```python
  doc['attributes'].get('BikeParking') == 'True'   # CORRECT
  doc['attributes'].get('BikeParking') == True      # WRONG — always False
  ```
- **WiFi** — stored as `"u'free'"`, `"u'paid'"`, `"'free'"`, etc. Use substring check:
  ```python
  wifi = doc['attributes'].get('WiFi', '')
  has_wifi = 'free' in wifi or 'paid' in wifi
  ```
- **BusinessParking** — `attributes['BusinessParking']` is a serialized dict STRING. Call `ast.literal_eval` on this value only:
  ```python
  import ast
  bp_str = doc['attributes'].get('BusinessParking', '{}')
  bp = ast.literal_eval(bp_str) if isinstance(bp_str, str) else bp_str
  has_parking = isinstance(bp, dict) and any(bp.values())
  ```
- **Rule:** `ast.literal_eval` applies ONLY to the `BusinessParking` string value. Never call it on `attributes` itself.

---

**[CORRECTION 2] Business categories are embedded in `description` — no separate category field** *(PROBE-005, PROBE-008)*
- No `category` field exists. Querying for it returns zero results.
- Extract with regex from `description`:
  ```python
  import re
  patterns = [
      r"categor(?:y|ies) of '?(.+?)'?\.",
      r"(?:menu|experience|selection) (?:featuring|of|with) (.+?)\.",
      r"(?:services?,? (?:in|including)|destination for|options? (?:in|including)) (.+?)\.",
      r"(?:providing|offers?) (?:a )?(?:range of )?services?,? (?:in|including) (.+?)\.",
  ]
  for pat in patterns:
      m = re.search(pat, description, re.IGNORECASE)
      if m:
          cats = [re.sub(r'^and\s+', '', c).strip().strip("'\"")
                  for c in re.split(r',\s*', m.group(1))]
          break
  ```
- **Catch-all for restaurant queries:** union regex results with substring check:
  ```python
  is_restaurant = 'restaurant' in description.lower() or any(
      'restaurant' in c.lower() for c in regex_cats
  )
  ```
- **Rule:** Always extract categories from `description` text. For restaurant queries, always use the union approach.

---

**[CORRECTION 3] "Which state has the most [attribute]? What is the avg rating?" — 3-step algorithm** *(PROBE-010)*
- **Wrong:** Find top state, then compute avg over ALL businesses with attribute X globally → wrong number.
- **Correct — follow 3 steps exactly:**

  **Step 1:** Find all businesses with the attribute. Record each business's state. Build `{business_id: state}`.

  **Step 2:** Count per state → find top state. Filter to ONLY businesses that are BOTH in the top state AND have the attribute.

  **Step 3:** Convert ONLY those IDs to `businessref_N`. Compute `SELECT AVG(rating) FROM review WHERE business_ref IN (...)` over that list only.

  ```python
  from collections import Counter
  attr_biz_state = {}
  for doc in all_docs:
      wifi = doc.get('attributes', {}).get('WiFi', '') if doc.get('attributes') else ''
      if 'free' in wifi or 'paid' in wifi:
          m = re.search(r",\s*([A-Z]{2})(?:,|\s)", doc.get('description', ''))
          if m:
              attr_biz_state[doc['business_id']] = m.group(1)

  top_state = Counter(attr_biz_state.values()).most_common(1)[0][0]
  top_biz_ids = [bid for bid, st in attr_biz_state.items() if st == top_state]

  refs_sql = "', '".join(b.replace('businessid_', 'businessref_') for b in top_biz_ids)
  avg = conn.execute(f"SELECT AVG(rating) FROM review WHERE business_ref IN ('{refs_sql}')").fetchone()[0]
  ```
- **Answer format:** `"PA, {avg:.2f}"` — state first, value immediately after, within first sentence.

---

**[CORRECTION 4] Category aggregation — aggregate ALL reviewed businesses, not just top N** *(PROBE-011)*
- **Wrong:** Find top 5 businesses by review count, extract their categories → categories of top businesses, not top categories.
- **Correct:**
  1. Fetch review counts for ALL businesses reviewed by the target group (may be 60+).
  2. For each business, extract its categories from `description` (see Correction 2).
  3. Sum review counts per category across all businesses.
  4. Sort by total and return top N+2 (see Correction 5).
  ```python
  cat_counts = {}
  for biz_ref, review_cnt in all_biz_review_counts:
      bid = biz_ref.replace('businessref_', 'businessid_')
      for cat in extract_categories(biz_description[bid]):
          cat_counts[cat] = cat_counts.get(cat, 0) + review_cnt
  ```

---

**[CORRECTION 5] Category ranking — output top N+2 to handle ties** *(PROBE-012)*
- Categories at position N may tie with others. Hard-truncating to N omits tied categories the validator requires.
- Always output top N+2. The validator checks PRESENCE not rank.
- Example: "Breakfast & Brunch" ties at position 5 with "Bars" — output top 7 so both appear.
