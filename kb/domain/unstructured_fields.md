# Unstructured Text Fields Inventory

## Purpose
Some DAB queries require extracting structured facts from free-text fields before computing an answer. This document inventories all known text fields requiring transformation across all 12 datasets.

---

## agnews
### `articles.description` (MongoDB)
- **Content:** News article description/body text
- **Extraction tasks:** Topic classification, entity extraction, keyword search
- **Approach:** LLM classification or regex for specific entity mentions

### `articles.title` (MongoDB)
- **Content:** Article headlines
- **Extraction tasks:** Topic matching, entity extraction from headlines

---

## bookreview
### `books_info.descriptions` (PostgreSQL)
- **Content:** Book descriptions and summaries
- **Extraction tasks:** Genre classification, theme extraction, content matching

### `books_info.features` (PostgreSQL)
- **Content:** Book features/attributes as text
- **Extraction tasks:** Feature parsing, attribute extraction

### `review.text` (SQLite)
- **Content:** Full book review text from Amazon customers
- **Extraction tasks:** Sentiment analysis, topic extraction, opinion mining
- **Approach:** ILIKE for simple patterns; LLM for semantic classification

---

## crmarenapro
### `emailmessage` fields (PostgreSQL - support)
- **Content:** Customer email content
- **Extraction tasks:** Issue classification, sentiment, urgency detection

### `livechattranscript` fields (PostgreSQL - support)
- **Content:** Live chat conversation logs
- **Extraction tasks:** Topic extraction, resolution identification

### `VoiceCallTranscript__c` fields (DuckDB - activities)
- **Content:** Voice call transcription text
- **Extraction tasks:** Call topic classification, action item extraction

### `knowledge__kav` fields (PostgreSQL - support)
- **Content:** Knowledge base articles
- **Extraction tasks:** Solution matching, content search

---

## deps_dev_v1
### `packages.description` (SQLite)
- **Content:** Package descriptions from NPM/Maven registries
- **Extraction tasks:** Purpose classification, technology identification

### `projects.description` (DuckDB)
- **Content:** GitHub project descriptions
- **Extraction tasks:** Project purpose matching

---

## github_repos
### `contents.content` (DuckDB)
- **Content:** Actual file content (source code, docs, configs)
- **Extraction tasks:** Code pattern matching, dependency identification, documentation search
- **Note:** Large text field — may need targeted queries with file path filters

### `commits.message` (DuckDB)
- **Content:** Git commit messages
- **Extraction tasks:** Change type classification, bug fix identification

### `commits.difference` (DuckDB)
- **Content:** File change diffs per commit
- **Extraction tasks:** Code change analysis

---

## googlelocal
### `business_description.description` (PostgreSQL)
- **Content:** Business descriptions from Google Maps
- **Extraction tasks:** Service type identification, feature extraction

### `review.text` (SQLite)
- **Content:** Google Maps user reviews
- **Extraction tasks:** Sentiment analysis, aspect extraction (food, service, ambiance)

---

## music_brainz_20k
- **No significant free-text fields.** Data is structured (track metadata + sales figures).

---

## pancancer_atlas
### `clinical_info` multiple text columns (PostgreSQL)
- **Content:** Clinical notes and coded fields across 100+ columns
- **Extraction tasks:** Treatment outcome extraction, diagnosis parsing
- **Note:** Many columns with coded values requiring domain knowledge to interpret

---

## patents
### `publicationinfo` description fields (SQLite)
- **Content:** Patent technical descriptions, abstracts, claims
- **Extraction tasks:** Technology classification, inventor identification, citation parsing
- **Note:** Highly technical language — may need domain-specific extraction

---

## stockindex / stockmarket
- **No significant free-text fields.** Data is structured numerical (prices, volumes).
- `stock_info.description` (SQLite) in stockmarket contains brief company descriptions but unlikely to be queried for extraction.

---

## Extraction Approach by Complexity

### Simple — SQL pattern matching
```sql
-- PostgreSQL
WHERE description ILIKE '%keyword%'
-- SQLite
WHERE description LIKE '%keyword%'
```
Use for: Known keyword presence, exact phrase matching.

### Medium — Python regex on pulled data
```python
import re
matches = [r for r in results if re.search(r'pattern', r['text'], re.IGNORECASE)]
```
Use for: Pattern extraction, structured data from semi-structured text.

### Complex — LLM classification on pulled data
```
Step 1: Pull text field values from database
Step 2: Send to LLM: "Classify each text as [category A/B/C]"
Step 3: Store classifications in structured format
Step 4: Use structured result in final aggregation
```
Use for: Sentiment analysis, semantic topic classification, multi-label categorization.

---

## Datasets Ranked by Unstructured Text Complexity

| Rank | Dataset | Complexity | Key Fields |
|---|---|---|---|
| 1 | github_repos | High | File contents, commit diffs, messages |
| 2 | crmarenapro | High | Emails, chat transcripts, voice calls, KB articles |
| 3 | patents | High | Technical descriptions, claims |
| 4 | bookreview | Medium | Reviews, book descriptions |
| 5 | googlelocal | Medium | Business descriptions, reviews |
| 6 | pancancer_atlas | Medium | Clinical notes (coded) |
| 7 | agnews | Medium | Article descriptions |
| 8 | deps_dev_v1 | Low | Package/project descriptions |
| 9 | stockmarket | Low | Company descriptions |
| 10-12 | music_brainz, stockindex, yelp | Minimal | Mostly structured data |
