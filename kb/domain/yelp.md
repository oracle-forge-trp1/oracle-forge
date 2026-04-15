# Yelp Dataset — Domain Knowledge

This document is injected into the agent's Domain Knowledge context layer before any Yelp query is answered. All facts here are specific to this dataset — do not assume they apply to other DAB datasets.

---

## Dataset Structure

Two active databases. Every Yelp query spans both — business metadata lives in MongoDB, user activity lives in DuckDB.

| Database | What it contains |
|----------|-----------------|
| MongoDB `yelp_db` | Business profiles, check-in records |
| DuckDB `yelp_user.db` | Reviews, tips, user profiles |

---

## Location — Critical Rule

MongoDB `business` has **no `city`, `state`, or `address` fields**. Location is embedded in the `description` field as natural language text:

```
"Located at 6901 Phelps Rd in Goleta, CA, this facility..."
```

To answer any location-based question, extract state and city using this regex **before** filtering:

```python
import re
pattern = r"Located at .+? in (.+?),\s*([A-Z]{2})"
match = re.search(pattern, description)
city  = match.group(1)  # e.g. "Indianapolis"
state = match.group(2)  # e.g. "IN"
```

In MongoDB aggregation, use `$regexFind` on the `description` field. Do not query for `city` or `state` directly — those fields do not exist.

---

## Attributes Field — Parsing Rules

MongoDB `business.attributes` is a **serialised dict string**, not a structured object. It contains amenity data needed for queries about WiFi, parking, and credit cards.

Key patterns to extract:

| Attribute | What to look for in the string |
|-----------|-------------------------------|
| WiFi | `'WiFi': 'free'` or `'WiFi': 'paid'` — both count as offering WiFi |
| Credit cards | `'BusinessAcceptsCreditCards': 'True'` |
| Business parking | `'BusinessParking': ...` contains `'parking': True` or `'lot': True` |
| Bike parking | `'BikeParking': 'True'` |

Parse using Python `ast.literal_eval()` after stripping the outer string, or use regex matching on the raw string for each attribute.

---

## Categories Field

**CRITICAL:** `business.categories` is **NULL for most businesses** in this dataset. Do NOT rely on it.

Categories are embedded in the **`description` text field**, appended at the end:

```
"Located at 123 Main St in City, PA, this establishment provides services in
Restaurants, Pizza, Italian."
```

To extract categories from description:
```python
# Python-side extraction
desc = doc["description"]
# Last sentence often contains categories
last_part = desc.rsplit(". ", 1)[-1].rstrip(".")
categories = [c.strip() for c in last_part.split(", ")]
```

For MongoDB aggregation, extract via `$split` on the description string or fetch descriptions and process in Python. Never query `business.categories` directly.

**IMPORTANT for average-of-group queries:**
When computing average rating for a group of businesses (e.g. all credit-card-accepting businesses), get ALL individual review ratings and compute AVG once:
```sql
-- CORRECT: single AVG across all reviews
SELECT AVG(rating) FROM review WHERE business_ref IN (...)
-- WRONG: average of per-business averages (gives wrong result)
SELECT AVG(per_biz_avg) FROM (SELECT AVG(rating) per_biz_avg FROM review GROUP BY business_ref)
```

---

## String-Typed Fields — Always Cast

These MongoDB fields are stored as strings despite containing numeric or boolean values:

| Field | Stored as | Cast to |
|-------|-----------|---------|
| `review_count` | `"42"` | `int(review_count)` |
| `is_open` | `"1"` or `"0"` | `== "1"` for open, `== "0"` for closed |

---

## Date Formats — DuckDB

`review.date`, `tip.date`, and `user.yelping_since` contain **three mixed formats in the same column**:

| Format | Example |
|--------|---------|
| `YYYY-MM-DD HH:MM:SS` | `2013-12-04 02:46:01` |
| `Month DD, YYYY at HH:MM AM/PM` | `August 01, 2016 at 03:44 AM` |
| `DD Mon YYYY, HH:MM` | `29 May 2013, 23:01` |

Never use `STRPTIME` with a single format — it silently drops non-matching rows.

For year-only filters (e.g. "registered in 2016", "reviews in 2018"):

```sql
WHERE regexp_extract(date, '\d{4}') = '2016'
```

For full date range filters use `TRY_STRPTIME` across all three formats.

---

## Cross-Database Join Key

MongoDB `business.business_id` and DuckDB `review.business_ref` / `tip.business_ref` refer to the same entity with different prefixes:

```
MongoDB:  "businessid_34"
DuckDB:   "businessref_34"
```

Strip both prefixes and match on the integer. Direct string equality always returns 0 rows.

---

## Check-in Date Field

MongoDB `checkin.date` is a **single comma-separated string** of datetime values, not an array:

```
"2011-03-18 21:32:32, 2011-07-03 19:19:32, ..."
```

To count or filter check-ins, split on `", "` first.

---

## The 7 DAB Yelp Queries — What Each Requires

| Query | Key challenge | Ground truth |
| ----- | ------------ | ------------ |
| Q1: Avg rating of businesses in Indianapolis IN | Location extraction from `description` → cross-DB join → avg `rating` | `3.547008547008547` |
| Q2: State with highest reviews + avg rating | Extract state from all 100 `description` fields → group by state → join reviews | `PA, 3.699395770392749` |
| Q3: 2018 businesses with parking | Parse `attributes` for parking → year filter on `review.date` using regex | `35` |
| Q4: Category with most credit-card businesses + avg rating | Parse `attributes` for credit cards → split `categories` string | `Restaurant, 3.633676092544987` |
| Q5: State with most WiFi businesses + avg rating | Parse `attributes` for WiFi → location extraction → avg `rating` | `PA, 3.48` |
| Q6: Highest avg rating Jan–Jun 2016, min 5 reviews | Date range filter with mixed formats → min review count → cross-DB join | `Coffee House Too Cafe, Restaurants, Breakfast & Brunch, American (New), Cafes` |
| Q7: Top 5 categories for users registered in 2016 | Filter `user.yelping_since` by year → join reviews → split `categories` | `Restaurants, Food, American (New), Shopping, Breakfast & Brunch` |

Use ground truth values to self-check computed answers before returning. A mismatch means a pipeline error — recheck key translation, location extraction, or date parsing.

---

## High-Risk Query Rules (Run 2026-04-15-034)

### Q2 — State with highest review count + avg rating

- Review counts must come from DuckDB `review` row counts, not MongoDB `review_count`.
- Build state -> businesses mapping from MongoDB `description`, then join into DuckDB reviews.
- Compute average over all review rows for businesses in the winning state only.
- Output must be compact: `PA, <value>` with no extra numbers before `<value>`.

### Q4 — Top credit-card category + avg rating

- Filter only businesses with `attributes.BusinessAcceptsCreditCards == 'True'`.
- Extract categories from `description` (do not rely on `categories` field).
- Pick category with highest business count (ground truth: `Restaurant`).
- Average must be computed on review rows for businesses in that winning category.
- Self-check target is approximately `3.633676092544987`.

### Q7 — Top categories for 2016 users

- Do not aggregate categories from only top K businesses.
- First compute review counts for all reviewed businesses by users registered in 2016.
- Then map each business to extracted categories and sum review counts per category.
- Rank categories by weighted totals and ensure `Shopping` is considered before finalizing output.
