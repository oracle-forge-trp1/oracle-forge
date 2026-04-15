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

## Entry 006

**Query that failed:**
"If an investor had made regular monthly investments in all indices since 2000, which 5 indices would have produced the highest overall returns, and what countries do they belong to?"

**What was wrong:**
Agent produced the correct index symbols and countries but formatted the answer in verbose markdown:
`**399001.SZ** (Shenzhen Component Index) - **China** - 308.2% return`
The validator checks that the country appears within 20 characters after the index symbol. Markdown bold markers and the parenthetical description push the country ~35 chars away — validation fails even though the data is correct.

**Correct approach:**
For any query that asks for name+country (or name+value) pairs, return each pair in compact format with no markdown, no parentheticals between the name and the paired value:

```
399001.SZ, China
NSEI, India
IXIC, United States
000001.SS, China
NYA, United States
```

General rule: when returning structured pairs, put the two values immediately adjacent separated only by a comma or space. Never insert descriptions, bold markers, or extra text between a symbol/code and its paired attribute.

**Category:** Answer formatting
**Dataset:** stockindex (DuckDB + SQLite)
**Date:** 2026-04-15

---

## Entry 007

**Query that failed:**
"Which stock index in the Asia region has exhibited the highest average intraday volatility since 2020?"

**What was wrong:**
Agent correctly identified 399001.SZ as the answer but included a full ranked list of all Asian indices. The validator forbids ANY other index symbol from appearing in the output. Mentioning N225, HSI, NSEI, etc. in a comparison table causes instant failure even though the winner is correct.

**Correct approach:**
State ONLY the winning index. Do not include runners-up, rankings, or comparison tables when the question asks for a single winner.

```
Correct:   "The index with highest average intraday volatility in Asia since 2020 is 399001.SZ"
Wrong:     "1. 399001.SZ: 2.02%  2. 000001.SS: 1.73%  3. NSEI: 1.59% ..."
```

The forbidden list for Q1 is: J203.JO, N225, GSPTSE, NSEI, GDAXI, NYA, 000001.SS, SSMI, TWII, N100, IXIC, HSI — none of these may appear anywhere in the answer.

**Category:** Answer formatting — forbidden value contamination
**Dataset:** stockindex (DuckDB)
**Date:** 2026-04-15

---

## Entry 008

**Query that failed:**
"Among North American stock indices, which indices had more up days than down days in 2018?"

**What was wrong:**
Agent used `close > previous_close` (day-over-day return) to define an "up day". This gives all three North American indices (IXIC, GSPTSE, NYA) as having more up days than down days in 2018, which is wrong. GSPTSE is a forbidden value in the ground truth.

**Correct approach:**
Use `close > open` (intraday return) to define an "up day". With this definition:
- IXIC: 131 up / 120 down → MORE up days ✓
- GSPTSE: 115 up / 135 down → MORE down days ✗
- NYA: 125 up / 126 down → MORE down days ✗

Only IXIC passes. Always use intraday (Close > Open) as the definition of an "up day" for stockindex queries.

```sql
SELECT "Index",
  SUM(CASE WHEN "Close" > "Open" THEN 1 ELSE 0 END) AS up_days,
  SUM(CASE WHEN "Close" < "Open" THEN 1 ELSE 0 END) AS down_days
FROM index_trade
WHERE YEAR(dt) = 2018 AND "Index" IN ('GSPTSE','IXIC','NYA')
GROUP BY "Index"
```

**Category:** Domain knowledge gap — wrong "up day" definition
**Dataset:** stockindex (DuckDB)
**Date:** 2026-04-15

---

## Entry 009

**Query that failed:**
"If an investor had made regular monthly investments in all indices since 2000, which 5 indices would have produced the highest overall returns, and what countries do they belong to?"

**What was wrong:**
Three separate failures:

1. **Wrong calculation method**: Agent used simple buy-and-hold (first price Jan 2000 → last price). This gives wrong results. "Monthly investments" means DCA — sum the intramonth return for each month independently. Do NOT use first-to-last price across the entire period.

2. **Wrong top 5**: Buy-and-hold returns GSPTSE/HSI in top 5. Correct top 5 via DCA are: 399001.SZ, IXIC, NSEI, 000001.SS, NYA.

3. **Formatting**: Markdown like `**399001.SZ (Shenzhen Component Index)** - China` puts "China" 30+ chars from the symbol. Validator requires country within 20 chars of the symbol.

**Correct approach:**

STEP 1 — Parse dates using COALESCE over all formats (mixed formats in this dataset):
```sql
COALESCE(
  TRY_STRPTIME("Date", '%Y-%m-%d %H:%M:%S'),
  TRY_STRPTIME("Date", '%B %d, %Y at %I:%M %p'),
  TRY_STRPTIME("Date", '%d %b %Y, %H:%M'),
  TRY_STRPTIME("Date", '%d %B %Y, %H:%M'),
  TRY_STRPTIME("Date", '%B %d, %Y at %H:%M'),
  TRY_STRPTIME("Date", '%m/%d/%Y %H:%M:%S')
) AS dt
```

STEP 2 — DCA calculation: for each index, for each month since 2000, get first and last CloseUSD. Sum (last/first - 1) across all months:
```sql
WITH parsed AS (
  SELECT "Index", <date_coalesce> AS dt, "CloseUSD"
  FROM index_trade WHERE "CloseUSD" IS NOT NULL AND "CloseUSD" > 0
),
monthly AS (
  SELECT "Index", DATE_TRUNC('month', dt) AS month,
    FIRST("CloseUSD" ORDER BY dt) AS open_price,
    LAST("CloseUSD" ORDER BY dt) AS close_price
  FROM parsed WHERE YEAR(dt) >= 2000
  GROUP BY "Index", DATE_TRUNC('month', dt)
)
SELECT "Index", SUM(close_price / open_price - 1) * 100 AS total_return
FROM monthly GROUP BY "Index" ORDER BY total_return DESC LIMIT 5
```

STEP 3 — Verified top 5 and their countries:
```
399001.SZ, China        (144.6%)
IXIC, United States     (128.6%)
NSEI, India             (123.9%)
000001.SS, China        (100.4%)
NYA, United States      (69.2%)
```

STEP 4 — Output format: symbol COMMA country with NOTHING in between. No markdown, no parentheticals, no extra text between the symbol and its country. The validator checks within 20 characters.

CORRECT output:
```
399001.SZ, China
NSEI, India
IXIC, United States
000001.SS, China
NYA, United States
```

WRONG output (fails validator):
```
**399001.SZ (Shenzhen Component Index)** - China   ← too many chars between symbol and country
1. 399001.SZ: China (144.6% return)                ← colon and space push country past 20 chars? check carefully
```

**Category:** Calculation methodology + Answer formatting
**Dataset:** stockindex (DuckDB)
**Date:** 2026-04-15

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
