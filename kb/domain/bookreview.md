# BookReview Domain Knowledge

## Dataset Overview

Two databases for this dataset:

| Database | Type | Logical Name | Table | Key Fields |
|----------|------|--------------|-------|------------|
| books_info.sql | PostgreSQL | books_database | books_info | title, subtitle, author, rating_number, features, description, price, store, categories, details, book_id |
| review_query.db | SQLite | review_database | review | rating (int), title, text, review_time (str), helpful_vote (int), verified_purchase (int), purchase_id |

---

## Join Key: book_id ↔ purchase_id

**CRITICAL:** The two databases use different key field names AND different prefixes.

- `books_info.book_id` format: `bookid_N` (e.g. `bookid_1`, `bookid_186`)
- `review.purchase_id` format: `purchaseid_N` (e.g. `purchaseid_1`, `purchaseid_186`)

These represent the same book. To join: extract the numeric N from each and match.

**Cross-DB join strategy (Python):**

```python
# Step 1: Query PostgreSQL for books (e.g. with category filter)
pg_results = query_postgres("books_database",
    "SELECT book_id, title FROM books_info WHERE categories LIKE '%Literature & Fiction%'")

# Step 2: Build SQLite IN clause using matching purchase_id values
# bookid_N → purchaseid_N (same N)
book_ids = [r["book_id"] for r in pg_results]
purchase_ids = [bid.replace("bookid_", "purchaseid_") for bid in book_ids]

placeholders = ",".join(f"'{pid}'" for pid in purchase_ids)
sqlite_results = query_sqlite("review_database",
    f"SELECT purchase_id, AVG(rating) AS avg_rating FROM review WHERE purchase_id IN ({placeholders}) GROUP BY purchase_id")
```

**Alternative: DuckDB-style cross-DB**
If the agent has Python access, merge the two result sets on the numeric suffix extracted from the keys.

---

## Category Field Format

The `categories` field is stored as a **JSON array string**, e.g.:
```
["Books", "Literature & Fiction", "History & Criticism"]
```

Use `LIKE` for filtering — no JSON parsing needed in SQL:
```sql
-- PostgreSQL
WHERE categories LIKE '%Literature & Fiction%'
WHERE categories LIKE '%Children''s Books%'
WHERE categories LIKE '%Science Fiction%'
```
Use `ILIKE` for case-insensitive matching.

---

## Publication Year / Decade Extraction

The `details` field is a free-text description containing the publication year, e.g.:
```
"Published by Chatto & Windus, the first edition of this book was released on January 1, 2004.
It is written in English and comes in a hardcover format, comprising 196 pages."
```

Extract year with PostgreSQL regex:
```sql
-- Extract 4-digit year from details
SUBSTRING(details FROM '\m((?:19|20)\d{2})\M') AS pub_year

-- Compute decade (e.g. 2004 → 2000, 2023 → 2020)
(CAST(SUBSTRING(details FROM '\m((?:19|20)\d{2})\M') AS INTEGER) / 10) * 10 AS decade
```

The `subtitle` field also often contains the year (e.g. `"Hardcover – Import, January 1, 2004"`):
```sql
COALESCE(
  SUBSTRING(details FROM '\m((?:19|20)\d{2})\M'),
  SUBSTRING(subtitle FROM '\m((?:19|20)\d{2})\M')
) AS pub_year
```

---

## Review Date Filtering

`review_time` format in SQLite is consistently `'YYYY-MM-DD HH:MM:SS'`.

Lexicographic string comparison works for year filtering:
```sql
-- Reviews from 2020 onwards
WHERE review_time >= '2020'
-- Reviews from 2020-01-01 onwards (same effect)
WHERE review_time >= '2020-01-01'
```

---

## Rating Field

- `review.rating` is stored as INTEGER (1–5), NOT float.
- `AVG(rating)` returns a float; compare with `= 5.0` or `= 5` for perfect rating.
- For Q2 (perfect 5.0 average): `HAVING AVG(rating) = 5`
- For Q3 (4.5+ average since 2020): `HAVING AVG(rating) >= 4.5 AND review_time >= '2020'`

---

## Query Patterns (No Answer Keys)

| Query | Required computation | Key Constraint |
|-------|----------------------|----------------|
| Q1: Decade with highest avg rating (≥10 distinct books) | Extract publication year, derive decade, aggregate avg rating by decade | decade computed from details/subtitle text |
| Q2: Literature/Fiction books with perfect avg | Filter category, join to review DB, keep groups with AVG(rating)=5 | categories LIKE '%Literature & Fiction%' |
| Q3: Children's books with ≥4.5 avg since 2020 | Filter category + date, aggregate by purchase/book | categories LIKE '%Children''s Books%', review_time >= '2020' |

Do not rely on memorized title lists. Always derive outputs from live query results.
