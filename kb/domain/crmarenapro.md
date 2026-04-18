# CRM Arena Pro Domain Knowledge

## Dataset Overview

This dataset spans 6 databases and 27 tables.

This is the **largest DAB dataset** (13 queries). Salesforce-style CRM data spread across 3 DB types.

| Database | Type | Logical Name | Tables |
|----------|------|--------------|--------|
| core_crm.db | SQLite | core_crm | User, Account, Contact |
| sales_pipeline.duckdb | DuckDB | sales_pipeline | Contract, Lead, Opportunity, OpportunityLineItem, Quote, QuoteLineItem |
| support.sql | PostgreSQL | support | Case, knowledge__kav, issue__c, casehistory__c, emailmessage, livechattranscript |
| products_orders.db | SQLite | products_orders | ProductCategory, Product2, ProductCategoryProduct, Pricebook2, PricebookEntry, Order, OrderItem |
| activities.duckdb | DuckDB | activities | Event, Task, VoiceCallTranscript__c |
| territory.db | SQLite | territory | Territory2, UserTerritory2Association |

---

## CRITICAL: Data Corruption (~25% of records)

### ID Field Corruption — Leading `#`
~25% of ID fields have a leading `#` character:
```
Clean:     001Wt00000PFj4zIAD
Corrupted: #001Wt00000PFj4zIAD
```

**Must strip `#` before ANY join or comparison:**
```python
clean_id = raw_id.strip().lstrip('#')
```

**Affected fields:** Id, AccountId, ContactId, OwnerId — across ALL 6 databases.

### Text Field Corruption — Trailing Whitespace
~20% of text fields have trailing spaces:
```
Clean:     "Company Name"
Corrupted: "Company Name   "
```

**Must `.strip()` all string fields before comparison.**

**Affected fields:** Name, FirstName, LastName, Email, Subject, Status.

---

## Schema Reference

The dataset overview table defines database-to-table coverage across all six stores.
Use that table as the primary schema anchor, then introspect live columns at runtime before writing final joins.

---

## Cross-Database Join Keys

All 6 databases use Salesforce-style IDs (18-char alphanumeric). The same ID format is used across databases, but corruption (`#` prefix, whitespace) breaks direct equality.

Common join paths:
```
User.Id → Lead.OwnerId / Opportunity.OwnerId / Case.ownerid
Account.Id → Contact.AccountId / Opportunity.AccountId / Order.AccountId / Case.accountid
Contact.Id → Opportunity.ContactId / Quote.ContactId
Product2.Id → OrderItem.Product2Id / OpportunityLineItem.Product2Id / PricebookEntry.Product2Id
```

**Always normalize IDs before joining:**
```python
def clean_crm_id(val):
    return str(val).strip().lstrip('#')
```

---

## Data Semantics

| Term | Definition |
|---|---|
| **Lead** | Potential customer, not yet converted. Status: Open, Qualified, Converted, Closed. |
| **Opportunity** | Qualified sales deal in pipeline. Stages: Prospecting → Qualification → Proposal → Negotiation → Closed Won / Closed Lost. |
| **Case** | Customer support ticket. Status: New, Working, Escalated, Closed. |
| **Account** | Company/organization in CRM. |
| **Contact** | Individual person linked to an Account. |
| **Territory** | Geographic/logical sales region assigned to Users. |
| **Contract** | Signed agreement with a customer Account. |
| **PricebookEntry** | Links a Product to a Pricebook with a specific UnitPrice. |

---

## Query Strategy Playbook

### Multi-DB routing (most queries span 3+ databases)
```python
# Example: "Total revenue for accounts in territory X"
# Step 1: SQLite (territory) — get UserIds in territory
# Step 2: SQLite (core_crm) — get Accounts owned by those Users
# Step 3: SQLite (products_orders) — get Orders for those Accounts
# Step 4: Join and aggregate in application layer
```

### PostgreSQL support queries
```sql
-- Case resolution time
SELECT id, subject,
  (closeddate::timestamp - createddate::timestamp) AS resolution_time
FROM "Case"
WHERE status = 'Closed'
```

Note: PostgreSQL table/column names in support DB use lowercase. Use double quotes if needed.

### DuckDB sales pipeline queries
```sql
-- Opportunity win rate
SELECT OwnerId,
  COUNT(*) FILTER (WHERE StageName = 'Closed Won') AS won,
  COUNT(*) AS total,
  ROUND(COUNT(*) FILTER (WHERE StageName = 'Closed Won') * 100.0 / COUNT(*), 2) AS win_rate
FROM Opportunity
GROUP BY OwnerId
```

### Output contract for validator-facing CRM queries
- Month questions: return month name token only (for example `November`), no explanation.
- Agent/product/knowledge questions: return canonical IDs exactly as stored (`005...`, `01t...`, `ka0...` etc.) when IDs are requested.
- Do not answer with policy narrative (`no violation`) when the prompt asks for an identifier from matched records.

---

## Common Pitfalls

- Joining IDs without first removing leading `#` and surrounding whitespace.
- Mixing cleaned and uncleaned IDs across intermediate query steps.
- Assuming support-table casing is uniform; PostgreSQL identifiers may need quoting.
- Treating `permission denied` as a reasoning issue and retrying indefinitely (it is a server role/GRANT issue).
- Counting opportunities/orders after many-to-many joins without deduplication keys.
- Computing SLA/resolution metrics from raw text timestamps without normalization.

---

## Support DB permissions failure mode (PostgreSQL)
If queries against the `support` logical DB return `permission denied for table ...`:
- This is an **environment configuration** problem (missing SELECT grants) and cannot be solved by better SQL alone.
- Do not loop on the same failing query; pivot to other databases only if the question can be answered without `support`.
- Otherwise, return a concise “cannot complete due to database permissions” response rather than fabricating values.

For prompts that explicitly require CRM IDs (agent/product/knowledge/issue):
- Do not return `None` when an ID can be selected from accessible filtered candidates.
- Apply full filters first, then pick deterministic winner (`ORDER BY metric DESC, Id ASC`) before final output.

---

## Validation Checklist

- ID hygiene: percentage of keys changed by normalization (`lstrip('#').strip()`).
- Join diagnostics: matched vs unmatched counts for each cross-DB join edge.
- Cardinality guard: compare distinct business entities before/after joins.
- Timestamp sanity: null/parse-failure rates for created/closed fields.
- Metric consistency: verify at least one sampled owner/account trace end-to-end across DBs.
- ID answer check: for ID-target questions, confirm final output token exists in final filtered candidate rows (not in pre-filter supersets).
- Month/ID output shape: when prompt requests month or single ID, output only that token (no narrative prefix/suffix).

---

## Leakage-Safe Policy

- Keep only reusable CRM data-handling guidance (normalization, joins, QA checks).
- Do not include query-specific expected outputs, top-entity lists, or benchmark target values.
- Any historical lessons must remain generic and process-oriented.
