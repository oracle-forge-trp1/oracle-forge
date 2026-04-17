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

### PROBE-017: Strict Mode Context Layers
- Category: Runtime Reliability
- Symptom: stakeholders cannot tell whether CORE KB, corrections log, and domain files load under `ORACLE_FORGE_STRICT_NO_LEAKAGE=1`.
- Expected robust behavior: `python scripts/verify_agent_context.py --dataset <key> --strict` reports OK for those sections unless `ORACLE_FORGE_STRICT_OMIT_KB=1`.

### PROBE-018: Validator helper imports
- Category: Runtime Reliability
- Symptom: harness fails loading `validate.py` with `ModuleNotFoundError: common_scaffold`.
- Expected robust behavior: DataAgentBench checkout includes top-level `common_scaffold/`; harness `--dab-root` points at that repo; optional fast-fail error names missing folder.

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
- Retire probes that are consistently passing across 3 consecutive runs.
