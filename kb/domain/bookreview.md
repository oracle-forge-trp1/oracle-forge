# BookReview Domain Knowledge

## Dataset Overview

Two databases for this dataset:

| Database | Type | Logical Name | Table | Key Fields |
|----------|------|--------------|-------|------------|
| books_info.sql | PostgreSQL | books_database | books_info | title, subtitle, author, rating_number, features, description, price, store, categories, details, book_id |
| review_query.db | SQLite | review_database | review | rating (int), title, text, review_time (str), helpful_vote (int), verified_purchase (int), purchase_id |

---

## CRITICAL: Cross-Database Join Keys

The two databases use **different key field names AND different prefixes** for the same book:

- `books_info.book_id` → format `bookid_N` (e.g. `bookid_1`)
- `review.purchase_id` → format `purchaseid_N` (e.g. `purchaseid_1`)

**Same N = same book.** To join: replace `bookid_` with `purchaseid_` (or extract the numeric N and match).

```python
# Step 1: Query PostgreSQL for books with category filter
pg_results = query_postgres("books_database",
    "SELECT book_id, title FROM books_info WHERE categories ILIKE '%Literature & Fiction%'")

# Step 2: Map book_id → purchase_id
purchase_ids = [r["book_id"].replace("bookid_", "purchaseid_") for r in pg_results["data"]]
placeholders = ",".join(f"'{pid}'" for pid in purchase_ids)

# Step 3: Query SQLite with purchase_ids
sqlite_results = query_sqlite("review_database",
    f"SELECT purchase_id, AVG(rating) AS avg_rating, COUNT(*) AS review_count "
    f"FROM review WHERE purchase_id IN ({placeholders}) GROUP BY purchase_id")
```

---

## Publication Year and Decade Extraction

There is **NO standalone year column** in `books_info`. The publication year is embedded in the `details` text field.

Typical `details` field format:
```
"Published by Chatto & Windus, the first edition of this book was released on January 1, 2004. 
It is written in English and comes in a hardcover format, comprising 196 pages."
```

### PostgreSQL regex extraction:
```sql
-- Extract 4-digit publication year
SUBSTRING(details FROM '((?:19|20)\d{2})') AS pub_year

-- Compute decade label (e.g., 2004 → 2000, 2020 → 2020, 2023 → 2020)
(CAST(SUBSTRING(details FROM '((?:19|20)\d{2})') AS INTEGER) / 10) * 10 AS decade_start
```

Use COALESCE across multiple fields to maximize coverage:
```sql
COALESCE(
    SUBSTRING(details FROM '((?:19|20)\d{2})'),
    SUBSTRING(subtitle FROM '((?:19|20)\d{2})')
) AS pub_year
```

### Decade label format
The decade is reported as the starting year: `2020` means "2020s" (2020–2029), `2010` means "2010s" (2010–2019).

---

## Language Filter

There is **no explicit language column**. Language is embedded in the `details` field:
`"It is written in English and comes in a hardcover format..."`

To filter English-language books:
```sql
WHERE details ILIKE '%written in English%'
```

---

## Categories Field

`categories` in `books_info` is stored as a JSON-array string, e.g.:
```
["Books", "Literature & Fiction", "History & Criticism"]
```

Use `ILIKE` (case-insensitive) for filtering — no JSON parsing required:
```sql
WHERE categories ILIKE '%Literature & Fiction%'
WHERE categories ILIKE '%Children''s Books%'
```

---

## Review Date Filtering

`review_time` in SQLite uses `'YYYY-MM-DD HH:MM:SS'` format consistently.
Lexicographic comparison works for year filtering:
```sql
WHERE review_time >= '2020-01-01'   -- reviews from 2020 onwards
WHERE review_time >= '2018-01-01' AND review_time < '2019-01-01'   -- year 2018
```

---

## Data Semantics

- `review.rating` is stored as INTEGER (1–5)
- `AVG(rating)` returns float; compare with `= 5` for perfect rating
- `rating_number` in `books_info` is a denormalized count — do not use as a proxy for review counts; use actual SQLite `review` rows

---

## Query Strategy Playbook

### Decade-level rating analysis
1. PostgreSQL: extract pub_year with regex, compute decade, filter books with ≥N distinct reviews
2. SQLite: aggregate ratings per purchase_id
3. Join in Python on numeric key suffix
4. Compute AVG(rating) per decade from row-level review data

### Category-constrained rating quality
1. PostgreSQL: `WHERE categories ILIKE '%TargetCategory%'` → get `book_id` list
2. Convert to `purchase_id` list
3. SQLite: `AVG(rating)` per `purchase_id`, apply `HAVING` threshold

### Exhaustive title lists
If the prompt asks for **all** qualifying books, include every title returned by the final query — no summarization, no "and others", no ellipsis.

---

## When PostgreSQL Fails

If `query_postgres` returns errors repeatedly:
1. Check the exact error message — may be "relation does not exist" (wrong table name) or connection issue
2. Try introspecting: `SELECT table_name FROM information_schema.tables WHERE table_schema='public'`
3. The PostgreSQL `books_database` must be loaded at agent startup — if it fails entirely, report the error and attempt SQLite-only analysis with whatever information is available
4. Do NOT return a wrong decade based on SQLite-only data (SQLite lacks publication year info)

---

## Common Pitfalls

- Joining `book_id` and `purchase_id` without suffix normalization (`bookid_N` vs `purchaseid_N`). → **Entry 001**
- Assuming publication year is a column — must parse from `details` text. → **Entry 002**
- Not filtering for English language when question specifies English-language books.
- Applying time filters after aggregation instead of before.
- Averaging per-book averages across categories instead of row-level review ratings. → **Entry 006**
- Using `rating_number` from `books_info` instead of counting actual SQLite review rows.

---

## Validation Checklist

- Key mapping: verify `bookid_N → purchaseid_N` conversion coverage.
- Year extraction: check non-null rate from regex on `details` field.
- Decade formula: confirm integer division gives correct decade start year.
- Language filter: applied before aggregation when question specifies English.
- Rating source: row-level `AVG(rating)` from SQLite review table, not denormalized fields.
- Completeness: for list queries, ensure ALL qualifying titles are returned.

---

## Leakage-Safe Policy

- Do not include expected title lists, hardcoded ranked outputs, or final benchmark values.
- Keep only reusable parsing/join/aggregation methods and quality checks.
- Examples should remain procedural and recomputable from current tool outputs.
