# StockIndex Domain Knowledge (Leakage-Safe)

## Scope

This file contains methodology and schema interpretation guidance only.
Do not store or use query-specific precomputed outputs, ranked winner lists, restricted symbol lists, or fixed numeric targets.

---

## Leakage-Safe Policy

- No query-specific precomputed outputs or fixed ranked winners.
- No restricted symbol lists or fixed numeric targets.
- Keep only reusable methodology and schema interpretation guidance.

---

## Dataset Overview

Two databases are used in this dataset:

| Database | Type | Logical Name | Table | Key Fields |
|----------|------|--------------|-------|------------|
| indexInfo_query.db | SQLite | indexinfo_database | index_info | Exchange (text), Currency (text) |
| indextrade_query.db | DuckDB | indextrade_database | index_trade | Index (text), Date (text), Open, High, Low, Close, Adj Close, CloseUSD (numeric) |

There is no direct relational foreign key between the two tables. Region/country attributes are often inferred from exchange metadata.

---

## Cross-Database Join Keys

There is no strict foreign-key join path between `index_info` and `index_trade`.
Use symbol/exchange context alignment and runtime-derived mapping logic when combining metadata with trade aggregates.

---

## Schema Reference

Resolve symbol geography from data at runtime instead of relying on pre-listed winners.

Recommended pattern:

```sql
SELECT Exchange, Currency
FROM index_info;
```

Then build region grouping logic from exchange names in your query plan.
Do not hardcode final winners or ranked outputs.

---

## Query Strategy Playbook

### Intraday Volatility

```sql
SELECT "Index",
  AVG(("High" - "Low") / NULLIF("Open", 0)) AS avg_volatility
FROM index_trade
WHERE <date filter>
GROUP BY "Index"
ORDER BY avg_volatility DESC
```

Use the winner row from query output. Do not assume the winner in advance.

### Up/Down Day Definition

Use intraday movement:

```sql
SUM(CASE WHEN "Close" > "Open" THEN 1 ELSE 0 END) AS up_days,
SUM(CASE WHEN "Close" < "Open" THEN 1 ELSE 0 END) AS down_days
```

Avoid day-over-day substitutes (`Close > previous Close`) unless the question explicitly asks for day-over-day logic.

### Periodic Investment Style Queries

When a prompt asks for regular/monthly investments, avoid naive first-to-last buy-and-hold unless explicitly requested.
Use month-bucketed return aggregation when the question describes periodic contributions.

```sql
WITH parsed AS (
  SELECT "Index",
    COALESCE(
      TRY_STRPTIME("Date", '%Y-%m-%d %H:%M:%S'),
      TRY_STRPTIME("Date", '%B %d, %Y at %I:%M %p'),
      TRY_STRPTIME("Date", '%d %b %Y, %H:%M'),
      TRY_STRPTIME("Date", '%d %B %Y, %H:%M'),
      TRY_STRPTIME("Date", '%B %d, %Y at %H:%M'),
      TRY_STRPTIME("Date", '%m/%d/%Y %H:%M:%S')
    ) AS dt,
    "CloseUSD"
  FROM index_trade
),
monthly AS (
  SELECT "Index", DATE_TRUNC('month', dt) AS month,
    FIRST("CloseUSD" ORDER BY dt) AS open_price,
    LAST("CloseUSD" ORDER BY dt)  AS close_price
  FROM parsed
  WHERE dt IS NOT NULL AND "CloseUSD" IS NOT NULL AND "CloseUSD" > 0
  GROUP BY "Index", DATE_TRUNC('month', dt)
)
SELECT "Index", SUM(close_price / open_price - 1) * 100 AS total_return
FROM monthly
GROUP BY "Index"
ORDER BY total_return DESC;
```

---

## Data Semantics

The `Date` field can contain mixed formats in the same column.
Always use multi-pattern `COALESCE(TRY_STRPTIME(...))` and filter out null parse results.

---

## Output Policy

- Compute answers from tool/query outputs at runtime.
- Do not rely on memorized benchmark outputs.
- For single-winner questions, return only the winner.
- For paired outputs (symbol + country/value), keep values adjacent in compact plain text.

---

## Geography and exchange filters

- Questions may name a **region** (for example North America, Asia). **Do not** rank symbols from exchanges outside that region.
- Always join or filter using `index_info` (exchange names, currency, and related metadata) to build the **eligible symbol set** before computing extrema on `index_trade`.
- A symbol that appears in price data but whose primary listing exchange is outside the filtered region must be excluded from the winner set for that question.

---

## Common Pitfalls

- Applying a single date parser to mixed-format `Date` values.
- Using day-over-day movement when question intent is intraday movement.
- Hardcoding exchange-to-region mappings without checking `index_info` contents.
- Mixing `Close` and `CloseUSD` in one calculation without explicit conversion intent.
- Ranking on unstable denominators (for example, tiny sample months).

---

## Validation Checklist

- Date parse success: parsed/non-parsed row counts after multi-pattern parsing.
- Metric unit check: verify whether formula uses local close or USD-normalized close.
- Sample-size guard: minimum row/month counts per index before ranking.
- Join/context sanity: ensure exchange/currency mapping exists for ranked symbols.
- Recompute check: rerun top candidates with narrowed filters to confirm stability.
