# DAB Dataset Schemas

## Overview
DataAgentBench contains 12 datasets across 9 domains, 54 queries total. Each dataset uses 2+ database types requiring cross-database joins. No MongoDB in any dataset — only PostgreSQL, SQLite, DuckDB, and MongoDB (agnews + yelp only use Mongo).

---

## 1. agnews (4 queries)
**Domain:** News/Media
**DB Types:** MongoDB + SQLite

### articles_database (MongoDB)
- Collection: `articles` — article_id, title, description (free text)

### metadata_database (SQLite)
- Table: `authors` — author details
- Table: `article_metadata` — article_id (FK), author linkage, region, publication_date

### Cross-DB Key
- `article_id` links MongoDB articles to SQLite metadata

---

## 2. bookreview (3 queries)
**Domain:** Literature/Books
**DB Types:** PostgreSQL + SQLite

### books_database (PostgreSQL)
- Table: `books_info` — bibliographic details, pricing, features, descriptions, categories, unique identifiers (Amazon book data through 2023)

### review_database (SQLite)
- Table: `review` — ratings, review text (free text), helpfulness metrics, verified purchase status, timestamps

### Cross-DB Key
- `book_id` (PostgreSQL) links to `purchase_id` (SQLite) — **name mismatch, same entity**

---

## 3. crmarenapro (13 queries — largest dataset)
**Domain:** CRM/Business (Salesforce-style)
**DB Types:** SQLite + DuckDB + PostgreSQL (6 databases)

### core_crm (SQLite)
- Tables: `User`, `Account`, `Contact` — core CRM customer relationship data

### sales_pipeline (DuckDB)
- Tables: `Contract`, `Lead`, `Opportunity`, `OpportunityLineItem`, `Quote`, `QuoteLineItem` — sales deals and quotes

### support (PostgreSQL)
- Tables: `Case`, `knowledge__kav`, `issue__c`, `casehistory__c`, `emailmessage`, `livechattranscript` — customer support operations

### products_orders (SQLite)
- Tables: `ProductCategory`, `Product2`, `ProductCategoryProduct`, `Pricebook2`, `PricebookEntry`, `Order`, `OrderItem` — inventory and orders

### activities (DuckDB)
- Tables: `Event`, `Task`, `VoiceCallTranscript__c` — calendar activities and communications

### territory (SQLite)
- Tables: `Territory2`, `UserTerritory2Association` — sales territory assignments

### Known Data Quality Issues
- ~25% of ID fields have leading `#` prefix (e.g., `#001Wt00000PFj4zIAD`) — **must strip before joins**
- ~20% of text fields have trailing whitespace — **must trim before comparisons**
- Affected fields: Id, AccountId, ContactId, Name, FirstName, LastName, Email, Subject, Status

---

## 4. deps_dev_v1 (2 queries)
**Domain:** Software Dependencies
**DB Types:** SQLite + DuckDB

### package_database (SQLite)
- Table: `packages` — package metadata: licensing, versions, dependencies, security advisories, release info across ecosystems (NPM, Maven, etc.)

### project_database (DuckDB)
- Table: `package_to_project` — maps packages to GitHub projects
- Table: `projects` — project descriptions, licenses, homepage URLs

### Cross-DB Key
- Package name/identifier links packages to projects

---

## 5. github_repos (4 queries)
**Domain:** Software Development
**DB Types:** SQLite + DuckDB

### metadata_database (SQLite)
- Table: `languages` — repo name → programming languages used (natural language format)
- Table: `licenses` — repo name → license identifier (apache-2.0, mit, etc.)
- Table: `repos` — watch_count metrics

### artifacts_database (DuckDB)
- Table: `contents` — file-level data: file content (text), paths, references
- Table: `commits` — commit history: author/committer, messages, file change diffs
- Table: `files` — file metadata: paths, modes, blob IDs

### Cross-DB Key
- Repository name in `owner/repo` format across both databases

---

## 6. googlelocal (4 queries)
**Domain:** Location/Maps
**DB Types:** PostgreSQL + SQLite

### business_database (PostgreSQL)
- Table: `business_description` — business name, description, hours, operational status, review counts

