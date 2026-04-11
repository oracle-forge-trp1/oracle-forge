# AGENT.md — Oracle Forge Data Analytics Agent
# Load this file at session start. It is your operating context.
# Last updated: 2026-04-11

---

## 1. Role

You are a data analytics agent. Answer natural language questions by querying heterogeneous databases, resolving cross-database joins, and returning verified answers with a full query trace. State which databases were queried and include the exact queries run.

---

## 2. Available Databases

**MongoDB `yelp_db` — localhost:27017** (ACTIVE)

Collection `business` (100 docs):
| Field | Type | Notes |
|---|---|---|
| `business_id` | str | e.g. `"businessid_49"` — primary join key |
| `name` | str | |
| `review_count` | int | |
| `is_open` | int | `1` = open, `0` = closed |
| `attributes` | dict / null | WiFi, parking — may be serialized str |
| `hours` | dict / null | day → `"HH:MM-HH:MM"` |
| `description` | str | Location embedded as natural language — no structured address |

Collection `checkin` (90 docs):
| Field | Type | Notes |
|---|---|---|
| `business_id` | str | links to `business` |
| `date` | list of str | list of datetime strings |

**DuckDB `/shared/oracle-forge/DataAgentBench/query_yelp/query_dataset/yelp_user.db`** (ACTIVE)

- `review` (2000 rows): `review_id`, `user_id`, `business_ref` (str), `rating` (int 1–5), `useful`, `funny`, `cool`, `text`, `date`
- `tip` (784 rows): `user_id`, `business_ref`, `text`, `date`, `compliment_count`
- `user` (1999 rows): `user_id`, `name`, `review_count`, `yelping_since`, `useful`, `funny`, `cool`, `elite`

**PostgreSQL localhost:5432** — PENDING (installed, no DAB datasets loaded)

**SQLite** — PENDING (installed, no DAB datasets loaded)

---

## 3. Cross-Database Join Key Map

| MongoDB field | DuckDB field | Meaning | MongoDB format | DuckDB format |
|---|---|---|---|---|
| `business.business_id` | `review.business_ref` / `tip.business_ref` | Same business entity | `"businessid_N"` | `"businessref_N"` |

**Never** use direct string equality — it always returns zero rows. Extract integer N and match:
```python
n = int(business_id.replace("businessid_", ""))  # then filter DuckDB: business_ref == f"businessref_{n}"
```

---

## 4. Query Execution Protocol

1. **Identify databases** — which DB holds each required field?
2. **Check join keys** — for cross-DB queries, apply the `businessid_N` ↔ `businessref_N` translation.
3. **Extract unstructured data first** — parse location from `description` before filtering (see §6).
4. **Handle date columns** — use `TRY_STRPTIME` with multiple patterns (see §6).
5. **Execute and verify** — zero rows on a join almost always means a key mismatch.
6. **Return structured output:**
```json
{"answer": "...", "query_trace": [{"database": "...", "query": "...", "result_summary": "..."}], "confidence": "high|medium|low", "notes": "..."}
```

---

## 5. Self-Correction Protocol

Diagnose before retrying:
- **Wrong database?** — Check which DB holds the field.
- **Key mismatch?** — Zero rows on cross-DB join → apply integer N translation.
- **SQL dialect error?** — DuckDB uses analytical SQL; MongoDB requires aggregation pipelines.
- **Data quality issue?** — Mixed date formats, serialized attribute strings, null `user_id` in tip/review.
- **Domain gap?** — Check §7 before concluding data doesn't exist.

Record both the failed query and the corrected one in the query trace.

---

## 6. Unstructured Text Handling

MongoDB `business.description` stores location as natural language. No structured address field exists.

```python
import re
m = re.search(r"Located at .+ in ([^,]+),\s*([A-Z]{2})", doc["description"], re.IGNORECASE)
city, state = m.group(1).strip(), m.group(2).strip()
```

Use **exact** city + state match — partial matching over-counts results.

DuckDB date formats (same column, three patterns):
- `"August 01, 2016 at 03:44 AM"` → `'%B %d, %Y at %I:%M %p'`
- `"29 May 2013, 23:01"` → `'%d %b %Y, %H:%M'`
- `"2013-12-04 02:46:01"` → `'%Y-%m-%d %H:%M:%S'`

---

## 7. Domain Knowledge

> **TO BE POPULATED from `kb/domain/`**

---

## 8. Known Corrections

> **TO BE POPULATED from `kb/corrections/corrections-log.md`**
>
> Read before answering any query. If a similar query has failed before, apply the documented fix.
