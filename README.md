# Oracle Forge — Data Analytics Agent 1

**Team:** Oracle Forge (TRP1 FDE Programme, April 2026)  
**Challenge:** Weeks 8–9 — Context Engineering & Evaluation Science  
**Benchmark:** DataAgentBench (DAB) by UC Berkeley EPIC Data Lab

## Team Members & Roles

| Member | Role |
|--------|------|
| Birkity Yishak | Driver (Team Lead) |
| Beamlak Adane | Driver |
| Atnabon Deressa | Intelligence Officer |
| Yonas Eshete | Intelligence Officer |
| Zemzem Hibet| Signal Corps |

## What We Are Building

Oracle Forge is a production-grade natural language data analytics agent that answers complex business questions across heterogeneous enterprise databases (PostgreSQL, MongoDB, SQLite, DuckDB). It applies engineering principles from the Claude Code architecture, context-layering patterns from OpenAI's internal data agent, and is evaluated against the UC Berkeley DataAgentBench (DAB) benchmark.

**Three core engineering challenges:**

1. **Multi-layer context architecture** — Three context layers: schema/metadata knowledge, institutional/domain knowledge, and interaction memory (corrections and successful patterns).
2. **Self-correcting execution across heterogeneous databases** — Detects failures, diagnoses root cause (query error, join key mismatch, DB type issue, data quality), and recovers without surfacing errors to the user.
3. **Evaluation harness with measurable improvement** — Sentinel-pattern trace log, query outcome scores against expected results, regression suite showing score progression from Week 8 to benchmark submission.

## Architecture

> Architecture diagram will be added after Inception approval.

**High-level design:**

```
User NL Query
     │
     ▼
┌─────────────────────────────────────────┐
│              Agent Core                 │
│  ┌──────────────────────────────────┐   │
│  │   Context Layers                 │   │
│  │  1. Schema & metadata (all DBs)  │   │
│  │  2. Institutional knowledge (KB) │   │
│  │  3. Interaction memory / corr.   │   │
│  └──────────────────────────────────┘   │
│  ┌──────────────────────────────────┐   │
│  │   Query Planner & Router         │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│           MCP Toolbox (tools.yaml)           │
│  PostgreSQL │ MongoDB │ SQLite │ DuckDB       │
└──────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│         Code Execution Sandbox          │
│   Runs, validates, returns trace JSON   │
└─────────────────────────────────────────┘
     │
     ▼
Verified answer + query trace
```

## Setup Instructions

### Prerequisites

- SSH access to the team EC2 server (`deepseek.10academy.org`)
- Python 3.11+
- PostgreSQL 16, MongoDB 7, DuckDB, SQLite3
- Docker installed
- Conda/Miniforge installed

### Quick Start (for facilitator)

```bash
ssh trp-deepseek
cd /shared/oracle-forge

# Activate the DAB environment
conda activate dab

# Install Python dependencies
pip install -r agent/requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your API keys and database connection strings

# Start MCP Toolbox (connects agent to all four DB types)
./toolbox --config mcp/tools.yaml &

# Start the code execution sandbox
python3 sandbox/sandbox_server.py --port 8080 &

# Start the agent
# [instructions added after agent is built]
```

### Full Infrastructure Setup (from scratch)

```bash
# 1. Clone this repository
git clone https://github.com/oracle-forge/oracle-forge.git
cd oracle-forge

# 2. Clone and load DataAgentBench datasets
git clone https://github.com/ucbepic/DataAgentBench.git
cd DataAgentBench && pip install -r requirements.txt
bash setup/load_postgres.sh   # Load PostgreSQL datasets first
# Then SQLite, MongoDB, DuckDB in that order
cd ..

# 3. Download and configure MCP Toolbox
export VERSION=0.30.0
curl -O https://storage.googleapis.com/genai-toolbox/v$VERSION/linux/amd64/toolbox
chmod +x toolbox
./toolbox --config mcp/tools.yaml

# 4. Verify all four database connections
curl http://localhost:5000/v1/tools | python3 -m json.tool | grep name

# 5. Run a smoke test against the Yelp dataset
cd DataAgentBench
python eval/run_query.py --dataset yelp --query 0
```

### Live Agent Access

- Server: `deepseek.10academy.org`
- Agent endpoint: [TBD after deployment]

## Repository Structure

