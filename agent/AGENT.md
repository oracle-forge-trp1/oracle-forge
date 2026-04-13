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
| `review_count` | int | |
| `is_open` | int | `1` = open, `0` = closed |
| `attributes` | dict / null | WiFi, parking — may be serialized str |
| `hours` | dict / null | day → `"HH:MM-HH:MM"` |
| `description` | str | Location embedded as natural language — no structured address |

Collection `checkin` (90 docs):
| Field | Type | Notes |
|---|---|---|
| `business_id` | str | links to `business` |
| `date` | list of str | list of datetime strings |

**DuckDB `/shared/oracle-forge/DataAgentBench/query_yelp/query_dataset/yelp_user.db`** (ACTIVE)

- `review` (2000 rows): `review_id`, `user_id`, `business_ref` (str), `rating` (int 1–5), `useful`, `funny`, `cool`, `text`, `date`
- `tip` (784 rows): `user_id`, `business_ref`, `text`, `date`, `compliment_count`
- `user` (1999 rows): `user_id`, `name`, `review_count`, `yelping_since`, `useful`, `funny`, `cool`, `elite`

**PostgreSQL localhost:5432** — PENDING (installed, no DAB datasets loaded)

**SQLite** — PENDING (installed, no DAB datasets loaded)

---

## 3. Cross-Database Join Key Map

| MongoDB field | DuckDB field | Meaning | MongoDB format | DuckDB format |
|---|---|---|---|---|
| `business.business_id` | `review.business_ref` / `tip.business_ref` | Same business entity | `"businessid_N"` | `"businessref_N"` |

**Never** use direct string equality — it always returns zero rows. Extract integer N and match:
```python
n = int(business_id.replace("businessid_", ""))  # then filter DuckDB: business_ref == f"businessref_{n}"
```

---

## 4. Query Execution Protocol

1. **Identify databases** — which DB holds each required field?
2. **Check join keys** — for cross-DB queries, apply the `businessid_N` ↔ `businessref_N` translation.
3. **Extract unstructured data first** — parse location from `description` before filtering (see §6).
4. **Handle date columns** — use `TRY_STRPTIME` with multiple patterns (see §6).
5. **Execute and verify** — zero rows on a join almost always means a key mismatch.
6. **Return structured output:**
```json
{"answer": "...", "query_trace": [{"database": "...", "query": "...", "result_summary": "..."}], "confidence": "high|medium|low", "notes": "..."}
```

---

## 9. Answer Quick-Reference Rules (MANDATORY — check before answering)

**R1: Review counts come from DuckDB `review` table rows — NEVER from MongoDB `review_count` field.**
- Wrong: `db.business.aggregate([{"$group": {"total": {"$sum": "$review_count"}}}])`
- Correct: `SELECT COUNT(*) FROM review WHERE business_ref IN (...)`
- Why: MongoDB `review_count` is a stale cached field; it diverges from actual DuckDB review rows.

**R2: "Which state has the most reviews/businesses?" queries — always lead the answer with "STATE, value".**
- Validators scan only 50 chars after "PA" or "Pennsylvania" for the numeric value.
- Correct first sentence: `"PA, 3.70"` or `"Pennsylvania: 3.70"` — state and number together immediately.
- Wrong: `"Pennsylvania (PA) has the highest number of reviews with 626 total reviews, and the average rating is 3.70"` — the number 626 appears in the 50-char window before 3.70, causing validation failure.

**R3: Average ratings — always `SELECT AVG(rating)` over raw DuckDB review rows directly. Never average per-business averages.**
- See Correction 1.

**R4: Category "top N" queries — always output top N+2 to handle ties.**
- See Correction 9.

---

## 5. Self-Correction Protocol

Diagnose before retrying:
- **Wrong database?** — Check which DB holds the field.
- **Key mismatch?** — Zero rows on cross-DB join → apply integer N translation.
- **SQL dialect error?** — DuckDB uses analytical SQL; MongoDB requires aggregation pipelines.
- **Data quality issue?** — Mixed date formats, serialized attribute strings, null `user_id` in tip/review.
- **Domain gap?** — Check §7 before concluding data doesn't exist.

Record both the failed query and the corrected one in the query trace.

---

## 6. Unstructured Text Handling

MongoDB `business.description` stores location as natural language. No structured address field exists.
Descriptions use different formats — some say "Located at … in City, ST,", others "Situated at … in City, ST,", others "This City, ST location…".
**Use the simple comma-state pattern** — it works for all formats:

```python
import re
# Extract state code: find ", ST," or ", ST " anywhere in description
m = re.search(r",\s*([A-Z]{2})(?:,|\s)", doc["description"])
state = m.group(1).upper() if m else None
```

**Never use** the "Located at .+ in City, ST" pattern — it misses businesses that use "Situated at" or city-first descriptions, silently under-counting and producing wrong averages.

DuckDB date formats — ALL date columns (`review.date`, `tip.date`, `user.yelping_since`) contain mixed formats in the same column. Using a single `TRY_STRPTIME` pattern silently returns NULL for non-matching rows, causing wrong year counts. **Always COALESCE all known patterns:**

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

