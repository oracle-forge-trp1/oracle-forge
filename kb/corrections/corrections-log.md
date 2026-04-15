# KB v3 — Corrections Log

Read this before answering any query. If a similar query has failed before, apply the documented fix rather than repeating the same error.

Format: [query that failed] → [what was wrong] → [correct approach]

---

## Entry 001

**Query that failed:**
"What is the average rating of all businesses located in Indianapolis, Indiana?"

**What was wrong:**
Agent attempted a direct string equality join between MongoDB `business.business_id` ("businessid_34") and DuckDB `review.business_ref` ("businessref_34"). Join returned 0 rows with no error — silent failure.

**Correct approach:**
Strip the prefix from both keys and match on the integer N only.

```python
MongoDB: int(business_id.replace("businessid_", ""))
DuckDB:  int(business_ref.replace("businessref_", ""))
```

Never attempt direct string equality across these two fields.

**Category:** Ill-formatted join key
**Dataset:** Yelp (MongoDB + DuckDB)

---

## Entry 002

**Query that failed:**
Any query filtering DuckDB `review.date`, `tip.date`, or `user.yelping_since` by year or date range.

**What was wrong:**
Agent used `STRPTIME(date, '%Y-%m-%d %H:%M:%S')` with a single format. Rows using other formats (`"August 01, 2016 at 03:44 AM"`, `"29 May 2013, 23:01"`) were silently dropped, producing wrong counts and averages.

**Correct approach:**
Use `TRY_STRPTIME` with multiple format patterns, or extract year with regex for year-only filters:

```sql
-- Year-only filter (safe across all formats)
WHERE regexp_extract(date, '\d{4}') = '2015'

-- Full parse (use TRY_ to handle mixed formats)
WHERE TRY_STRPTIME(date, '%Y-%m-%d %H:%M:%S') IS NOT NULL
   OR TRY_STRPTIME(date, '%B %d, %Y at %I:%M %p') IS NOT NULL
```

**Category:** Unstructured text extraction / Type mismatch
**Dataset:** Yelp (DuckDB)

---

## Entry 003

**Query that failed:**
Any query requiring city, state, or address for a Yelp business (e.g. "businesses in Goleta, CA").

**What was wrong:**
Agent queried MongoDB `business` collection for a `city` or `state` field. No such structured field exists. Query returned empty or null for all documents.

**Correct approach:**
Location is embedded in the `description` text field as natural language. Extract with regex before filtering:

```python
import re
pattern = r"Located at (.+?) in (.+?),\s*([A-Z]{2})"
match = re.search(pattern, description)
city = match.group(2)   # e.g. "Goleta"
state = match.group(3)  # e.g. "CA"
```

Apply this extraction in the MongoDB aggregation pipeline using `$regexFind` before any location filter.

**Category:** Domain knowledge gap / Unstructured text extraction
**Dataset:** Yelp (MongoDB)

---

## Entry 004

**Query that failed:**
Any query comparing or summing MongoDB `business.review_count` or checking `business.is_open` as boolean.

**What was wrong:**
Agent treated `review_count` as integer and `is_open` as boolean. Both are stored as strings in MongoDB. Arithmetic and boolean comparisons returned wrong results or errors.

**Correct approach:**
Cast before use:

```python
# review_count
int(document["review_count"])

# is_open
document["is_open"] == "1"   # True = open
document["is_open"] == "0"   # True = closed
```

**Category:** Domain knowledge gap / Type mismatch
**Dataset:** Yelp (MongoDB)

---

## Entry 005

**Query that failed:**
Any query counting or filtering Yelp check-ins by date from MongoDB `checkin.date`.

**What was wrong:**
Agent treated `checkin.date` as a single datetime value. It is a comma-separated string of multiple datetime values. Filtering or counting directly returned wrong results.

**Correct approach:**
Split on `", "` first, then process as a list:

```python
checkin_dates = checkin["date"].split(", ")
# checkin_dates is now a list of datetime strings
count = len(checkin_dates)
```

**Category:** Unstructured text extraction
**Dataset:** Yelp (MongoDB)

---

## Template — Add new entries below this line

**Query that failed:**
[paste the exact query or question]

**What was wrong:**
[describe the failure — wrong database routed, key mismatch, wrong extraction, missing domain knowledge, type error]

**Correct approach:**
[describe the fix, include code snippet where relevant]

**Category:**

- [ ] Multi-database routing
- [ ] Ill-formatted join key
- [ ] Unstructured text extraction
- [ ] Domain knowledge gap

**Dataset:** [which DAB dataset]

**Date:** YYYY-MM-DD
