# Weekly Global Ecosystem Report - Week 8

**Date:** 2026-04-11
**Author:** Intelligence Officer

---

## 1. DataAgentBench (DAB) — Benchmark Landscape

### Current Leaderboard (as of March 2026)

| Agent    | Model            | Pass@1    | Trials  | Framework   |
| -------- | ---------------- | --------- | ------- | ----------- |
| PromptQL | Gemini 3.1 Pro   | **54.3%** | 5/query | Proprietary |
| Baseline | Gemini 3 Pro     | 38%       | 2,700   | ReAct       |
| Baseline | GPT-5-mini       | 30%       | 2,700   | ReAct       |
| Baseline | GPT-5.2          | 25%       | 2,700   | ReAct       |
| Baseline | Kimi-K2          | 23%       | 2,700   | ReAct       |
| Baseline | Gemini 2.5 Flash | 9%        | 2,700   | ReAct       |

**Source:** [DAB Paper](https://arxiv.org/html/2603.20576), [DAB Leaderboard](https://ucbepic.github.io/DataAgentBench/)

### Key Finding: Where Agents Fail

The DAB paper analyzed 1,147 incorrect trajectories across all baseline agents:

- **45% — Incorrect Implementation (FM4):** Agent selects the right data and logic but executes incorrectly (wrong SQL syntax, bad joins, calculation errors)
- **40% — Incorrect Plan (FM2):** Agent formulates a flawed computational strategy that cannot produce the right answer
- **15% — Incorrect Data Selection (FM3):** Agent picks the wrong tables or columns despite correct methodology
- **~0% — Fails Before Planning (FM1):** Agents almost never refuse to attempt a query
- **Negligible — Runtime Errors (FM5):** Except Kimi-K2 at 6.6%

**Takeaway for our team:** FM2 + FM4 = 85% of failures. Better context engineering (domain terms, query patterns) directly targets FM2. Better self-correction and validation targets FM4. This is exactly what our KB v2 and evaluation harness are designed to address.

### Critical Pattern: No Agent Uses LLM-Based Text Extraction

Every tested baseline agent used regex-based extraction exclusively for unstructured text fields. None attempted NLP or LLM-based extraction. This causes systematic failures on queries requiring semantic understanding (e.g., sentiment classification, entity extraction from free-text fields).

**Opportunity:** If our agent uses LLM-based extraction for unstructured fields (review text, support notes, clinical notes), we have a structural advantage over all baseline agents on those query types.

### PromptQL Partnership

PromptQL (by Hasura) co-developed DAB with UC Berkeley's EPIC Data Lab. PromptQL's proprietary agent improves pass@1 by 7 percentage points over the ReAct baseline with the same model. Their approach extends Hasura's data-access infrastructure to connect heterogeneous sources (PostgreSQL, Snowflake, BigQuery, MongoDB, MySQL, SaaS tools).

**Source:** [PromptQL Blog](https://promptql.io/blog/partnering-with-uc-berkeley-to-build-the-benchmark-enterprise-ai-needs), [GlobeNewsWire Announcement](https://www.globenewswire.com/news-release/2025/06/04/3093929/0/en/PromptQL-Partners-with-UC-Berkeley-to-Develop-New-Data-Agent-Benchmark-for-Reliability-of-Enterprise-AI-Agents.html)

---

## 2. Claude Code Source Leak — Architecture Insights

### What Happened

On March 31, 2026, Anthropic's Claude Code (their agentic CLI tool) had its entire source code exposed via npm source maps. A known Bun bug (issue #28001) caused source maps to ship in production builds. The exposure lasted ~3 hours. The codebase: **512,000 lines across 1,906 TypeScript files**.

**Source:** [The Register](https://www.theregister.com/2026/03/31/anthropic_claude_code_source_code/), [VentureBeat](https://venturebeat.com/technology/claude-codes-source-code-appears-to-have-leaked-heres-what-we-know), [DEV Community](https://dev.to/gabrielanhaia/claude-codes-entire-source-code-was-just-leaked-via-npm-source-maps-heres-whats-inside-cjo)

### Architecture Findings Relevant to Our Agent

| Component              | What Was Revealed                                                                                                              | How It Applies to Us                                                                        |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| **Tool System**        | ~40 discrete tools, each permission-gated. Base tool definition alone is 29,000 lines.                                         | Our MCP Toolbox tools.yaml follows the same pattern — discrete tools per database operation |
| **Memory System**      | MEMORY.md as lightweight index of pointers, always loaded. Topic files fetched on-demand. Raw transcripts never fully re-read. | Our KB architecture (index → topic files) directly mirrors this. Validates our approach.    |
| **Sub-Agent Spawning** | Can spawn "swarms" — sub-agents with their own context and tool permissions for parallelizable tasks.                          | Relevant for our multi-database routing — could spawn per-database sub-queries in parallel  |
| **Query Engine**       | 46,000 lines handling all LLM API calls, streaming, caching. Largest single module.                                            | Shows the query orchestration layer is the hardest engineering challenge                    |
| **KAIROS**             | Unreleased autonomous daemon mode referenced 150+ times. Claude as persistent background agent.                                | Not directly applicable, but shows where Anthropic is heading                               |

**Community repos studying the code:**

- [sanbuphy/claude-code-source-code](https://github.com/sanbuphy/claude-code-source-code) — 9k+ stars, includes English docs analyzing architecture
- The Python fork became one of the fastest-growing GitHub projects in history (111K stars in one day)

**Source:** [Layer5 Analysis](https://layer5.io/blog/engineering/the-claude-code-source-leak-512000-lines-a-missing-npmignore-and-the-fastest-growing-repo-in-github-history/), [Alex Kim's Deep Dive](https://alex000kim.com/posts/2026-03-31-claude-code-source-leak/)

---

## 3. OpenAI In-House Data Agent — Six-Layer Context

OpenAI published a detailed writeup of their internal data agent that makes 70,000+ datasets and 600 petabytes of data searchable via natural language.

### The Six Layers

| Layer                      | What It Does                                                      | Our Equivalent                                       |
| -------------------------- | ----------------------------------------------------------------- | ---------------------------------------------------- |
| 1. Schema Metadata         | Column names, data types, historical query patterns               | KB v2 `dab_schemas.md`                               |
| 2. Curated Descriptions    | Domain expert annotations on semantics and limitations            | KB v2 `domain_terms.md`                              |
| 3. Codex Enrichment        | Crawl codebase to derive deeper table definitions                 | Not implemented — potential Week 9 enhancement       |
| 4. Institutional Knowledge | Search Slack, Docs, Notion for product/metric context             | KB v2 `query_patterns.md` + `unstructured_fields.md` |
| 5. Learning Memory         | Corrections from previous conversations applied to future queries | KB v3 `corrections_log.md`                           |
| 6. Live Query              | Query data warehouse when no prior info exists                    | Agent's direct DB querying via MCP Toolbox           |

**Performance impact:** Without memory, a test query took 22 minutes. With memory: 1 minute 22 seconds.

**Source:** [OpenAI Blog](https://openai.com/index/inside-our-in-house-data-agent/), [The Decoder](https://the-decoder.com/openai-develops-six-layer-context-system-to-help-employees-navigate-600-petabytes-of-data/), [VentureBeat](https://venturebeat.com/technology/openais-ai-data-agent-built-by-two-engineers-now-serves-4-000-employees-and)

---

## 4. MCP Toolbox for Databases — Latest State

Google's MCP Toolbox for Databases (formerly Gen AI Toolbox) latest release: **v0.30.0** (March 20, 2026). Repository recently renamed from `genai-toolbox` to `mcp-toolbox`.

Key facts:

- Still in beta — breaking changes possible before v1.0
- Now supports MCP protocol natively — connects to Gemini CLI, Claude Code, Codex
- Prebuilt tools available for common database operations
- Supports PostgreSQL, MySQL, SQL Server, Cloud SQL, AlloyDB, Spanner, Bigtable
- **Does NOT natively support MongoDB, SQLite, or DuckDB** — we need custom tool definitions for these in our tools.yaml

**Source:** [MCP Toolbox Docs](https://googleapis.github.io/genai-toolbox/), [GitHub Releases](https://github.com/googleapis/genai-toolbox/releases)

---

## 5. Open-Source Data Agent Landscape

| Tool                                              | What It Does                                                                                                 | Stars       | Relevance                                               |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ----------- | ------------------------------------------------------- |
| [WrenAI](https://github.com/Canner/WrenAI)        | Text-to-SQL + charts with semantic layer (MDL). Supports 12+ data sources, any LLM.                          | Active      | Semantic layer approach relevant to our domain terms KB |
| [Vanna AI 2.0](https://github.com/vanna-ai/vanna) | Complete rewrite — now a production-ready agent framework. Supports any LLM + any database including DuckDB. | Active      | Closest open-source equivalent to what we're building   |
| [Chat2DB](https://chat2db.ai/)                    | Most popular text-to-SQL on GitHub (1M+ users). Apache 2.0 license.                                          | Very active | Could study their multi-database routing approach       |
| [DBHub](https://github.com/bytebase/dbhub)        | Universal database MCP server — bridges AI assistants to databases via MCP protocol.                         | Growing     | Alternative to Google MCP Toolbox for our architecture  |
| [DB-GPT](https://github.com/eosphoros-ai/DB-GPT)  | Multi-agent text-to-SQL framework. Ambitious but documentation gaps noted.                                   | Active      | Multi-agent architecture worth studying                 |

**Source:** [Bytebase Comparison](https://www.bytebase.com/blog/top-text-to-sql-query-tools/), [vanducng Analysis](https://vanducng.dev/2026/02/06/Data-Agents-From-OpenAI-to-Open-Source/)

---

## 6. Implications for Our Team

### What to prioritize this week:

1. **LLM-based text extraction** — No DAB baseline agent does this. Using LLM classification for unstructured fields (review text, support notes) gives us a structural advantage on ~20% of failure cases.

2. **Context engineering over model choice** — PromptQL's 54.3% vs Gemini 3 Pro's 38% with the same model proves that context engineering (not model selection) is the differentiator. Our KB v2 rewrite with real DAB schemas is the right investment.

3. **Self-correction targeting FM4** — 45% of failures are correct plan, wrong execution. Building a validation step that checks query results against expected patterns before returning to the user would target the single largest failure mode.

4. **CRM dataset (crmarenapro) is the high-value target** — 13 queries (24% of DAB), 6 databases, known data corruption patterns. Getting this dataset right yields the most benchmark points per engineering hour.

5. **MCP Toolbox limitation** — Google's toolbox doesn't natively support MongoDB, SQLite, or DuckDB. Our custom tools.yaml definitions for these are necessary, not optional.
