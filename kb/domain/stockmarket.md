# Stock Market Domain Knowledge

## Dataset Overview

| Database | Type | Logical Name | Contents |
|----------|------|--------------|---------|
| stockinfo_query.db | SQLite | stockinfo_database | `stockinfo` table — 2,752 securities metadata |
| stocktrade_query.db | DuckDB | stocktrade_database | 2,753 individual ticker tables — daily OHLCV data |

---

## CRITICAL: DuckDB Has No `stock_trade` Table

**There is NO single `stock_trade` table in DuckDB.**
Instead, each ticker symbol has its own table. The table name IS the ticker symbol.

```sql
-- Query one ticker:
SELECT * FROM "AAPL" WHERE Date >= '2020-01-01'

-- List all available ticker tables:
SHOW TABLES;
```

**Pattern for multi-ticker queries:**
1. Get qualifying ticker symbols from SQLite
2. For each ticker, query its individual DuckDB table
3. Aggregate results across tickers in Python

Example for finding ETFs on NYSE Arca below $1 at any point in 2020-2022:
```python
# Step 1: get qualifying tickers from SQLite
etf_tickers = query_sqlite("stockinfo_database",
    "SELECT Symbol FROM stockinfo WHERE ETF='Y' AND \"Listing Exchange\"='P'")

# Step 2: for each ticker, check DuckDB
results = []
for row in etf_tickers["data"]:
    ticker = row["Symbol"]
    res = query_duckdb("stocktrade_database",
        f'SELECT \'{ticker}\' AS symbol, MIN("Adj Close") AS min_adj_close '
        f'FROM "{ticker}" '
        f'WHERE "Date" >= \'2020-01-01\' AND "Date" <= \'2022-12-31\'')
    if res["data"] and res["data"][0]["min_adj_close"] is not None:
        if res["data"][0]["min_adj_close"] < 1.0:
            results.append(ticker)
```

---

## CRITICAL: SQLite Column Names (Use Exact Quoted Names)

The actual column names in `stockinfo` use display names with spaces:

| Column Name | Meaning |
|---|---|
| `Symbol` | Ticker symbol (join key with DuckDB table names) |
| `Listing Exchange` | Exchange code (see mapping below) |
| `Market Category` | NASDAQ tier code (see mapping below) |
| `ETF` | `'Y'` = ETF, `'N'` = non-ETF |
| `Financial Status` | Status code (see mapping below) |
| `Company Description` | Full company name — use this for final answers |
| `Nasdaq Traded` | Whether listed on NASDAQ |

**Always double-quote column names with spaces in SQLite SQL:**
```sql
SELECT Symbol, "Company Description", "Listing Exchange", "Market Category"
FROM stockinfo
WHERE ETF = 'Y' AND "Listing Exchange" = 'P'
```

---

## DuckDB Per-Ticker Table Column Names

Each ticker table has these columns (use double-quotes):
- `"Date"` (text/varchar)
- `"Open"`, `"High"`, `"Low"`, `"Close"`, `"Adj Close"` (double)
- `"Volume"` (bigint)

```sql
SELECT "Date", "Adj Close" FROM "AAPL" WHERE "Date" >= '2020-01-01'
```

---

## Listing Exchange Codes

| Code | Exchange |
|---|---|
| `A` | NYSE MKT (American Stock Exchange) |
| `N` | New York Stock Exchange |
| `P` | NYSE Arca |
| `Q` | NASDAQ |
| `Z` | BATS Global Markets |
| `V` | IEXG |

---

## Market Category Codes (NASDAQ only)

| Code | Tier |
|---|---|
| `Q` | NASDAQ Global Select Market |
| `G` | NASDAQ Global Market |
| `S` | NASDAQ Capital Market |
| (empty/`Not applicable`) | Non-NASDAQ listed |

---

## Financial Status Codes

| Code | Meaning |
|---|---|
| `N` | Normal — not deficient or delinquent |
| `D` | Deficient |
| `E` | Delinquent |
| `Q` | Bankrupt |
| `H` | Deficient and delinquent |
| `G` | Deficient and bankrupt |
| `K` | Deficient, delinquent, and bankrupt |

"Financially troubled" = `Financial Status` IN (`'D'`, `'E'`, `'Q'`, `'H'`, `'G'`, `'K'`) — anything other than `'N'` (normal).

---

## CRITICAL: Always Return Company Names, Not Ticker Symbols

For any question asking for company names (not "symbols" or "tickers"), ALWAYS:
1. Get the ticker from DuckDB computations
2. Join back to SQLite to retrieve `"Company Description"` as the company name
3. Return the `"Company Description"` value, not the ticker symbol

```python
# After computing top tickers in DuckDB:
tickers_str = ",".join(f"'{t}'" for t in top_tickers)
names = query_sqlite("stockinfo_database",
    f'SELECT Symbol, "Company Description" FROM stockinfo WHERE Symbol IN ({tickers_str})')
# Use names["data"][i]["Company Description"] in the final answer
```

---

## Consecutive Down Days (Window Function Pattern)

For "most consecutive down days" queries:
```sql
WITH daily AS (
    SELECT "Date",
        "Close",
        LAG("Close") OVER (ORDER BY "Date") AS prev_close
    FROM "TICKER"
    WHERE "Date" >= '2022-01-01' AND "Date" <= '2022-12-31'
),
flags AS (
    SELECT "Date",
        CASE WHEN "Close" < prev_close THEN 1 ELSE 0 END AS is_down
    FROM daily WHERE prev_close IS NOT NULL
),
groups AS (
    SELECT "Date", is_down,
        ROW_NUMBER() OVER (ORDER BY "Date") -
        ROW_NUMBER() OVER (PARTITION BY is_down ORDER BY "Date") AS grp
    FROM flags
)
SELECT MAX(cnt) AS max_consecutive_down FROM (
    SELECT COUNT(*) AS cnt FROM groups WHERE is_down = 1 GROUP BY grp
)
```

Apply this per ticker, then find the maximum across the eligible set.

---

## Scale Warning

2,753 tickers × potentially years of daily data = millions of rows.
**Always filter by ticker early** — never do full table scans across all ticker tables.
Process tickers in batches if the eligible set is large (>50 tickers).

---

## Common Pitfalls

- Querying `stock_trade` table (does not exist). → **Entry 055**
- Using `ticker` or `exchange` column names (actual names: `Symbol`, `Listing Exchange`). → **Entry 055**
- Returning ticker symbols instead of company names when question asks for names. → **Entry 056**
- Missing double-quotes on column names with spaces in SQLite. → **Entry 055**
- Joining info/trade tables after aggregation and losing required group keys. → **Entry 017**
- Returning different top stocks on each run due to missing tie-breaker. → **Entry 036**
- `Financial Status` NULL values (most rows) treated as non-normal status.

---

## Validation Checklist

- DuckDB table names: confirmed ticker tables exist with `SHOW TABLES` before querying.
- Column names: double-quoted in SQL where spaces exist.
- Company names: final answer uses `Company Description`, not ticker symbols.
- Exchange filter: using correct single-letter code (`P` for NYSE Arca, not `NYSE Arca`).
- Financial status filter: using correct codes, not NULL as "normal".
- Results completeness: for list queries, count returned items vs expected cardinality.

---

## Leakage-Safe Policy

- No pre-filled winners, expected tickers, or fixed benchmark outputs.
- Exchange codes, column names, and financial status codes above are factual schema knowledge.
- Keep only robust financial-data query strategy and verification guidance.
