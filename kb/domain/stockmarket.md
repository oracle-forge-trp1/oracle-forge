# Stock Market Domain Knowledge

## Dataset Overview

| Database | Type | Logical Name | Table | Key Fields |
|----------|------|--------------|-------|------------|
| stockinfo_query.db | SQLite | stockinfo_database | stock_info | ticker, market_category, trading_status, description, financial_status, exchange |
| stocktrade_query.db | DuckDB | stocktrade_database | stock_trade | ticker, date, open, high, low, close, adj_close, volume |

**Scale:** 2,754 securities with daily price data — potentially millions of rows.

---

## Cross-DB Join Key

- SQLite `stock_info.ticker` → DuckDB `stock_trade.ticker`
- Format is consistent — direct string match. **No prefix mismatch.**

---

## Stock Info — Code Definitions

### Listing Exchanges
| Code | Exchange |
|---|---|
| A | NYSE MKT |
| N | New York Stock Exchange |
| P | NYSE ARCA |
| Z | BATS Global Markets |
| V | IEXG |
| Q | NASDAQ |

### Financial Status Codes
| Code | Meaning |
|---|---|
| N | Normal — not deficient or delinquent |
| D | Deficient |
| E | Delinquent |
| Q | Bankrupt |
| H | Deficient and delinquent |
| G | Deficient and bankrupt |
| K | Deficient, delinquent, and bankrupt |

A company is "financially troubled" if deficient, delinquent, or both.

### Market Categories (NASDAQ)
| Code | Tier |
|---|---|
| Q | NASDAQ Global Select Market |
| G | NASDAQ Global Market |
| S | NASDAQ Capital Market |

---

## Large Table Warning

`stock_trade` has daily data for 2,754 tickers — **always filter early:**

```sql
-- GOOD: filter by ticker first
SELECT * FROM stock_trade WHERE ticker = 'AAPL' AND date >= '2023-01-01'

-- BAD: full table scan
SELECT * FROM stock_trade ORDER BY date
```

---

## Key Query Patterns

### Price analysis
```sql
-- DuckDB: Average closing price per ticker for a date range
SELECT ticker, AVG(close) as avg_close
FROM stock_trade
WHERE date BETWEEN '2023-01-01' AND '2023-12-31'
GROUP BY ticker
ORDER BY avg_close DESC
LIMIT 10
```

### Cross-DB: Company info + price data
```python
# Step 1: Filter companies in SQLite
companies = query_sqlite("stockinfo_database",
    "SELECT ticker, description FROM stock_info WHERE market_category = 'Q'")

# Step 2: Get price data from DuckDB
tickers = [c["ticker"] for c in companies]
placeholders = ",".join(f"'{t}'" for t in tickers)
prices = query_duckdb("stocktrade_database",
    f"SELECT ticker, AVG(close) FROM stock_trade WHERE ticker IN ({placeholders}) GROUP BY ticker")
```

### Volatility
```sql
-- DuckDB: Average intraday volatility
SELECT ticker, AVG((high - low) / NULLIF(open, 0)) AS avg_volatility
FROM stock_trade
WHERE date >= '2023-01-01'
GROUP BY ticker
ORDER BY avg_volatility DESC
```

---

## Description Field

`stock_info.description` contains brief company descriptions. Use for text-based queries:
```sql
-- SQLite
SELECT ticker, description FROM stock_info
WHERE description LIKE '%technology%'
```
