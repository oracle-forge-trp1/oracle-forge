# MusicBrainz 20K Domain Knowledge

## Dataset Overview

| Database | Type | Logical Name | Table | Key Fields |
|----------|------|--------------|-------|------------|
| tracks.db | SQLite | tracks_database | tracks | track_id, source_id, source_track_id, title, artist, album, year, length, language |
| sales.duckdb | DuckDB | sales_database | sales | sale_id, track_id, country, store, units_sold, revenue_usd |

---

## Cross-Database Join Keys

- SQLite `tracks.track_id` → DuckDB `sales.track_id`
- Format is consistent — direct integer/string match. **No prefix mismatch.**

---

## CRITICAL: Entity Resolution Required

The `tracks` table contains **duplicate entries** — different `track_id`s can represent the **same real-world track**.

**Do NOT assume track_id is unique per real-world track.** Duplicates may differ in:
- `year` format (e.g., "2005" vs "05")
- Minor attribute variations (capitalization, spacing)
- Different `source_id` / `source_track_id` (from different catalogs)

**To answer queries correctly, perform entity resolution** by comparing:
- `title` (primary match)
- `artist` (secondary match)
- `album` (tertiary match)

```python
# Example: Find unique tracks
# Do NOT just COUNT(DISTINCT track_id) — this overcounts
# Instead group by (title, artist) or similar
```

```sql
-- Approximate deduplication
SELECT LOWER(title) as norm_title, LOWER(artist) as norm_artist,
       COUNT(*) as duplicates
FROM tracks
GROUP BY LOWER(title), LOWER(artist)
HAVING COUNT(*) > 1
```

---

## Schema Reference

Sales span 5 countries and 5 stores:

| Countries | Stores |
|---|---|
| USA, UK, Canada, Germany, France | iTunes, Spotify, Apple Music, Amazon Music, Google Play |

```sql
-- DuckDB: Revenue by country
SELECT country, SUM(revenue_usd) as total_revenue
FROM sales
GROUP BY country
ORDER BY total_revenue DESC

-- DuckDB: Top tracks by units sold
SELECT track_id, SUM(units_sold) as total_units
FROM sales
GROUP BY track_id
ORDER BY total_units DESC
LIMIT 10
```

---

## Data Semantics

- `source_id` — identifies the catalog source (MusicBrainz, external)
- `source_track_id` — ID from the originating catalog
- `track_id` — internal unique ID (but NOT unique per real-world track due to duplicates)

---

## Query Strategy Playbook

### Cross-DB: Track info + sales
```python
# Step 1: Find tracks matching criteria in SQLite
tracks = query_sqlite("tracks_database",
    "SELECT track_id, title, artist FROM tracks WHERE language = 'English'")

# Step 2: Get sales for those tracks from DuckDB
track_ids = [t["track_id"] for t in tracks]
placeholders = ",".join(str(tid) for tid in track_ids)
sales = query_duckdb("sales_database",
    f"SELECT track_id, SUM(revenue_usd) as revenue FROM sales WHERE track_id IN ({placeholders}) GROUP BY track_id")
```

### Entity resolution + aggregation
For queries asking about "unique tracks" or "distinct songs":
1. Query SQLite tracks table
2. Deduplicate by (title, artist) — case-insensitive
3. Map deduplicated tracks to all their track_ids
4. Aggregate sales across all track_ids for each real-world track

---

## Common Pitfalls

- Treating `track_id` as one-to-one with real-world songs.
- Deduplicating by title only and merging different artists' tracks.
- Aggregating sales before entity resolution, which inflates duplicates.
- Mixing language/year normalization rules inconsistently across grouping steps.
- Assuming one source catalog; `source_id` fragmentation can hide duplicate entities.

---

## Validation Checklist

- Duplicate audit: count candidate duplicate groups by normalized `(title, artist)`.
- Merge quality: sample merged groups for false merges/splits.
- Sales conservation: verify total revenue/units preserved pre/post dedup rollup.
- Join coverage: percentage of deduped tracks with matching sales rows.
- Country/store sanity: confirm expected domain values before final ranking.

---

## Leakage-Safe Policy

- Do not include expected top tracks, fixed ranking outputs, or target numeric answers.
- Keep guidance focused on entity resolution mechanics and aggregation correctness.
- Historical notes must describe failure modes, not benchmark-specific outcomes.
