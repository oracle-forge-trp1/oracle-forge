# Yelp Domain Knowledge (Leakage-Safe)

## Scope

This file contains data-shape and methodology guidance only.
Do not include query-by-query answer keys, expected output strings, fixed winners, or ground-truth values.

---

## Dataset Overview

Two active databases are used:

| Database | Purpose |
|----------|---------|
| MongoDB `yelp_db` | Business metadata, check-ins |
| DuckDB `yelp_user.db` | Reviews, tips, user profiles |

Most questions require combining both systems.

---

## Schema Reference

MongoDB `business` does not expose normalized `city`/`state` columns in many records.
Location is often encoded in `description` text and must be parsed before filtering/grouping.

Example extraction pattern:

```python
import re
pattern = r"Located at .+? in (.+?),\s*([A-Z]{2})"
match = re.search(pattern, description)
if match:
    city = match.group(1)
    state = match.group(2)
```

In aggregation workflows, use regex/text functions over `description` instead of assuming structured location fields.

---

## Attributes Parsing

`business.attributes` can be string-encoded or mixed-typed and may require normalization.

Common checks:
- WiFi: detect string content robustly (for example, free/paid variants).
- Credit card acceptance: normalize boolean-like strings.
- Parking flags: nested values may require parsing.

Do not assume a single consistent Python type across all records.

---

## Categories Extraction

`business.categories` can be missing or incomplete. Category information may appear in `description` text.
When building category aggregates, normalize category tokens and deduplicate per business where needed.

For aggregate rating questions:
- Compute over raw review rows in DuckDB.
- Avoid averaging a set of per-business averages.

```sql
SELECT AVG(rating)
FROM review
WHERE business_ref IN (...)
```

---

## Data Semantics

Some MongoDB fields are string-typed even when semantically numeric/boolean.
Cast/normalize before comparison or arithmetic.

Typical examples:
- `review_count`: cast to integer
- `is_open`: compare to string flags like `"1"`/`"0"`

---

## Date Parsing

DuckDB date fields can include multiple formats in the same column.
Use `TRY_STRPTIME` with multiple patterns and `COALESCE` rather than a single parser.

For year-only filters, regex year extraction is often the safest approach.

---

## Cross-Database Join Keys

Business identifiers may use different prefixes across MongoDB and DuckDB.
Normalize each id to a shared canonical form before joining.

Example pattern:
- MongoDB: `businessid_<N>`
- DuckDB: `businessref_<N>`

Join using normalized `<N>`.

---

## Check-in Field Shape

`checkin.date` may be a single comma-separated string containing multiple timestamps.
Split before counting/filtering event instances.

---

## Query Strategy Playbook

- Compute answers from live tool outputs.
- Do not use memorized expected values.
- Keep final outputs compact and plain text for validator compatibility.

---

## Leakage-Safe Policy

- Keep content methodological and runtime-derivable.
- Do not store fixed benchmark outputs or precomputed winners.
- Favor reusable parsing/join/validation guidance over query-specific shortcuts.

---

## Common Pitfalls

- Joining Mongo and DuckDB IDs without canonical normalization.
- Assuming structured city/state fields always exist in business records.
- Aggregating per-business averages when question requires review-level aggregation.
- Failing to parse multi-value check-in strings before event counts.
- Treating mixed-type attribute values as uniformly typed booleans/numbers.

---

## Validation Checklist

- ID join quality: matched/unmatched counts after normalization.
- Location extraction quality: sample precision/recall from description parsing.
- Aggregate denominator check: reviews vs businesses vs users clearly separated.
- Type normalization audit: count rows requiring cast/fallback per key field.
- Temporal parsing audit: parse-success rate across mixed date formats.
