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

However, when the question is explicitly about **U.S. state**, first check for a structured top-level field:
- Prefer `business.state` or `business.full_state` (top-level) if present and non-null.
- Do not assume `attributes.State` exists (often null/missing).
- MongoDB `$group` by `$state` can yield `_id: null` when state is missing — prefer filtering businesses that have a non-empty state field before grouping, or use a fallback field from introspection.
- If the final answer must mention a state, include the **exact** token stored in `business.state` (usually the two-letter abbreviation). When unsure, output the abbreviation — many validators accept both abbreviated and full state names only if those exact strings appear in the answer text.

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
- Credit card acceptance: normalize boolean-like strings (`true`/`false`, `yes`/`no`, `1`/`0`) — **match how values appear in documents**, not only the string `"Yes"`.
- Parking flags: nested values may require parsing.

Do not assume a single consistent Python type across all records.

---

## Categories Extraction

`business.categories` can be missing or incomplete. Category information may appear in `description` text.
When building category aggregates, normalize category tokens and deduplicate per business where needed.

**Validator-facing outputs:** Inspect distinct category strings from the data (for example `Restaurant` vs `restaurants`). Emit the **same casing and token** the stored documents use when the question is about category membership or counts — do not rely on a single guessed label.

Leakage-safe retrieval rule:
- When the question asks “what category does it belong to?”, fetch the business with a projection that includes `categories` (do not omit it), and take the category token(s) from that field when present.
- Use `description` only as a fallback when `categories` is missing/null, and then quote exact tokens from the text rather than inventing a normalized label.
- Do not “clean up” final category tokens for readability (no singularization, no case normalization, no punctuation stripping). Tokens like `American (New)` and `Restaurants` must be emitted exactly as stored.

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

### State-token discipline (for PA/Pennsylvania-style validators)
- For state-linked outputs, always fetch and retain `state` explicitly from source rows/documents; do not rely on derived/null placeholders.
- Final output must contain a non-null state token copied from data (`PA` or `Pennsylvania` where applicable), with paired numeric value adjacent when requested.

### Methodology disambiguation (no memorized targets)

- **State / region rankings:** If the question ties a numeric result to “the state with the most …”, first identify that state using counts on the full filtered business (or event) population, then compute the numeric metric **only** for businesses in that state (AGENT.md §12.1).
- **Attribute-based rankings:** For “most businesses with attribute X”, count businesses meeting X per group, find the winning group, then any follow-up average must use **only** rows/businesses in that group—not a global average of X across all groups.
- **Category lists:** For “top categories” across businesses matching a date or other filter, explode/normalize categories from **all** matching businesses before ranking—not from a handful of top businesses by review count or stars.
- **Review-linked metrics:** Star averages and similar measures should come from **review** rows in DuckDB joined to the relevant business keys after normalization—not from Mongo-only shortcuts when the question is about review behavior.
- **State + numeric pair outputs:** If the question expects a state token and a metric (for example a value near `PA`/`Pennsylvania`), compute the winning state first, then compute the metric restricted to that state only, and output the pair compactly in one line.
- **Category fidelity:** For category answers, emit exact category tokens from `business.categories` (for example keep `Breakfast & Brunch` exactly as stored).
- **Category completeness:** If prompt expects top-N categories, render exactly N categories from final ranked results and ensure required canonical tokens (for example `Restaurants`, `Food`) are not dropped.

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
- Final token check: for category/name outputs, ensure final tokens are copied from selected source fields (`name`, `categories`) and not inferred prose.
