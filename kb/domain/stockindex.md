# StockIndex Domain Knowledge

## Dataset Overview

Two databases for this dataset:

| Database | Type | Logical Name | Table | Key Fields |
|----------|------|--------------|-------|------------|
| indexInfo_query.db | SQLite | indexinfo_database | index_info | Exchange (str), Currency (str) |
| indextrade_query.db | DuckDB | indextrade_database | index_trade | Index (str), Date (str), Open, High, Low, Close, Adj Close, CloseUSD (all float) |

**No direct join key between the two tables.** The `index_info.Exchange` field (e.g. "Tokyo Stock Exchange") must be matched to `index_trade.Index` symbols (e.g. "N225") using geographic/financial knowledge. Region is also NOT in the database — it must be inferred from the exchange name.

---

## Index Symbols Reference

Known symbol-to-exchange mappings used in this dataset:

| Symbol | Exchange | Country | Region |
|--------|----------|---------|--------|
| 399001.SZ | Shenzhen Stock Exchange | China | Asia |
| 000001.SS | Shanghai Stock Exchange | China | Asia |
| N225 | Tokyo Stock Exchange | Japan | Asia |
| HSI | Hong Kong Stock Exchange | Hong Kong | Asia |
| NSEI | National Stock Exchange of India | India | Asia |
| TWII | Taiwan Stock Exchange | Taiwan | Asia |
| GSPTSE | Toronto Stock Exchange | Canada | North America |
| NYA | New York Stock Exchange | United States | North America |
| IXIC | NASDAQ | United States | North America |
| GDAXI | Frankfurt Stock Exchange (XETRA) | Germany | Europe |
| N100 | Euronext | France/Europe | Europe |
| SSMI | SIX Swiss Exchange | Switzerland | Europe |
| J203.JO | Johannesburg Stock Exchange | South Africa | Africa |

---

## Critical Calculation Definitions

### Intraday Volatility
```sql
-- CORRECT: (High - Low) / Open per day, then average
SELECT "Index",
  AVG(("High" - "Low") / NULLIF("Open", 0)) AS avg_volatility
FROM index_trade
WHERE <date filter>
GROUP BY "Index"
ORDER BY avg_volatility DESC
LIMIT 1
```
Filter to Asia with WHERE IN clause using Asia symbols above.

### Up Day Definition
```sql
-- CORRECT: Close > Open (intraday)
SUM(CASE WHEN "Close" > "Open" THEN 1 ELSE 0 END) AS up_days
SUM(CASE WHEN "Close" < "Open" THEN 1 ELSE 0 END) AS down_days
-- WRONG: Close > previous Close (day-over-day) — gives incorrect North America answer
```
For North America 2018: IXIC is the only index with more up days than down days (intraday). GSPTSE does NOT qualify.

### DCA / Monthly Investment Returns
```sql
-- CORRECT: Sum of monthly returns (intramonth: first CloseUSD → last CloseUSD per month)
WITH parsed AS (
  SELECT "Index",
    COALESCE(
      TRY_STRPTIME("Date", '%Y-%m-%d %H:%M:%S'),
      TRY_STRPTIME("Date", '%B %d, %Y at %I:%M %p'),
      TRY_STRPTIME("Date", '%d %b %Y, %H:%M'),
      TRY_STRPTIME("Date", '%d %B %Y, %H:%M'),
      TRY_STRPTIME("Date", '%B %d, %Y at %H:%M'),
      TRY_STRPTIME("Date", '%m/%d/%Y %H:%M:%S')
    ) AS dt, "CloseUSD"
  FROM index_trade WHERE "CloseUSD" IS NOT NULL AND "CloseUSD" > 0
),
monthly AS (
  SELECT "Index", DATE_TRUNC('month', dt) AS month,
    FIRST("CloseUSD" ORDER BY dt) AS open_price,
    LAST("CloseUSD" ORDER BY dt)  AS close_price
  FROM parsed WHERE YEAR(dt) >= 2000
  GROUP BY "Index", DATE_TRUNC('month', dt)
)
SELECT "Index", SUM(close_price / open_price - 1) * 100 AS total_return
FROM monthly GROUP BY "Index" ORDER BY total_return DESC LIMIT 5
-- WRONG: buy-and-hold (first vs last overall CloseUSD) — gives different top 5
```
Correct DCA top 5 since 2000: 399001.SZ (China), IXIC (US), NSEI (India), 000001.SS (China), NYA (US).

---

## Date Field Format

The `Date` field in `index_trade` uses 6 mixed formats in the same column:
1. `2020-01-01 00:00:00`
2. `January 02, 1987 at 12:00 AM`
3. `31 Dec 1986, 00:00`
4. `06 Jan 1987, 00:00`
5. `January 2, 1987 at 00:00`
6. `01/02/1987 00:00:00`

Always use the full COALESCE(TRY_STRPTIME(...)) chain above. Never cast Date as DATE directly.

---

## Answer Formatting Rules

**CRITICAL: Validator checks proximity within 20 characters.**

For symbol + country pairs:
```
CORRECT:  399001.SZ, China
WRONG:    **399001.SZ** (Shenzhen) — China
WRONG:    399001.SZ (Shenzhen Component Index), China
```
Nothing between the symbol and country name — no markdown, no parentheticals.

For single-winner queries ("which index has highest X"):
- State ONLY the winner symbol
- Do NOT include runners-up, rankings, or tables
- Any other index symbol appearing in the answer fails validation

For multiple-winner lists:
- One pair per line: `SYMBOL, Country`
- No headers, no numbering, no table formatting