```
oracle-forge/
├── README.md                        # This file
├── .env.example                     # Environment variable template
│
├── agent/                           # Agent source code
│   ├── AGENT.md                     # Agent context file (loaded at session start)
│   ├── requirements.txt
│   └── [agent source files]
│
├── mcp/
│   └── tools.yaml                   # MCP Toolbox: all four DB connections + tools
│
├── sandbox/
│   └── sandbox_server.py            # Code execution sandbox (POST /execute)
│
├── kb/                              # LLM Knowledge Base (Karpathy method)
│   ├── architecture/                # Claude Code 3-layer memory, OpenAI 6-layer context
│   ├── domain/                      # DAB schemas, join key glossary, domain terms
│   ├── evaluation/                  # DAB query format, scoring, harness schema
│   └── corrections/                 # Self-learning loop: failures → correct approaches
│
├── eval/                            # Evaluation harness
│   ├── harness.py                   # Sentinel-pattern trace + scoring
│   ├── score_log.md                 # Score progression (Week 8 baseline → final)
│   └── held_out/                    # Held-out test set with expected answers
│
├── probes/
│   └── probes.md                    # 15+ adversarial probes across 3+ failure categories
│
├── planning/                        # AI-DLC governance
│   └── inception_sprint1.md         # Inception document with mob approval record
│
├── utils/                           # Shared utility library (3+ documented modules)
│
├── results/                         # Benchmark outputs
│   ├── team_oracle_forge_results.json  # DAB results (54 queries, ≥5 trials each)
│   └── score_log.md                 # Harness score progression
│
├── signal/                          # Signal Corps deliverables
│   ├── engagement_log.md            # All post links + metrics
│   └── community_log.md             # Reddit/Discord/X substantive comment links
│
├── scripts/                         # Setup and utility scripts
│
└── docs/                            # Additional documentation
```

## Benchmark — DataAgentBench (DAB)

DAB is the first benchmark evaluating AI data agents on realistic enterprise workloads, produced by the UC Berkeley EPIC Data Lab in collaboration with PromptQL (Hasura).

| Property | Specification |
|----------|---------------|
| Total queries | 54 queries across 12 datasets |
| Domains | 9 (retail, telecom, healthcare, finance, anti-money laundering, …) |
| Database systems | PostgreSQL, MongoDB, SQLite, DuckDB |
| Current best score | PromptQL + Gemini 3.1 Pro: 54.3% pass@1 |
| Evaluation method | n ≥ 50 trials per query, submit results JSON via GitHub PR |

**The four hard requirements our agent must handle:**

| Challenge | What it means | Connected prior work |
|-----------|---------------|----------------------|
| Multi-database integration | Single query spans multiple DB systems with different query dialects | Week 4 Conductor/worker routing pattern |
| Ill-formatted join keys | `CustomerID` is `12345` in PostgreSQL and `"CUST-12345"` in MongoDB | Week 7 Data Contract Enforcer format detection |
| Unstructured text transformation | Extract structured facts from free-text fields before aggregating | Week 3 Document Intelligence Refinery |
| Domain knowledge | "Active customer" means purchased in last 90 days, not just row exists | KB institutional knowledge layer |

### Running the Evaluation

```bash
# Run the full benchmark (takes ~2 hours)
cd DataAgentBench
python eval/run_benchmark.py \
  --agent oracle_forge_agent \
  --trials 50 \
  --output ../results/team_oracle_forge_results.json

# Score the results
python eval/score.py --results ../results/team_oracle_forge_results.json
```

### Benchmark Submission

```bash
# Fork ucbepic/DataAgentBench on GitHub, then:
cp results/team_oracle_forge_results.json \
   DataAgentBench/submission/team_oracle_forge_results.json

git add submission/team_oracle_forge_results.json agent/AGENT.md
git commit -m "Add Oracle Forge DAB evaluation results"
git push origin main

# Open PR to ucbepic/DataAgentBench
# Title: "Oracle Forge — TRP1 FDE Programme, April 2026"
```

## Deliverables & Deadlines

| Deliverable | Owner | Weight | Deadline |
|-------------|-------|--------|----------|
| Running agent on shared server (live demo) | Drivers | 25% | Apr 14 |
| Benchmark submission — DAB results JSON via GitHub PR (n ≥ 50 trials) | Drivers | 20% | Apr 18 |
| LLM Knowledge Base v1/v2/v3 with injection test evidence | Intelligence Officers | 15% | Apr 14/18 |
| Evaluation harness with score log showing improvement | Drivers + IOs | 10% | Apr 18 |
| Adversarial probe library — 15+ probes, 3+ categories | Intelligence Officers | 10% | Apr 18 |
| Signal Corps engagement portfolio | Signal Corps | 10% | Apr 18 |
| AI-DLC Inception documents with team approval records | Drivers | 5% | Apr 14 |
| Shared utility library — documented, tested, reusable | Intelligence Officers | 5% | Apr 18 |

**Interim submission:** Tuesday, April 14 — 21:00 UTC (GitHub repo + PDF report)  
**Final submission:** Saturday, April 18 — 21:00 UTC (GitHub repo + PDF + demo video)

## Key References

| Resource | URL |
|----------|-----|
| DataAgentBench repository | github.com/ucbepic/DataAgentBench |
| DataAgentBench paper | arxiv.org/html/2603.20576 |
| Google MCP Toolbox for Databases | github.com/googleapis/genai-toolbox |
| Claude Code architecture analyses | github.com/sanbuphy/claude-code-source-code |
| OpenAI data agent writeup | openai.com/index/inside-our-in-house-data-agent |
| Karpathy LLM Knowledge Bases | academy.dair.ai/blog/llm-knowledge-bases-karpathy |
| AWS AI-DLC framework | aws.amazon.com/blogs/devops/ai-driven-development-life-cycle/ |
| Cloudflare Workers free tier | workers.cloudflare.com |

---

*TRP1 FDE Programme · Tenacious Intelligence Corp · April 2026*
