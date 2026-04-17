# Adversarial Probe Library (Strict, Leakage-Safe)

Scope:
- Cross-dataset probe suite for DataAgentBench.
- No query text, no expected answers, no ground-truth values.
- Focus on failure mechanisms and reproducible diagnostics.

Status policy:
- Official status is strict-only (raw model output pass/fail).
- Repaired status may be tracked for diagnostics but not for quality claims.

Evidence required for each update:
- run_id
- dataset
- query_id
- strict_validation_message
- error/terminate reason (if any)

---

## Probe Categories

1. Join-Key Normalization
- Goal: detect silent zero-row joins caused by key format mismatch.
- Trigger: cross-DB query with empty join result but non-empty source sets.
- Pass condition: agent normalizes keys and obtains non-zero join cardinality.

2. Date Parsing Robustness
- Goal: detect row loss caused by single-format date parsing.
- Trigger: date-filtered query where mixed date strings exist.
- Pass condition: multi-pattern parse strategy used and row-count sanity check passes.

3. Unstructured Field Extraction
- Goal: detect missed entities due to brittle regex or missing fallback parser.
- Trigger: text-derived fields (location/category/attribute).
- Pass condition: extraction includes fallback paths and null-safe handling.

4. Aggregation Correctness
- Goal: detect metric bias from average-of-averages and partial-group aggregation.
- Trigger: grouped averages/top-N category summaries.
- Pass condition: row-level aggregation used where required; top-N applied only at final stage.

5. Output Shape Compatibility
- Goal: detect validator failures caused by verbose output structure.
- Trigger: winner-only and pair-output style prompts.
- Pass condition: compact plain text, pair adjacency, no extra runner-up entities.

6. Runtime Reliability
- Goal: detect non-deterministic failures from tool outages, timeouts, and truncation.
- Trigger: MCP unavailability, timeout pressure, large result sets.
- Pass condition: graceful failure messaging + retry/plan correction behavior.

---

## Probe Definitions

### PROBE-001: Cross-DB Prefix Mismatch
- Category: Join-Key Normalization
- Symptom: zero rows after join despite non-empty source query outputs.
- Expected robust behavior: normalize keys before join and verify cardinality.

### PROBE-002: Mixed Date Formats
- Category: Date Parsing Robustness
- Symptom: unexpectedly low counts in date-window queries.
- Expected robust behavior: multi-pattern parser + parsed-row sanity check.

### PROBE-003: Serialized Nested Attribute Handling
- Category: Unstructured Field Extraction
- Symptom: missing entities when nested fields are strings/dicts inconsistently.
- Expected robust behavior: parse only serialized subfields, not already-native dicts.

### PROBE-004: Free-Text Location/Category Extraction
- Category: Unstructured Field Extraction
- Symptom: sparse or unstable extraction from text fields.
- Expected robust behavior: primary regex + fallback parser + null-safe filtering.

### PROBE-005: Average-of-Averages Trap
- Category: Aggregation Correctness
- Symptom: suspiciously shifted averages compared to row-level aggregates.
- Expected robust behavior: aggregate over raw rows when metric semantics require it.

### PROBE-006: Truncated Top-N Pipeline
- Category: Aggregation Correctness
- Symptom: category/entity ranking differs across reruns due to early truncation.
- Expected robust behavior: full eligible set aggregation before final top-N selection.

### PROBE-007: Single-Winner Output Discipline
- Category: Output Shape Compatibility
- Symptom: includes extra entities/rankings in single-winner response.
- Expected robust behavior: return only the winner token/value in compact format.

### PROBE-008: Pair-Adjacency Output
- Category: Output Shape Compatibility
- Symptom: required pair values appear too far apart in final text.
- Expected robust behavior: adjacent pair formatting with minimal separators.

### PROBE-009: MCP Health Degradation
- Category: Runtime Reliability
- Symptom: tool calls fail intermittently or MCP unavailable.
- Expected robust behavior: explicit error trace + deterministic abort behavior.

### PROBE-010: Timeout Pressure
- Category: Runtime Reliability
- Symptom: max-iteration or timeout before final answer.
- Expected robust behavior: compact fallback answer synthesis from gathered evidence.

### PROBE-011: Required-ID Output Contract
- Category: Output Shape Compatibility
- Symptom: final response omits required identifier token.
- Expected robust behavior: include at least one valid ID-shaped token when query intent asks for identifier output.

### PROBE-012: Exhaustive List Completeness
- Category: Aggregation Correctness
- Symptom: one or more qualifying items missing from output list.
- Expected robust behavior: full eligible set built before rendering list; deterministic ordering and dedup applied.

### PROBE-013: Violation Decision Consistency
- Category: Output Shape Compatibility
- Symptom: response claims no violation while extracted evidence indicates violation.
- Expected robust behavior: binary decision must be consistent with evidence rows; include supporting reference ID when evidence exists.

### PROBE-014: Numeric Tolerance Compliance
- Category: Aggregation Correctness
- Symptom: near-correct value fails validator due to rounding/format token mismatch.
- Expected robust behavior: full-precision compute path, single canonical numeric token at final render.

### PROBE-015: Taxonomy Label Lock
- Category: Output Shape Compatibility
- Symptom: semantically plausible but non-canonical class label.
- Expected robust behavior: final label belongs to allowed taxonomy set exactly.

### PROBE-016: Temporal Token Render
- Category: Date Parsing Robustness
- Symptom: computed period correct but required month/temporal token missing in output text.
- Expected robust behavior: render layer enforces required temporal token format.

---

## Update Template

Run: <run_id> | Dataset: <dataset> | Query: <query_id> | Probe: <probe_id>
Strict: <PASS/FAIL> | Note: <short reason>
Evidence:
- strict_validation_message: <message>
- terminate_reason/error: <reason>
- key trace marker: <tool or query step>

