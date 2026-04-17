# AG News Domain Knowledge

## Dataset Overview

| Database | Type | Logical Name | Collection/Table | Key Fields |
|----------|------|--------------|-----------------|------------|
| agnews_articles (BSON dump) | MongoDB | articles_database | articles | article_id, title, description |
| metadata.db | SQLite | metadata_database | authors, article_metadata | author details, article_id, region, publication_date |

---


## Cross-Database Join Keys
=======


- MongoDB `articles.article_id` → SQLite `article_metadata.article_id`
- Format is consistent across both databases — direct string equality works.

---


## Data Semantics


Articles fall into exactly **4 categories:**

| Category | Topic |
|---|---|
| World | International news and politics |
| Sports | Sports news and events |
| Business | Business and financial news |
| Science/Technology | Science and technology news |

Categories must be determined from the article `title` and `description` content. There may or may not be an explicit category field — classification may require text analysis.

---

## Schema Reference

- **Article content:** MongoDB `articles` collection — `title` and `description` fields
- **Publication metadata:** SQLite `article_metadata` — region, date, author linkage
- **Author info:** SQLite `authors` table

---

## Query Strategy Playbook

### Count articles by category
```python
# Step 1: Fetch all articles from MongoDB
articles = query_mongodb("articles_database", "articles", "find", "{}", '{"article_id": 1, "title": 1, "description": 1}')

# Step 2: Classify each article (by keyword matching or LLM classification)
# Step 3: Count per category
```

### Filter by region or date
Region and date are in SQLite `article_metadata`, not in MongoDB:
```python
# Step 1: Query SQLite for article_ids in target region
metadata = query_sqlite("metadata_database",
    "SELECT article_id FROM article_metadata WHERE region = 'US'")

# Step 2: Fetch matching articles from MongoDB
article_ids = [m["article_id"] for m in metadata]
articles = query_mongodb("articles_database", "articles", "find",
    json.dumps({"article_id": {"$in": article_ids}}))
```

### Cross-DB aggregation
```python
# "How many Science/Technology articles were published in region X?"
# Step 1: Get articles from MongoDB
# Step 2: Classify by category
# Step 3: Get metadata from SQLite (region, date)
# Step 4: Filter and count
```

---

## Common Pitfalls

- Assuming category is a single normalized column when it may require text-based classification.
- Joining Mongo and SQLite before deduplicating `article_id`, causing over-counting.
- Applying region/date filters to Mongo documents instead of SQLite metadata.
- Ignoring null or empty `title`/`description` during classification.
- Mixing publication date formats without explicit normalization.

---

## Validation Checklist

- Join integrity: `%` of Mongo articles with matching SQLite metadata.
- De-duplication: distinct `article_id` count before and after joins.
- Classification coverage: share of rows assigned one of the 4 categories.
- Temporal sanity: min/max normalized publication dates are plausible.
- Spot-checks: manually inspect a sample of classified rows for label drift.

---

## Leakage-Safe Policy

- Never store expected per-query counts, labels, or final benchmark outputs.
- Keep only reusable category-classification and cross-source-join methodology.
- If adding examples, keep them procedural and dataset-structural, not answer-bearing.
