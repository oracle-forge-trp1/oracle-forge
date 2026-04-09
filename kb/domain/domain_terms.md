# Domain Term Definitions

## Purpose
Terms used in DAB queries that have non-obvious or dataset-specific definitions. The agent MUST use these definitions — not naive interpretations — to answer correctly.

---

## CRM / Business Terms (crmarenapro)

### Lead
- **Definition:** A potential customer who has expressed interest but not yet converted
- **Key fields:** Status (Open, Qualified, Converted, Closed), LeadSource

### Opportunity
- **Definition:** A qualified sales deal in the pipeline with an estimated close date and amount
- **Stages:** Prospecting → Qualification → Proposal → Negotiation → Closed Won / Closed Lost
- **Not:** A lead — opportunities are further down the funnel

### Case
- **Definition:** A customer support ticket/issue in the support database
- **Status values:** New, Working, Escalated, Closed

### Account vs Contact
- **Account:** A company/organization in the CRM
- **Contact:** An individual person associated with an Account

### Territory
- **Definition:** A geographic or logical sales region assigned to specific users

---

## Finance / Stock Terms (stockindex, stockmarket)

### OHLC
- **Definition:** Open, High, Low, Close — standard daily price data points
- **Adjusted Close:** Close price adjusted for splits and dividends — use this for historical comparisons

### Market Category
- **Values in stockmarket:** Categories like "Large Cap", "Mid Cap", "Small Cap", ETF classifications
- **Trading Status:** Whether a security is actively traded

### Index
- **In stockindex:** A composite indicator of a stock exchange's performance (e.g., S&P 500, FTSE 100)
- **Not:** An individual stock

---

## Biomedical Terms (pancancer_atlas)

### ParticipantBarcode
- **Format:** TCGA barcode (e.g., `TCGA-XX-XXXX`) uniquely identifying a patient
- **Note:** Sample-level barcodes extend this with additional segments — truncate to patient level for clinical joins

### Hugo_Symbol
- **Definition:** The official gene name from HUGO Gene Nomenclature Committee (e.g., TP53, BRCA1)

### Variant_Classification
- **Location:** `Mutation_Data` table in molecular_database (DuckDB)
- **Values:** Missense_Mutation, Nonsense_Mutation, Frame_Shift_Del, Frame_Shift_Ins, Silent, Splice_Site, etc.
- **Missense_Mutation:** A point mutation that changes the amino acid
- **Note:** Filtering for "damaging" mutations typically excludes Silent variants

### Cancer Type Acronyms
- Common TCGA abbreviations: BRCA (breast), LUAD (lung adenocarcinoma), GBM (glioblastoma), COAD (colon), PRAD (prostate)

### Normalized Count (RNASeq)
- **Definition:** Gene expression level after normalization for sequencing depth
- **Usage:** Higher count = higher expression. Compare across samples for differential expression.

---

## Patent / IP Terms (patents)

### CPC Code
- **Definition:** Cooperative Patent Classification — hierarchical system for categorizing patents
- **Structure:** Section (H) → Class (H04) → Subclass (H04L) → Group (H04L67/10)
- **Note:** Queries may ask for patents in a category — requires matching at the right hierarchy level

### Patent Citation
- **Forward citation:** Later patents citing this one (indicates influence)
- **Backward citation:** Patents this one cites (indicates prior art)

---

## Software / Dev Terms (deps_dev_v1, github_repos)

### Package Ecosystem
- **Values:** NPM (JavaScript), Maven (Java), PyPI (Python), Go, Cargo (Rust), etc.
- **Note:** Same package name can exist in different ecosystems — ecosystem is part of the identity

### Security Advisory
- **Definition:** Known vulnerability (CVE) associated with a package version
- **Query pattern:** "packages with known vulnerabilities" = packages with security advisories

### Repository License
- **Common values:** mit, apache-2.0, gpl-3.0, bsd-2-clause, unlicense
- **Note:** In github_repos licenses table, stored as SPDX identifiers

---

## Review / Rating Terms (bookreview, googlelocal, yelp)

### Rating / Stars
- **Scale:** Typically 1-5 (both Yelp and Google/Amazon)
- **Average Stars:** Mean of all ratings for an entity

### Helpfulness (bookreview)
- **Definition:** How many users found a review helpful
- **Verified Purchase:** Whether the reviewer actually bought the item — important for credibility filtering

### Review Count vs Rating
- **review_count:** Total number of reviews (volume)
- **stars/rating:** Quality score (average)
- **Note:** These are independent — high review count does not mean high rating

---

## Music Terms (music_brainz_20k)

### Source ID / Source Track ID
- **Definition:** Tracks can come from multiple sources (MusicBrainz, external catalogs)
- **track_id:** Internal unique ID
- **source_track_id:** ID from the originating catalog — not unique across sources

---

## News Terms (agnews)

### Region (article_metadata)
- **Definition:** Geographic region of publication
- **Note:** May be used to filter articles by geography

---

## Cross-Dataset Temporal Terms

### Date Handling
- Dates are stored differently per DB type — always parse to a common format before comparison
- "Last N days/months" in queries means relative to the latest date in the dataset, NOT today's date
- Fiscal year: assume calendar year (Jan-Dec) unless dataset metadata says otherwise

### "Through 2023"
- bookreview, googlelocal data goes through 2023 — do not expect 2024+ data
- "Recent" in queries for these datasets means late 2023, not current date