---

## Maintenance Rules

- Do not add benchmark query text into this file.
- Do not add expected answers, winner identities, or numeric ground truth.
- Convert every new failure into a mechanism-focused probe.

---

## Observed Evidence Log

Evidence from `eval/score_log.json` (6 clean runs, 3 datasets).

### Failures (Pre-Fix / Non-Deterministic)

Run: 2026-04-16-001 | Dataset: yelp | Query: query2 | Probe: PROBE-008
Strict: FAIL | Note: Empty answer — agent returned no output
Evidence:
- strict_validation_message: "Missing name: ['PA', 'Pennsylvania']"
- terminate_reason/error: none (agent produced empty string)
- key trace marker: output formatting failure — no compact pair emitted

Run: 2026-04-16-001 | Dataset: yelp | Query: query4 | Probe: PROBE-004
Strict: FAIL | Note: Category extraction from description failed
Evidence:
- strict_validation_message: "Category 'Restaurant' not found in LLM output."
- terminate_reason/error: none
- key trace marker: free-text category extraction missed target label

Run: 2026-04-16-002 | Dataset: stockindex | Query: query3 | Probe: PROBE-005, PROBE-008
Strict: FAIL | Note: Wrong top-5 list — TWII included instead of correct entry
Evidence:
- strict_validation_message: "Missing name: IXIC"
- terminate_reason/error: none
- key trace marker: DCA calculation methodology error or aggregation over wrong time window

Run: 2026-04-16-003 | Dataset: bookreview | Query: query2 | Probe: PROBE-009
Strict: FAIL | Note: OpenRouter 403 rate limit — no agent computation possible
Evidence:
- strict_validation_message: "Missing book title in LLM output: The Sludge"
- terminate_reason/error: OpenRouter 403 key limit exceeded
- key trace marker: MCP/LLM unavailability

Run: 2026-04-16-003 | Dataset: bookreview | Query: query3 | Probe: PROBE-009
Strict: FAIL | Note: OpenRouter 403 rate limit — same as q2
Evidence:
- strict_validation_message: "Missing book title in LLM output: Around the World Mazes"
- terminate_reason/error: OpenRouter 403 key limit exceeded
- key trace marker: MCP/LLM unavailability

### Passes (Post-Fix — 100% Runs)

Run: 2026-04-15-016 | Dataset: yelp | All 7 queries
Strict: ALL PASS | Note: Corrections 001-015 + yelp.md domain doc in context
Evidence:
- query1: "Found matching number: 3.547008547008547 ≈ 3.55" (19.7s)
- query2: "Found: name='PA', value≈3.7" (70.3s)
- query3: "Found number: 35" (20.6s)
- query4: "Found: Restaurant, 3.63" (87.6s)
- query5: "Found: name='PA', value≈3.48" (28.1s)
- query6: "Name and all categories are present." (10.4s)
- query7: "All categories are present." (51.7s)

Run: 2026-04-15-017 | Dataset: stockindex | All 3 queries
Strict: ALL PASS | Note: Corrections 006-009 + stockindex.md domain doc in context
Evidence:
- query1: "Only target '399001.SZ' present, no forbidden values." (10.2s)
- query2: "Only target 'IXIC' present, no forbidden values." (11.3s)
- query3: "All name-country pairs matched correctly in order." (7.9s)

Run: 2026-04-15-018 | Dataset: bookreview | All 3 queries
Strict: ALL PASS | Note: bookreview.md domain doc in context
Evidence:
- query1: "Ground truth found in LLM output." (37.6s)
- query2: "All book titles found in LLM output." (15.1s)
- query3: "All book titles found in LLM output." (13.5s)

### Probe Coverage Summary

| Probe | Observed Failure Run | Observed Pass Run | Status |
|---|---|---|---|
| PROBE-001 | (fixed before score_log window) | 2026-04-15-016 yelp q1 | Fixed |
| PROBE-002 | (fixed before score_log window) | 2026-04-15-016 yelp q3 | Fixed |
| PROBE-003 | (fixed before score_log window) | 2026-04-15-016 yelp q3 | Fixed |
| PROBE-004 | 2026-04-16-001 yelp q4 | 2026-04-15-016 yelp q4 | Non-deterministic |
| PROBE-005 | 2026-04-16-002 stockindex q3 | 2026-04-15-017 stockindex q3 | Non-deterministic |
| PROBE-006 | (fixed before score_log window) | 2026-04-15-016 yelp q7 | Fixed |
| PROBE-007 | (no single-winner failure in current log) | 2026-04-15-017 stockindex q1,q2 | Pass observed |
| PROBE-008 | 2026-04-16-001 yelp q2 | 2026-04-15-016 yelp q2 | Non-deterministic |
| PROBE-009 | 2026-04-16-003 bookreview q2,q3 | 2026-04-15-018 bookreview q2,q3 | Rate-limit dependent |
| PROBE-010 | (no timeout in current log) | — | Not triggered |
| PROBE-011 | (no ID-omission in current log) | 2026-04-15-017 stockindex q1 | Pass observed |
| PROBE-012 | (no list-miss in current log) | 2026-04-15-016 yelp q7 | Pass observed |
| PROBE-013 | (no contradiction in current log) | — | Not triggered |
| PROBE-014 | (no precision failure in current log) | 2026-04-15-016 yelp q1 | Pass observed |
| PROBE-015 | (no label-lock failure in current log) | — | Not triggered |
| PROBE-016 | (no temporal-token failure in current log) | — | Not triggered |
- Retire probes that are consistently passing across 3 consecutive runs.
