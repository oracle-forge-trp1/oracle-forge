# Yelp Domain Knowledge (Leakage-Safe)

## Scope

This file contains data-shape and methodology guidance only.
Do not include query-by-query answer keys, expected output strings, fixed winners, or ground-truth values.

---

## Dataset Overview

Two active databases are used:

| Database | Type | Logical Name | Key Contents |
|----------|------|-------------|-------------|
| MongoDB `yelp_db` | MongoDB | — | `business` (metadata, attributes), `checkin` (dates) |
| DuckDB `yelp_user.db` | DuckDB | yelp_user_database | `review` (ratings), `tip`, `user` |

Most questions require combining both systems.

---

## CRITICAL: Rating Source — Never Use MongoDB `business.stars`

**`business.stars` in MongoDB is a pre-computed, stale cached value.**
It does NOT match `AVG(review.rating)` computed over actual reviews.
Using `business.stars` for "average rating" questions yields wrong answers (typically ~0.5–1.0 too high).

**Rule**: For any question that asks for an average rating, ALWAYS compute from DuckDB:
```sql
SELECT AVG(rating) FROM review WHERE business_ref IN (...)
```
Never use `business.stars` from MongoDB for the final numeric answer.

---

## CRITICAL: Cross-Database Join Keys

The business identifier uses **different prefixes** in each system:
- MongoDB `business`: `business_id` field → format `businessid_N` (e.g. `businessid_49`)
- DuckDB `review`: `business_ref` field → format `businessref_N` (e.g. `businessref_49`)

**The numeric suffix N is shared** — use it to join:
```python
# businessid_49 in MongoDB corresponds to businessref_49 in DuckDB
# Normalize: strip prefix, match on numeric part
```

**Pattern for state-level rating queries:**
1. Query MongoDB: `db.business.find({}, {"business_id": 1, "state": 1})` → get (businessid_N, state) pairs
2. Map: `businessid_N` → `businessref_N`
3. Query DuckDB: `SELECT business_ref, AVG(rating) FROM review WHERE business_ref IN (...) GROUP BY business_ref`
4. Join in Python: merge on normalized numeric key

Never return raw `businessref_XX` or `businessid_XX` values in the final answer — always resolve to the human-readable name or state label.

---

## CRITICAL: Business Name Lookup

After aggregating in DuckDB (e.g., finding the top-rated `business_ref`), you MUST look up the human-readable name from MongoDB:
1. Convert `businessref_N` → `businessid_N` (same N)
2. Query MongoDB: `db.business.find_one({"business_id": "businessid_N"}, {"name": 1})`
3. Use `name` field as the final answer

The validator checks for the business name, not the internal ID.

---

## Schema Reference

### MongoDB `business` collection fields
- `business_id`: string, format `businessid_N`
- `name`: business name (use this for answers requiring business name)
- `state`: two-letter state code (e.g. `"PA"`) — present as top-level field in most documents
- `review_count`: integer (cast before arithmetic)
- `is_open`: string `"1"` or `"0"` (not boolean)
- `attributes`: nested dict-like structure (see Attributes section below)
- `description`: free text containing address, categories, and other info
- **`categories`**: Field may be absent or null. Use `description` text parsing as the primary source for category data.

### DuckDB `review` table columns
- `review_id`, `user_id`, `business_ref` (e.g. `businessref_49`), `rating` (integer 1–5), `useful`, `funny`, `cool`, `text`, `date`

### DuckDB `user` table
- `user_id`, `name`, `yelping_since` (year-only filter: `yelping_since LIKE '2016%'`)

---

## Attributes Parsing

`business.attributes` is a dict embedded in MongoDB. Common fields:

### WiFi
Stored as Python string repr with possible `u` prefix:
- `"u'free'"`, `"'free'"` → WiFi is free
- `"u'paid'"`, `"'paid'"` → WiFi is paid
- `"u'no'"`, `"'no'"`, `None` → no WiFi

**Match robustly** (do not use exact equality):
```python
# In MongoDB aggregation:
{"$match": {"attributes.WiFi": {"$regex": "free|paid", "$options": "i"}}}
# For WiFi=yes (free or paid): match anything NOT containing "no" and not null
```

### Credit Card Acceptance
`attributes.BusinessAcceptsCreditCards` — stored as string `"True"` or `"False"`.
```python
{"$match": {"attributes.BusinessAcceptsCreditCards": "True"}}
```

