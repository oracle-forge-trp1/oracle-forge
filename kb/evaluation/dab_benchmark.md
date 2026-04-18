# DataAgentBench (DAB) — Benchmark Overview

## What DAB Tests
DAB is the first benchmark for evaluating AI data agents on realistic enterprise workloads. Created by UC Berkeley EPIC Data Lab in collaboration with PromptQL (Hasura), published March 2026.

## Scale
- **54 queries** across **12 datasets** in **9 domains**
- **4 database systems:** PostgreSQL, SQLite, DuckDB, MongoDB
- Multiple DBs per query — cross-database joins required

## Current Leaderboard (March 2026)

| Agent | Model | Pass@1 | Trials | Framework |
|---|---|---|---|---|
| PromptQL | Gemini 3.1 Pro | 54.3% | 5/query | Proprietary |
| Baseline | Gemini 3 Pro | 38% | 2,700 | ReAct |
| Baseline | GPT-5-mini | 30% | 2,700 | ReAct |
| Baseline | GPT-5.2 | 25% | 2,700 | ReAct |
| Baseline | Kimi-K2 | 23% | 2,700 | ReAct |
| Baseline | Gemini 2.5 Flash | 9% | 2,700 | ReAct |

## Scoring Method
- **Pass@1** = fraction of queries answered correctly on the first attempt, averaged across n trials per query
- Score computed per-dataset first, then averaged across datasets (stratified)
- Minimum **5 trials** per query required for submission

## Submission Format
Run agent on all 54 queries, collect results as JSON:
```json
[{"dataset": "example_dataset", "query": "1", "run": 0, "answer": "computed_answer"}]
```
Submit via GitHub PR to `ucbepic/DataAgentBench`.

## The Four Hard Requirements
1. **Multi-database integration** — single query spans 2+ DB types
2. **Ill-formatted join keys** — same entity, different ID formats across DBs
3. **Unstructured text transformation** — extract structured facts from free-text fields
4. **Domain knowledge** — terms not in schema (churn, active customer, fiscal year)

## Key Finding from Paper
FM2 (incorrect plan) + FM4 (incorrect implementation) = **85% of all failures**. Data discovery is rarely the problem — planning and execution are.