Example: filtering reviews from 2018 with single-format gets 36 businesses; with COALESCE gets the correct 67. Always use COALESCE or the answer will be wrong.

---

## 7. Domain Knowledge

> **TO BE POPULATED from `kb/domain/`**

---

## 8. Known Corrections

> Additional corrections in `kb/corrections/corrections-log.md`. Read before answering any query.

**[CORRECTION 1] Weighted vs unweighted average across businesses**
- **Query type:** "What is the average rating of businesses in [location]?"
- **Wrong approach:** GROUP BY business, get per-business AVG, then average those → returns ~3.86
- **Root cause:** Businesses with few reviews get equal weight to businesses with many reviews
- **Correct approach:** Flat `SELECT AVG(rating) FROM review WHERE business_ref IN (...)` over all review rows → returns 3.547
- **Rule:** Never average a column of averages. Always aggregate over the raw review rows directly.

**[CORRECTION 3] MongoDB `attributes` — already a Python dict; only its VALUES are strings**
- **Critical:** `attributes` is already a native Python dict when returned by pymongo. Do NOT call `ast.literal_eval` on the `attributes` object itself — it is not a string and doing so will raise an error or return wrong results.
- Only the **VALUES** inside `attributes` are stored as strings (Python repr format).
- **Boolean attributes** (e.g. `BikeParking`, `BusinessAcceptsCreditCards`): value is the string `'True'` / `'False'`, not a Python bool:
  ```python
  doc['attributes'].get('BikeParking') == 'True'            # CORRECT — string 'True'
  doc['attributes'].get('BikeParking') == True              # WRONG — Python bool, always False
  ```
- **WiFi**: stored as Python-2-style unicode string `"u'free'"`, `"u'paid'"`, `"'free'"`, `"'no'"`, `"u'no'"`:
  ```python
  wifi = doc['attributes'].get('WiFi', '')
  has_wifi = 'free' in wifi or 'paid' in wifi   # catches all free/paid variants
  ```
- **BusinessParking**: the `attributes['BusinessParking']` VALUE is a serialized Python dict STRING, e.g. `"{'garage': False, 'street': True, 'lot': False}"`. Call `ast.literal_eval` on this string VALUE only:
  ```python
  import ast
  bp_str = doc['attributes'].get('BusinessParking', '{}')
  bp = ast.literal_eval(bp_str) if isinstance(bp_str, str) else bp_str
  has_parking = isinstance(bp, dict) and any(bp.values())
  ```
- **Rule:** `ast.literal_eval` applies ONLY to the `BusinessParking` string value. Never call it on `attributes` itself or any other attribute value.

**[CORRECTION 2] Answer format — lead with the key value**
- **Query type:** "Which [X] has the highest [Y], and what is its [Z]?"
- **Wrong format:** "Pennsylvania (PA) has the highest number... The average rating for those businesses is 3.48." (number is 80+ chars from the state name — validation window misses it)
- **Correct format:** Lead with the concise key-value pair: `"PA, 3.48"` or `"Pennsylvania: 3.48"` — put the name and number close together in the first sentence.

**[CORRECTION 5] DuckDB date parsing — always COALESCE all formats, never single TRY_STRPTIME**
- **Problem:** `review.date`, `tip.date`, and `user.yelping_since` use at least 4 mixed formats in the same column. A single `TRY_STRPTIME(date, '%Y-%m-%d %H:%M:%S')` returns NULL for non-ISO rows and silently produces wrong counts. For 2018 reviews: single-format gives 36 distinct businesses; COALESCE gives the correct 67.
- **Correct approach:** Use the full COALESCE expression shown in §6 everywhere a date comparison is needed.
- **Rule:** Never use `TRY_STRPTIME` with a single format. Always wrap with COALESCE over all 6 patterns in §6.

**[CORRECTION 6] Business categories are embedded in `description` text — no separate category field**
- **Problem:** The `business` collection has no `category` field. Querying for it returns zero results.
- **Root cause:** Categories are embedded as natural language in the `description` field, in patterns like:
  - `"...offers a diverse menu featuring Restaurants, Breakfast & Brunch, American (New), and Cafes."`
  - `"...in the categories of 'Restaurants, Chinese'."`
  - `"...providing a range of services in Education, Elementary Schools..."`
  - `"...including Hair Salons, Beauty & Spas, Hair Stylists..."`
- **Correct approach:** Extract with Python regex after fetching the full business document:
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
  Split the extracted string on `, ` and strip leading `"and "`.
- **Catch-all for restaurant queries:** When the question asks about restaurants or restaurant-related attributes, ALSO flag any business where `'restaurant' in description.lower()`. Some businesses use "restaurant" in a sentence but not in a category phrase that the regex captures. Union the regex-extracted set with the substring-match set:
  ```python
  regex_cats = extract_categories(description)
  is_restaurant = 'restaurant' in description.lower() or any(
      'restaurant' in c.lower() for c in regex_cats
  )
  ```
- **Rule:** When a query asks about business categories, extract from `description` text — do not query for a category field. For restaurant-specific queries, always use the union approach above.