### Parking
`attributes.BusinessParking` — stored as a serialized dict string, e.g.:
`"{'garage': False, 'street': False, 'validated': False, 'lot': True, 'valet': False}"`

To detect business parking (any type except none):
```python
# Match if any parking type is True (use regex on the stringified dict)
{"$match": {"attributes.BusinessParking": {"$regex": "True"}}}
```

For bike parking, check for `attributes.BikeParking` = `"True"`.

---

## Categories Extraction

`business.categories` field is **frequently absent** from documents. The primary source for category data is the `description` text field.

Parse categories from `description` using regex or text matching. Emit tokens **exactly as they appear** in the stored data — do NOT normalize case, singularize, or paraphrase.

Common category tokens include: `Restaurants`, `Food`, `Nightlife`, `Bars`, `Coffee & Tea`, `American (New)`, `Breakfast & Brunch`, `Shopping`, `Beauty & Spas`, etc.

**For category aggregate queries:**
- Extract categories from ALL qualifying businesses before ranking
- Use `$unwind` if categories are an array, or parse from description text
- Never rank categories using only a subset of businesses

---

## State Queries

`business.state` is a top-level MongoDB field containing the two-letter state code.

For "which state has the most X" patterns:
```python
# MongoDB aggregation for state-level review counts:
pipeline = [
    {"$lookup": or cross-DB join from DuckDB review counts back to MongoDB state},
    ...
]
# Or: get (business_ref → state) mapping from MongoDB, then aggregate in DuckDB
```

**State token in final answer**: Always emit the exact two-letter abbreviation from `business.state` (e.g. `PA`). The validator accepts both `PA` and `Pennsylvania`.

---

## Date Parsing

DuckDB `review.date` can include multiple formats. Use `COALESCE(TRY_STRPTIME(...))` with at least 3 patterns:
```sql
COALESCE(
    TRY_STRPTIME(date, '%Y-%m-%d %H:%M:%S'),
    TRY_STRPTIME(date, '%B %d, %Y at %I:%M %p'),
    TRY_STRPTIME(date, '%Y-%m-%d')
) AS parsed_date
```
For year-only filters, regex year extraction is the safest approach:
```sql
WHERE regexp_extract(date, '\d{4}') = '2018'
```

---

## Check-in Field Shape

`checkin.date` may be a single comma-separated string containing multiple timestamps.
Split before counting/filtering event instances.

---

## Methodology Rules

### Row-level aggregation (avg ratings)
Compute `AVG(review.rating)` over review rows directly. Never average a set of per-business means.

### Two-stage state/category queries
1. First find the winning state/category using counts on the full eligible population
2. Then compute the secondary metric (avg rating) ONLY for that winning group

### Category completeness
For "top-N categories" queries, aggregate from ALL businesses matching the filter — not just the top few by review count.

---

## Common Pitfalls

- Using `business.stars` instead of `AVG(review.rating)` → wrong average (too high). → **Entry 050**
- Returning `businessref_XX` or `businessid_XX` IDs in final answer instead of business names. → **Entry 051**
- Joining on exact string match across MongoDB/DuckDB ID columns without prefix normalization. → **Entry 001**
- WiFi attribute exact-string matching failing due to `u'...'` Python repr format. → **Entry 052**
- Assuming `business.categories` field exists (often absent — parse from description). → **Entry 053**
- Aggregating per-business averages when question requires review-level aggregation. → **Entry 006**
- State token missing or null in final output despite correct numeric part. → **Entry 042**
- Category tokens paraphrased instead of copied verbatim. → **Entry 043**

---

## Validation Checklist

- ID join quality: matched/unmatched counts after normalization.
- Rating source: confirmed using DuckDB `review.rating`, NOT MongoDB `business.stars`.
- Business name: resolved from MongoDB `business.name`, not emitting internal IDs.
- State token: explicit two-letter abbreviation from `business.state`.
- Category tokens: verbatim from data, full set included, not paraphrased.
- Aggregate denominator: reviews vs businesses vs users clearly separated.

---

## Leakage-Safe Policy

- Keep content methodological and runtime-derivable.
- Do not store fixed benchmark outputs or precomputed winners.
- Favor reusable parsing/join/validation guidance over query-specific shortcuts.
