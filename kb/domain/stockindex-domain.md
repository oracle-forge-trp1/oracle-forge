# Stock Index Dataset — Domain Knowledge

This document is injected into the agent's Domain Knowledge context layer before any Stock Index query is answered. All facts here are specific to this dataset — do not assume they apply to other DAB datasets.

## Dataset Structure

Two active databases. Every Stock Index query spans both — exchange metadata lives in SQLite, daily price data lives in DuckDB.

| Database | What it contains |
|----------|-----------------|
| SQLite `indexinfo_database` | Stock exchange metadata (name, currency) |
| DuckDB `indextrade_database` | Daily price data per index symbol |

## Schema Reference

### SQLite — `indexinfo_database`

#### `index_info` table
| Field | Type | Notes |
|-------|------|-------|
| `Exchange` | str | Full exchange name e.g. "Tokyo Stock Exchange" |
| `Currency` | str | Trading currency of the exchange |

### DuckDB — `indextrade_database`

#### `index_trade` table
| Field | Type | Notes |
|-------|------|-------|
| `Index` | str | Abbreviated symbol e.g. "N225", "HSI", "000001.SS" |
| `Date` | str | Trading date |
| `Open` | float | Opening price |
| `High` | float | Highest price of the day |
| `Low` | float | Lowest price of the day |
| `Close` | float | Closing price |
| `Adj Close` | float | Adjusted closing price |
| `CloseUSD` | float | Closing price in USD |

## Join Key — Critical Rule

`index_info.Exchange` uses **full names**. `index_trade.Index` uses **abbreviated symbols**. There is no shared key — you must map them using geographic/financial knowledge.

| Exchange (SQLite) | Index Symbol (DuckDB) |
|-------------------|-----------------------|
| Tokyo Stock Exchange | N225 |
| Hong Kong Stock Exchange | HSI |
| Shanghai Stock Exchange | 000001.SS |
| New York Stock Exchange | (varies) |

Do not attempt a direct string join — it will always return 0 rows.

## Region — Must Infer

No `region` field exists in either database. Infer region from exchange name or index symbol using geographic knowledge:

- **Asia**: N225 (Japan), HSI (Hong Kong), 000001.SS (China)
- **Europe**: exchanges in Germany, France, UK, etc.
- **North America**: exchanges in USA, Canada

## Key Metric Definitions

| Term | Formula |
|------|---------|
| Up day | `Close > Open` |
| Down day | `Close < Open` |
| Average intraday volatility | `AVG((High - Low) / Open)` over a period |