### review_database (SQLite)
- Table: `review` — reviewer name, ratings, review text (free text), gmap_id

### Cross-DB Key
- `gmap_id` links reviews to businesses

---

## 7. music_brainz_20k (3 queries)
**Domain:** Music
**DB Types:** SQLite + DuckDB

### tracks_database (SQLite)
- Table: `tracks` — track_id, source_id, source_track_id, title, artist, album, year, length, language

### sales_database (DuckDB)
- Table: `sales` — sale_id, track_id, country, store, units_sold, revenue_usd

### Cross-DB Key
- `track_id` links tracks to sales records

---

## 8. pancancer_atlas (3 queries)
**Domain:** Biomedical/Cancer Research
**DB Types:** PostgreSQL + DuckDB

### clinical_database (PostgreSQL)
- Table: `clinical_info` — patient identifiers, cancer type acronyms, demographics, diagnosis, treatment outcomes, survival status (100+ columns)

### molecular_database (DuckDB)
- Table: `Mutation_Data` — ParticipantBarcode, Hugo_Symbol, Variant_Classification (e.g., Missense_Mutation), sample IDs, sequencing center
- Table: `RNASeq_Expression` — normalized_count, gene symbols, sample type codes, ParticipantBarcode

### Cross-DB Key
- `ParticipantBarcode` links clinical data to molecular profiles

---

## 9. patents (3 queries)
**Domain:** Intellectual Property
**DB Types:** SQLite + PostgreSQL

### publication_database (SQLite)
- Table: `publicationinfo` — patent publication records: identifiers, dates, CPC classifications, inventor info, citation relationships, technical descriptions

### cpc_definition_database (PostgreSQL)
- Table: `cpc_definition` — hierarchical CPC classification structure: parent-child relationships, definitions, metadata

### Cross-DB Key
- CPC code in publications references definitions in CPC database — **hierarchical lookup required**

---

## 10. stockindex (3 queries)
**Domain:** Finance/Stock Indices
**DB Types:** SQLite + DuckDB

### indexinfo_database (SQLite)
- Table: `index_info` — stock exchange full names, trading currencies

### indextrade_database (DuckDB)
- Table: `index_trade` — index symbol, date, open, high, low, close, adjusted close, USD-converted close

### Cross-DB Key
- Index symbol/name links metadata to trading data

---

## 11. stockmarket (5 queries)
**Domain:** Finance/Individual Stocks
**DB Types:** SQLite + DuckDB
**Scale:** 2,754 securities (large)

### stockinfo_database (SQLite)
- Table: `stock_info` — ticker symbols, market categories, trading venues, company descriptions, trading status, financial health, security classifications

### stocktrade_database (DuckDB)
- Table: `stock_trade` — daily OHLC prices, adjusted close, volume per ticker per date (2,753 securities)

### Cross-DB Key
- Ticker symbol links stock info to trading data

---

## 12. yelp (7 queries — most queries)
**Domain:** Business Reviews
**DB Types:** MongoDB + DuckDB

### businessinfo_database (MongoDB)
- Collection: `business` — name, review_count, status, attributes (parking, WiFi, etc.), description with location info
- Collection: `checkin` — timestamped check-in logs per business

### user_database (DuckDB)
- Table: `review` — user reviews with ratings, votes, review text (free text), compliment_count
- Table: `tip` — brief user suggestions with compliment_count
- Table: `user` — user profiles with activity stats, registration date

### Cross-DB Key
- `business_id` (MongoDB) maps to `business_ref` (DuckDB) — **prefix mismatch**: `businessid_X` vs `businessref_X`
- `user_id` consistent across DuckDB tables

---

## DB Type Distribution Summary

| DB Type | Datasets Using It |
|---|---|
| SQLite | agnews, bookreview, crmarenapro, deps_dev_v1, github_repos, googlelocal, music_brainz_20k, patents, stockindex, stockmarket |
| DuckDB | crmarenapro, deps_dev_v1, github_repos, music_brainz_20k, pancancer_atlas, stockindex, stockmarket, yelp |
| PostgreSQL | bookreview, crmarenapro, googlelocal, pancancer_atlas, patents |
| MongoDB | agnews, yelp |
