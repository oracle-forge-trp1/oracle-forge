# AI-DLC Inception Document — Sprint 1
**Project:** Oracle Forge — Data Analytics Agent  
**Sprint:** 1 of 2 (Week 8, Days 3-5)  
**Focus:** Infrastructure + Core Agent Build  
**Date drafted:** 2026-04-09  
**Approval status:** PENDING — must be approved at mob session before Construction begins

---

## 1. Press Release

The Oracle Forge team has deployed a working natural language data analytics agent on our shared EC2 server, capable of answering real business questions against the Yelp dataset using MongoDB and DuckDB. The agent accepts a plain English question, routes it across two databases — MongoDB for business metadata and check-in records, DuckDB for reviews, tips, and user profiles — resolves the cross-database join key mismatch between `businessid_N` (MongoDB) and `businessref_N` (DuckDB) automatically, and returns a verified answer with a full query trace in under 60 seconds. It operates with three context layers: schema and metadata knowledge pre-loaded at session start, institutional knowledge injected from our LLM Knowledge Base, and a corrections log that captures every failure so the agent improves across sessions. The evaluation harness runs automatically after each agent change, producing a pass@1 score against a held-out set of Yelp queries so the team knows immediately whether any change made the agent better or worse. This is the foundation layer — two database types, one dataset, cross-DB joins working — built in five days by a team of five. It is not the finished product. It is the scaffold on which Sprint 2 will build.

---

## 2. Honest FAQ — User

**Q1: What can the agent actually answer at the end of Sprint 1?**  
It can answer natural language questions about the Yelp dataset that require querying MongoDB and DuckDB together. Every Yelp DAB query spans both databases — business location and attributes live in MongoDB, while reviews and user profiles live in DuckDB — so even a question like "What is the average rating of businesses in Indianapolis?" requires a cross-database join. The agent can handle these joins for the 7 Yelp queries in the benchmark. It cannot yet handle questions from other DAB datasets (retail, telecom, healthcare, finance) — those require loading additional databases and are a Sprint 2 goal.

**Q2: How accurate is it?**  
We do not know yet — that is what the evaluation harness will measure. Our target for Sprint 1 is a working baseline score on the 7 Yelp DAB queries, not a high score. Expect failures on queries that require parsing location from MongoDB's unstructured `description` text field (all 7 queries depend on this), queries that filter by date (three different date formats exist in the same DuckDB column), and queries that require parsing serialised `attributes` strings for WiFi or parking status. Every failure will be logged in the corrections log for Sprint 2.

**Q3: Can I ask it questions about other datasets or databases?**  
Not reliably in Sprint 1. The agent's context layers — schema knowledge, domain terms, join key formats — are built specifically around the Yelp dataset. Extending to other DAB datasets (retail, telecom, healthcare) is a Sprint 2 goal once the architecture is validated on Yelp.

---

## 3. Honest FAQ — Technical

**Q1: What is the hardest technical challenge in Sprint 1?**  
Getting the cross-database join to work reliably. MongoDB uses `business_id` formatted as `"businessid_N"` and DuckDB uses `business_ref` formatted as `"businessref_N"` — same integer N, different prefixes. A naively written join will return zero rows every time. Beyond that, business location is embedded in MongoDB's unstructured `description` field as natural language text ("Located at 6901 Phelps Rd in Goleta, CA...") with no structured address field — all 7 Yelp queries require extracting state or city from this text before the join can happen. Getting this pipeline (text extraction → key translation → cross-DB join) working reliably is the core Sprint 1 challenge.

**Q2: What is most likely to go wrong?**  
The cross-database join returning zero rows due to key format mismatch. The agent must translate `businessid_N` ↔ `businessref_N` on every query — if it attempts a direct string equality match between these two fields it will always return nothing with no error, just an empty result. A secondary risk is date filter failure: DuckDB date columns contain three different formats in the same column (`"August 01, 2016 at 03:44 AM"`, `"29 May 2013, 23:01"`, `"2013-12-04 02:46:01"`). Using `STRPTIME` with a single format will silently drop rows in the other formats. We will validate both on Day 1 with known-answer test queries before building the full agent.

