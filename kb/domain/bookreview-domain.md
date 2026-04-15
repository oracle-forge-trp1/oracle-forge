# Book Review Dataset — Domain Knowledge

This document is injected into the agent's Domain Knowledge context layer before any Book Review query is answered. All facts here are specific to this dataset — do not assume they apply to other DAB datasets.

## Dataset Structure

Two active databases. Every Book Review query spans both — book metadata lives in PostgreSQL, review data lives in SQLite.

| Database | What it contains |
|----------|-----------------|
| PostgreSQL `books_database` | Book metadata (title, author, price, categories, etc.) |
| SQLite `review_database` | User reviews, ratings, helpfulness votes |

## Schema Reference

### PostgreSQL — `books_database`

#### `books_info` table
| Field | Type | Notes |
|-------|------|-------|
| `title` | str | Book title |
| `subtitle` | str | Book subtitle |
| `author` | str | Book author(s) |
| `rating_number` | int | Total number of ratings received |
| `features` | str | Stored as string representation of list/dict |
| `description` | str | Stored as string representation of list/dict |
| `price` | float | Book price |
| `store` | str | Store information |
| `categories` | str | Stored as string representation of list/dict |
| `details` | str | Additional book details |
| `book_id` | str | Unique book identifier — links to `review.purchase_id` |

### SQLite — `review_database`

#### `review` table
| Field | Type | Notes |
|-------|------|-------|
| `rating` | float | Rating 1.0–5.0 |
| `title` | str | Review title |
| `text` | str | Review text content |
| `purchase_id` | str | Links to `books_info.book_id` — fuzzy join required |
| `review_time` | str | Timestamp when review was posted |
| `helpful_vote` | int | Number of helpful votes |
| `verified_purchase` | bool | Whether purchase was verified |

## Join Key — Critical Rule

`books_info.book_id` and `review.purchase_id` refer to the same book but **field names differ and values may not match exactly**. Use a fuzzy join approach — do not assume direct string equality works.

## String-Serialised Fields — Always Parse

These PostgreSQL fields look structured but are stored as plain strings:

| Field | Stored as |
|-------|-----------|
| `description` | String representation of a list or dict |
| `categories` | String representation of a list or dict |
| `features` | String representation of a list or dict |

Use `ast.literal_eval()` to parse, or regex/substring matching on the raw string. Do not query them as structured objects.

## Additional Notes

- Category and genre information may be in either `categories` or `details` — check both when answering category-related queries.
- Data covers Amazon books up to 2023.
