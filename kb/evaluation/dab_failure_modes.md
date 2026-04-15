# DAB Failure Mode Taxonomy

## Source
Analysis of 1,147 completed-but-incorrect trajectories from the DAB paper (arxiv.org/html/2603.20576), across 5 baseline models.

## The Five Failure Modes

### FM1 — Fails Before Planning (0%)
Agent refuses to attempt the query entirely. Effectively never happens with current models.

### FM2 — Incorrect Plan (40% of failures)
Agent formulates a flawed computational strategy. The logic is wrong before any code runs.

**Examples from our Yelp runs:**
- PROBE-009: Agent averages per-business averages instead of flat avg over all review rows
- PROBE-010: Agent computes WiFi avg over all states instead of only the top state
- PROBE-011: Agent picks categories from top-5 businesses instead of aggregating across all businesses

**Fix pattern:** Add explicit algorithmic instructions to AGENT.md (numbered steps). Domain knowledge corrections directly target FM2.

### FM3 — Incorrect Data Selection (15% of failures)
Agent selects wrong tables or columns despite having a correct methodology.

**Examples from our Yelp runs:**
- PROBE-014: Agent routes "review count" to MongoDB `review_count` field (stale cached value) instead of DuckDB `review` table (actual rows)

**Fix pattern:** Add routing rules (R1 in AGENT.md: "Review counts come from DuckDB, never MongoDB").

### FM4 — Incorrect Implementation (45% of failures)
Agent has the right plan and right data but executes incorrectly — wrong SQL, bad joins, calculation errors.

**Examples from our Yelp runs:**
- PROBE-001: Direct string join `businessid_N` = `businessref_N` returns 0 rows
- PROBE-003: Single TRY_STRPTIME format silently drops non-ISO date rows
- PROBE-005: Querying non-existent `category` field
- PROBE-006: WiFi equality check fails on `"u'free'"` format
- PROBE-007: `ast.literal_eval` on full dict instead of only the parking sub-string

**Fix pattern:** Self-correction with specific implementation rules. Corrections log entries directly target FM4.

### FM5 — Runtime Errors (negligible, except Kimi-K2 at 6.6%)
Agent code crashes (syntax error, timeout, OOM). Our runs 006-007 hit this via OpenRouter rate limits (402/403).

## Critical Pattern: No LLM-Based Text Extraction
Every baseline agent tested used regex exclusively for text extraction. None attempted LLM-based extraction for sentiment, entity extraction, or semantic classification. This is a structural blind spot.

## Mapping to Our Corrections Log

| Corrections Log Entry | Failure Mode | Probe |
|---|---|---|
| Entry 001 — join key mismatch | FM4 | PROBE-001 |
| Entry 002 — mixed date formats | FM4 | PROBE-003 |
| Entry 003 — location from description | FM4 | PROBE-004 |
| Entry 004 — string-typed fields | FM4 | PROBE-007 |
| Entry 005 — checkin date format | FM4 | PROBE-003 |

## Score Impact
Our agent moved from 0/7 (no corrections) to 3/7 (42.86%) by adding 5 corrections targeting FM4. The remaining 4 failures are split between FM2 (queries 5, 7) and FM4 (queries 3, 4). Addressing FM2 requires algorithmic corrections, not just format fixes.
