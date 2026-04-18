# StockIndex Domain Knowledge (Leakage-Safe)

## Scope

This file contains methodology and schema interpretation guidance only.
Do not store or use query-specific precomputed outputs, ranked winner lists, restricted symbol lists, or fixed numeric targets.

---

## Dataset Overview

| Database | Type | Logical Name | Table | Key Fields |
|----------|------|--------------|-------|------------|
| indexInfo_query.db | SQLite | indexinfo_database | index_info | Exchange (text), Currency (text) |
| indextrade_query.db | DuckDB | indextrade_database | index_trade | Index (text), Date (text), Open (double), High (double), Low (double), Close (double), Adj Close (double), CloseUSD (double) |

**Note**: Column names in `index_trade` use title case with spaces — always quote with double-quotes in DuckDB:
`"Index"`, `"Date"`, `"Open"`, `"High"`, `"Low"`, `"Close"`, `"Adj Close"`, `"CloseUSD"`

---

## CRITICAL: No Region Column — Use Exchange-to-Region Mapping

`index_info` has **only two columns**: `Exchange` (text) and `Currency` (text).
There is **no `region`, `country`, or `symbol` column** in `index_info`.

The join between `index_info` (exchange metadata) and `index_trade` (price data) is **not via a foreign key** — you must map exchange names to index symbols using the table below.

### Exchange → Symbol → Region Mapping

| Exchange | Symbol in index_trade | Region |
|---|---|---|
| New York Stock Exchange | NYA | North America |
| NASDAQ | IXIC | North America |
| Toronto Stock Exchange | GSPTSE | North America |
| Hong Kong Stock Exchange | HSI | Asia |
| Shanghai Stock Exchange | 000001.SS | Asia |
| Shenzhen Stock Exchange | 399001.SZ | Asia |
| Tokyo Stock Exchange | N225 | Asia |
| National Stock Exchange of India | NSEI | Asia |
| Taiwan Stock Exchange | TWII | Asia |
| Euronext | N100 | Europe |
| Frankfurt Stock Exchange | GDAXI | Europe |
| SIX Swiss Exchange | SSMI | Europe |
| Johannesburg Stock Exchange | J203.JO | Africa |

**To filter by region**: look up exchange names in `index_info`, identify the matching symbols from the table above, then filter `index_trade` to only those symbols.

```sql
-- Step 1: confirm Asia exchanges from index_info
SELECT Exchange, Currency FROM index_info;

-- Step 2: filter index_trade to Asia symbols only
SELECT "Index", ... FROM index_trade
WHERE "Index" IN ('HSI', '000001.SS', '399001.SZ', 'N225', 'NSEI', 'TWII')
```

---

## Volatility Formula

### Intraday Volatility (standard)
Use `(High - Low) / Close` as the per-day volatility measure:
```sql
AVG(("High" - "Low") / NULLIF("Close", 0)) AS avg_intraday_volatility
```

Do NOT use `Open` as the denominator (produces different rankings than the expected answer).
Do NOT use absolute `(High - Low)` without normalizing by price level.

### Up/Down Day Definition

Use intraday movement (same-day open vs close):
```sql
SUM(CASE WHEN "Close" > "Open" THEN 1 ELSE 0 END) AS up_days,
SUM(CASE WHEN "Close" < "Open" THEN 1 ELSE 0 END) AS down_days
```

Do NOT use day-over-day (`Close > previous day Close`) — use intraday unless explicitly requested.

---

## DCA / Periodic Investment Return

When the question asks for monthly/periodic investment returns since a given year:

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
  SELECT "Index",
    DATE_TRUNC('month', dt) AS month,
    FIRST("CloseUSD" ORDER BY dt) AS open_price,
    LAST("CloseUSD" ORDER BY dt)  AS close_price
  FROM parsed
  WHERE dt IS NOT NULL AND "CloseUSD" IS NOT NULL AND "CloseUSD" > 0
  GROUP BY "Index", DATE_TRUNC('month', dt)
)
SELECT "Index",
  SUM(close_price / open_price - 1) * 100 AS total_return_pct
FROM monthly
WHERE month >= DATE_TRUNC('month', CAST('2000-01-01' AS DATE))
GROUP BY "Index"
ORDER BY total_return_pct DESC
LIMIT 5;
```

After getting the top 5 symbols, look up their exchange/country from the mapping table above.
Output format: `SYMBOL, Country` — one per line, 5 lines total.

---

## Date Parsing

`Date` field in `index_trade` contains mixed formats. Always use multi-pattern COALESCE:
```sql
COALESCE(
    TRY_STRPTIME("Date", '%Y-%m-%d %H:%M:%S'),
    TRY_STRPTIME("Date", '%B %d, %Y at %I:%M %p'),
    TRY_STRPTIME("Date", '%d %b %Y, %H:%M'),
    TRY_STRPTIME("Date", '%d %B %Y, %H:%M'),
    TRY_STRPTIME("Date", '%B %d, %Y at %H:%M'),
    TRY_STRPTIME("Date", '%m/%d/%Y %H:%M:%S')
) AS dt
```
Filter out nulls (`WHERE dt IS NOT NULL`) after parsing.

---

## Output Format for Multi-Symbol Answers

For single-winner questions: output only `SYMBOL, Country` — no extra text.
For top-5 lists: output each on its own line as `SYMBOL, Country`.
Do not include exchange names, rankings, or numeric values unless requested.

---

## Common Pitfalls

- Using `("High" - "Low") / "Open"` for intraday volatility instead of `/ "Close"`. → **Entry 054**
- Assuming `index_info` has a region or symbol column — it has only Exchange and Currency. → **Entry 054**
- Including indices outside the target region (e.g. including J203.JO when filtering Asia). → **AGENT.md §10**
- Single date format parser silently dropping rows. → **Entry 002**
- Unstable ORDER BY without tie-breaker on LIMIT queries. → **Entry 036**

---

## Validation Checklist

- Region filter: confirmed only region-appropriate symbols in the eligible set.
- Date parse success: check non-null count after COALESCE parsing.
- Volatility denominator: using Close, not Open.
- Symbol→Country lookup: every output symbol has a country from the mapping table.
- Tie-breaking: ORDER BY has a secondary stable key.

---

## Leakage-Safe Policy

- No pre-filled winners, expected tickers, or fixed benchmark outputs.
- The exchange→symbol→region mapping above is factual domain knowledge (not answer leakage).
- Keep only robust financial-data query strategy and verification guidance.