**Q3: What are the key external dependencies?**  
Three: (1) Anthropic Claude API access — the agent calls Claude for NL-to-query generation; if API access is unavailable or rate-limited we cannot run the agent. (2) The Yelp data on the server — MongoDB (`yelp_db` at `localhost:27017`) and DuckDB (`/shared/oracle-forge/DataAgentBench/query_yelp/query_dataset/yelp_user.db`) are already loaded; if either becomes inaccessible or the DuckDB file path changes, the agent cannot run. (3) MCP Toolbox binary — we pin to version 0.30.0 and configure it against these exact paths; if the binary is incompatible or misconfigured our fallback is direct Python database drivers (`pymongo`, `duckdb`).

---

## 4. Key Decisions

**Decision 1 — LLM provider for agent**  
**Chosen:** Anthropic Claude via API (claude-sonnet-4-6 as default, claude-opus-4-6 for complex multi-step reasoning)  
**Rationale:** The team has confirmed API access, Claude's tool-use and structured output capabilities are well-suited to the query generation and self-correction loop, and the claude-code-source-code leak gives the team direct insight into how Claude handles multi-layer context — making it the most studied option available to us.

**Decision 2 — Agent framework**  
**Chosen:** DAB `common_scaffold` as base with custom extensions for context layers and self-correction  
**Rationale:** The scaffold provides the standard agent interface DAB's evaluation harness expects (`{question, available_databases, schema_info}` → `{answer, query_trace, confidence}`), so we do not spend Sprint 1 writing evaluation glue code; custom extensions handle the three context layers, the corrections log loop, and multi-database routing that the scaffold does not provide out of the box.

**Decision 3 — Starting dataset**  
**Chosen:** Yelp (MongoDB + DuckDB, already loaded on the server)  
**Rationale:** The practitioner manual explicitly recommends Yelp as the starting point; it is already loaded on our server (MongoDB `yelp_db` + DuckDB `yelp_user.db`), has 7 benchmark queries with known ground-truth answers, and covers all four DAB hard requirements (cross-DB joins, ill-formatted keys, unstructured text, domain knowledge) in a contained form — making it the right dataset to validate the full agent architecture before extending to other datasets in Sprint 2.

---

## 5. Definition of Done

Sprint 1 is complete when all of the following are verifiably true. "I think it works" is not evidence. Each item requires a specific observable output.

1. **MCP Toolbox is running and MongoDB + DuckDB connections verified:** `curl http://localhost:5000/v1/tools` returns tool definitions for both `mongo-dab` and `sqlite-dab` sources. Screenshot saved to `docs/toolbox-verified.png`.

2. **Yelp data is directly queryable and cross-DB join works:** A Python script manually executes: (a) MongoDB aggregation returning businesses in "Indianapolis" from description text, (b) DuckDB query returning average `rating` for the translated `business_ref` values, (c) combined result matching ground truth 3.547 ± 0.001. Script and output saved to `docs/yelp-join-verified.json`.

3. **Agent answers DAB Yelp query 1 with correct answer and query trace:** The agent returns the correct answer to the question *"What is the average rating of all businesses located in Indianapolis, Indiana?"* (ground truth: `3.547008547008547`) within 60 seconds. Response includes `query_trace` showing both the MongoDB and DuckDB queries executed. Output saved to `docs/yelp-query1-agent.json`.

4. **All three context layers are loaded and injection-tested:** `AGENT.md` is committed to `agent/` and loads schema context at session start. At least two documents in `kb/architecture/` and one in `kb/domain/` have passed their injection test (test query + expected answer documented in the respective `CHANGELOG.md`).

5. **Evaluation harness produces a baseline score:** Running the harness against the held-out Yelp query set returns a pass@1 score (any number, including 0%). Score and run metadata are committed to `eval/score_log.md` as Run #1.

6. **Agent is running on the shared server and accessible:** Any team member can SSH to the server and run the agent from a fresh terminal session following only the instructions in `README.md`. The Driver demonstrates this live at the Sprint 1 close mob session.

7. **Signal Corps: first post live and Slack log started:** At least one substantive X thread is live (link committed to `signal/engagement_log.md`). Daily Slack posts have been made for at least Days 3–5 of the sprint.

8. **This Inception document is mob-approved:** The full team has read this document together, asked their hardest questions, and given explicit group approval. Approval is recorded below with the date, who approved, and the hardest question asked and its answer.

---

## Mob Approval Record

**Status:** PENDING

| Field | Value |
|-------|-------|
| Approval date | |
| Approved by | |
| Hardest question asked | |
| Answer given | |
| Any items sent back for revision | |

*No Construction work begins until this section is filled in and committed.*
