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

`business.categories` is a **comma-separated string** of category names:

```
"Restaurants, Italian, Pizza"
```

To find businesses in a category, use case-insensitive substring match. Do not expect exact single-value entries.

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