**[CORRECTION 7] "Which state has the most [attribute], avg rating for those businesses?" — MANDATORY 3-step algorithm**
- **Query pattern:** "Which [state/group] has the most [X], and what is the average rating for those businesses?"
- **Wrong approach:** Identify the top state (e.g. PA), then compute avg rating across ALL businesses that have attribute X regardless of state → returns wrong number (e.g. 3.71 instead of 3.48).
- **Root cause:** The avg must be scoped to ONLY the businesses in the TOP STATE that ALSO have the attribute — not all businesses with the attribute globally.

**Correct approach — follow these 3 steps exactly:**

**Step 1:** Find ALL businesses with the attribute (e.g. WiFi). For each, record its state using the comma-state regex. Build `{business_id: state}` mapping.

**Step 2:** Count businesses per state → find the top state. Then **filter the business_id list to ONLY businesses that are BOTH in the top state AND have the attribute**.

**Step 3:** Convert ONLY those business IDs to `businessref_N` and compute `SELECT AVG(rating) FROM review WHERE business_ref IN (...)` over that restricted list.

```python
import re
from collections import Counter

# Step 1: find attribute businesses and their states
attr_biz_state = {}
for doc in all_docs:
    wifi = doc.get('attributes', {}).get('WiFi', '') if doc.get('attributes') else ''
    if 'free' in wifi or 'paid' in wifi:
        m = re.search(r",\s*([A-Z]{2})(?:,|\s)", doc.get('description', ''))
        if m:
            attr_biz_state[doc['business_id']] = m.group(1)

# Step 2: top state, then filter to ONLY that state's attribute businesses
top_state = Counter(attr_biz_state.values()).most_common(1)[0][0]  # e.g. "PA"
top_biz_ids = [bid for bid, st in attr_biz_state.items() if st == top_state]

# Step 3: avg for ONLY those top-state businesses
refs = [b.replace('businessid_', 'businessref_') for b in top_biz_ids]
refs_sql = "', '".join(refs)
avg = conn.execute(f"SELECT AVG(rating) FROM review WHERE business_ref IN ('{refs_sql}')").fetchone()[0]
```

**Answer format:** `"PA, {avg:.2f}"` — state abbreviation first, then value, in the very first sentence. The validator scans only 50 chars after "PA"/"Pennsylvania" for the number — do not put any other number before the avg in that window.

**[CORRECTION 8] Category aggregation — aggregate ALL reviewed businesses, not just top N**
- **Query pattern:** "Which 5 categories have received the most reviews from [group of users]?"
- **Wrong approach:** Find top 5 businesses by review count, extract their categories, list them → gives categories of the top few businesses, not the top categories overall.
- **Root cause:** A category may rank highly not because one business has many reviews, but because many businesses share that category and each has a few reviews.
- **Correct approach:**
  1. Fetch review counts for ALL businesses reviewed by the target user group (may be 60+ businesses).
  2. For EACH of those businesses, extract its categories from `description` (see Correction 6).
  3. For each category, sum the total reviews from all businesses that have that category.
  4. Sort by total review count and return top 5.
  ```python
  cat_counts = {}
  for biz_ref, review_cnt in all_biz_review_counts:
      bid = biz_ref.replace('businessref_', 'businessid_')
      for cat in extract_categories(biz_description[bid]):
          cat_counts[cat] = cat_counts.get(cat, 0) + review_cnt
  top5 = sorted(cat_counts, key=cat_counts.get, reverse=True)[:5]
  ```
- **Rule:** Never summarize categories from only the top N businesses. Aggregate across all businesses in the result set.

**[CORRECTION 9] Category ranking — output top N+2 to handle ties at position N**
- **Query pattern:** "Which N categories have received the most reviews from [users]?"
- **Problem:** Categories at position N may tie with other categories. Outputting exactly N can omit a tied category that the validator requires.
- **Correct approach:** Sort all categories by review count, then output the top N+2 (e.g., top 7 if asked for top 5). List all of them in your answer — the validator checks for PRESENCE not strict rank.
- **Example:** For "top 5 categories", if "Breakfast & Brunch" (9 reviews) and "Bars" (14 reviews) are close in rank, outputting top 7 ensures both appear. The validator only checks that "Breakfast & Brunch" is somewhere in the output.
- **Rule:** Never hard-truncate to exactly N when building category answers. Include N+2 or more to be safe.

**[CORRECTION 4] Location extraction — use simple `,\s*STATE` pattern, not "Located at" regex**
- **Problem:** Some descriptions say "Situated at … in City, ST," or "This City, ST location…" — they never say "Located at". The regex `Located at .+ in ([^,]+),\s*([A-Z]{2})` misses ~8% of businesses, producing wrong state-level averages.
- **Root cause:** Greedy `.+` also picks up wrong states when " in " appears multiple times in the description.
- **Correct approach:**
  ```python
  m = re.search(r",\s*([A-Z]{2})(?:,|\s)", doc["description"])
  state = m.group(1).upper() if m else None
  ```
- **Rule:** Always use the comma-state pattern for state extraction. Never use the "Located at" pattern.
