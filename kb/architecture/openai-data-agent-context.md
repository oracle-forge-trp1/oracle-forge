# OpenAI Data Agent — Six-Layer Context Architecture

## Overview

OpenAI's internal data agent serves 4,000+ employees, querying 600+ petabytes across 70,000 datasets. Built by two engineers in three months. It uses no fine-tuning — all intelligence comes from context engineering.

## The Six Context Layers

The agent assembles six layers of context before answering any question:

**Layer 1 — Basic Schema Metadata**
Table definitions, column names, types, and relationships. The structural foundation.

**Layer 2 — Codex Enrichment (Table Enrichment)**
A daily offline pipeline where Codex inspects tables and their pipeline code, inferring: dependencies, table ownership, data granularity, join keys, and similar tables. Results are persisted and converted to embeddings for retrieval.

**Layer 3 — Curated Expert Descriptions**
Hand-written descriptions of key tables and dashboards by domain experts. Captures what schema metadata cannot — what a table is used for, which columns matter, canonical query patterns.

**Layer 4 — Institutional Knowledge**
Information mined from Slack, Google Docs, and Notion — business term definitions, metric ownership, team conventions.

**Layer 5 — Learning Memory**
Corrections from prior conversations. When users flag incorrect results, fixes feed back into the system. The self-learning loop — the agent improves from its own mistakes without retraining.

**Layer 6 — Live Query Fallback**
Direct warehouse access when no prior mapping exists. The agent queries the warehouse in real time to discover tables not yet covered by the other five layers.

## Retrieval Strategy

When a user asks about a metric (e.g. "revenue"), the agent queries a vector database to find tables that Codex has linked to that concept. Historical query patterns are tiered: exploratory queries ("SELECT * LIMIT 10") are deprioritized while canonical dashboards and executive reports are elevated as sources of truth.

## Self-Correction Approach

The agent uses prompt engineering to slow itself down: extended discovery phases, gathering multiple table alternatives, comparing candidates before committing, and self-evaluation at task completion. More context is not always better — curated, smaller context windows outperformed large, noisy ones in internal evaluations.

## Key Insight for Our Agent

Context layers are the architecture. The model is the same for everyone. The difference between a 38% DAB score and a competitive one is how much the agent knows before it writes its first query — schema, join keys, domain terms, past corrections. Each layer we add to our agent's context directly closes the gap.
