# Google Local Domain Knowledge

## Dataset Overview

| Database | Type | Logical Name | Table | Key Fields |
|----------|------|--------------|-------|------------|
| business_description.sql | PostgreSQL | business_database | business_description | gmap_id, name, description, hours, status, review_count |
| review_query.db | SQLite | review_database | review | gmap_id, reviewer_name, rating, text |

Data covers US-only Google Maps businesses and reviews through September 2021.

---

## Cross-Database Join Keys

- PostgreSQL `business_description.gmap_id` → SQLite `review.gmap_id`
- Format is consistent — direct string equality works. **No prefix mismatch.**

---

## Schema Reference

`business_description.description` is a **text field** containing business metadata:
- Business type/category
- Services offered
- Location details
- Operating hours summary

Use `ILIKE` (PostgreSQL) for searching:
```sql
SELECT gmap_id, name, description FROM business_description
WHERE description ILIKE '%restaurant%'
```

---

## Data Semantics

`review.text` is free-form review text from Google Maps users. For queries requiring sentiment or topic analysis:
- Simple: `WHERE text LIKE '%keyword%'`
- Complex: Pull reviews and classify with LLM

---

## Query Strategy Playbook

### Business + review aggregation
```python
# Step 1: Filter businesses in PostgreSQL
businesses = query_postgres("business_database",
    "SELECT gmap_id, name FROM business_description WHERE description ILIKE '%pizza%'")

# Step 2: Get reviews from SQLite
gmap_ids = [b["gmap_id"] for b in businesses]
placeholders = ",".join(f"'{gid}'" for gid in gmap_ids)
reviews = query_sqlite("review_database",
    f"SELECT gmap_id, AVG(rating) as avg_rating FROM review WHERE gmap_id IN ({placeholders}) GROUP BY gmap_id")
```

### Rating analysis
```sql
-- SQLite: Average rating per business
SELECT gmap_id, AVG(rating) as avg_rating, COUNT(*) as review_count
FROM review
GROUP BY gmap_id
HAVING COUNT(*) >= 5
ORDER BY avg_rating DESC
```

---

## Data Timeframe
Data goes through September 2021. "Recent" in queries means late 2021, not current date.

---

## Common Pitfalls

- Filtering location/business type only in one DB when the signal is split across both.
- Using inner joins too early and dropping businesses with sparse review coverage.
- Treating `description` as normalized taxonomy instead of noisy free text.
- Averaging per-business averages when query intent requires review-level aggregates.
- Ignoring timeframe boundaries and interpreting "recent" as current-year data.

---

## Validation Checklist

- Join coverage: `%` of filtered businesses with at least one review row.
- Text filter quality: sample false-positive/false-negative matches for key terms.
- Aggregate definition: verify denominator (reviews vs businesses) matches query intent.
- Outlier control: inspect businesses with extreme ratings at low review counts.
- Time sanity: min/max timestamps align with dataset cutoff (through Sep 2021).

---

## Leakage-Safe Policy

- No fixed expected winners, benchmark counts, or query-by-query outputs.
- Preserve only durable methods: join sequencing, text filtering, and aggregate validation.
- Examples must stay procedural and non-answer-bearing.
