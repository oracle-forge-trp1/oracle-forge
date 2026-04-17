# KB v3 — Corrections Log (Leakage-Safe)

Purpose: capture reusable failure patterns and fixes without storing benchmark answer keys.

Policy:
- Do not store exact benchmark questions.
- Do not store expected outputs, winner identities, forbidden-value lists, or ground-truth numbers.
- Keep entries procedural and dataset-agnostic where possible.

Format:
- Failure pattern
- Root cause
- Correct approach
- Verification note

Entry metadata (recommended for every new entry):
- `confidence`: low | medium | high
- `last_verified_run_id`: run id from score log where rule was last validated
- `datasets_seen`: list of datasets where the pattern was observed
- `owner`: person responsible for maintenance
- `expires_after_runs`: review threshold for freshness

---

## Entry 001 — Cross-DB Key Normalization

Metadata:
- confidence: high
- datasets_seen: yelp, bookreview, crmarenapro
- expires_after_runs: 20

Failure pattern:
- Cross-database joins return zero rows even though related entities exist.

Root cause:
- Equivalent IDs use different string prefixes across systems.

Correct approach:
- Normalize both IDs to a canonical key before joining (for example, extract numeric suffix).
- Validate join cardinality after normalization.

Verification note:
- Add a sanity check query that confirms at least one joined row before final aggregation.

---

## Entry 002 — Mixed Datetime Formats

Metadata:
- confidence: high
- datasets_seen: yelp, stockindex, stockmarket
- expires_after_runs: 20

Failure pattern:
- Time-filtered counts/aggregates are unexpectedly low.

Root cause:
- Single-format datetime parsing drops rows with alternative formats.

Correct approach:
- Use `COALESCE` over multiple `TRY_STRPTIME` patterns.
- For year-only filters, use regex extraction as fallback.

Verification note:
- Compare parsed row count vs total non-null date rows.

---

## Entry 003 — Unstructured Location Fields

Metadata:
- confidence: medium
- datasets_seen: yelp, googlelocal
- expires_after_runs: 20

Failure pattern:
- City/state filters produce empty or partial results.

Root cause:
- Location is embedded in free text rather than structured columns.

Correct approach:
- Parse location with regex/text functions before filtering.
- Add a fallback parser for alternative phrasing.

Verification note:
- Spot-check parsed state/city values on a random sample.

---

## Entry 004 — String-Typed Numeric/Boolean Fields

Metadata:
- confidence: high
- datasets_seen: yelp, crmarenapro
- expires_after_runs: 20

Failure pattern:
- Numeric comparisons or boolean logic behave incorrectly.

Root cause:
- Source values are stored as strings.

Correct approach:
- Cast numeric strings before arithmetic.
- Normalize boolean-like values (`"1"`, `"0"`, `"true"`, `"false"`) before filtering.

Verification note:
- Assert conversion success rate and log cast failures.

---

## Entry 005 — Serialized Nested Attributes

Metadata:
- confidence: high
- datasets_seen: yelp
- expires_after_runs: 20

Failure pattern:
- Attribute-based filters miss valid entities.

Root cause:
- Nested structures are serialized strings or mixed types.

Correct approach:
- Parse only the serialized nested field when needed.
- Do not parse already-materialized dictionaries.
- Use tolerant matching for value variants.

Verification note:
- Count entities matching each accepted variant.

---

## Entry 006 — Avoid Average-of-Averages

Metadata:
- confidence: high
- datasets_seen: yelp, stockmarket, bookreview
- expires_after_runs: 20

Failure pattern:
- Final averages are biased high/low.

Root cause:
- Averaging per-group averages instead of raw observations.

Correct approach:
- Aggregate directly over row-level measurements whenever the metric requires equal weight per row.

Verification note:
- Compare row-level average with grouped-average result and reject inconsistent method.

---

## Entry 007 — Output Formatting Compatibility

Metadata:
- confidence: high
- datasets_seen: stockindex, yelp, bookreview
- expires_after_runs: 20

Failure pattern:
- Semantically correct answer fails validation.

Root cause:
- Output includes extra formatting/text that breaks parser assumptions.

Correct approach:
- Return compact plain text.
- Keep paired values adjacent (for example, code and country/value) with minimal separators.

Verification note:
- Run a local formatting check before returning final output.

---

## Entry 008 — Single-Winner Query Discipline

Metadata:
- confidence: medium
- datasets_seen: stockindex, stockmarket
- expires_after_runs: 20

Failure pattern:
- Correct winner is present but response still fails.

Root cause:
- Response includes extra alternatives, rankings, or commentary.

Correct approach:
- For single-winner prompts, return only the winning entity.
- Omit runner-up context unless explicitly requested.

Verification note:
- Enforce response-shape rule in post-processing.

---

## Entry 009 — Top-N Aggregation Completeness

Metadata:
- confidence: high
- datasets_seen: yelp, github_repos, music_brainz_20k
- expires_after_runs: 20

Failure pattern:
- Top categories/entities are incomplete or misordered.

Root cause:
- Aggregation was performed over truncated intermediate subsets.

Correct approach:
- Aggregate over full eligible population before ranking.
- Apply top-N only at the final ranking stage.

Verification note:
- Compare top-N from full run vs sampled/truncated run.

---

## Entry 010 — Required Identifier Emission

Metadata:
- confidence: high
- datasets_seen: crmarenapro, patents
- expires_after_runs: 20

Failure pattern:
- Validator rejects output due to missing required ID token (for example issue/article/record identifiers).

Root cause:
- Final answer is returned as narrative summary without explicitly emitting the identifier field.

Correct approach:
- Add an answer-contract check before finalize: if prompt intent asks for an identifier, output must include at least one ID-shaped token.
- Prefer explicit prefix style in final answer (for example `ID: <value>`), then optional explanation.

Verification note:
- Run regex assertion for required ID family before finalizing.

---

## Entry 011 — Exhaustive Set/List Coverage

Metadata:
- confidence: high
- datasets_seen: bookreview, yelp, agnews
- expires_after_runs: 20

Failure pattern:
- Output includes partial set/list where validator expects all qualifying items.

Root cause:
- Early truncation, premature finalize, or missing completeness check on grouped outputs.

Correct approach:
- Materialize full eligible set first, then render final list.
- Apply deterministic ordering and deduplicate before emitting values.

Verification note:
- Compare item_count in final output vs item_count from final aggregation table.

---

## Entry 012 — Policy Violation Contradiction Guard

Metadata:
- confidence: medium
- datasets_seen: crmarenapro
- expires_after_runs: 20

Failure pattern:
- Output states “no violation” while evidence rows indicate a violation class and related reference item.

Root cause:
- Decision statement not cross-checked against extracted evidence.

Correct approach:
- Force binary decision consistency check: if violation evidence rows are non-empty, final decision cannot be "no violation".
- Emit the supporting reference ID when violation evidence exists.

Verification note:
- Add pre-final invariant: `violation_detected == (evidence_count > 0)`.

---

## Entry 013 — Numeric Tolerance and Precision Discipline

Metadata:
- confidence: high
- datasets_seen: DEPS_DEV_V1, stockindex, yelp
- expires_after_runs: 20

Failure pattern:
- Numeric outputs fail validator tolerance checks despite near-correct intermediate calculations.

Root cause:
- Inconsistent rounding/formatting or omission of final numeric token.

Correct approach:
- Keep full precision internally; round only at final render according to prompt/validator expectation.
- Emit a single canonical numeric token in final answer.

Verification note:
- Run final numeric regex check and tolerance sanity check before response emission.

---

## Entry 014 — Taxonomy-Locked Classification Output

Metadata:
- confidence: medium
- datasets_seen: crmarenapro, agnews
- expires_after_runs: 20

Failure pattern:
- Classification label is semantically close but not one of accepted taxonomy labels.

Root cause:
- Free-form wording used instead of constrained label set.

Correct approach:
- Map evidence to a predefined allowed label set and emit exact canonical label text.
- Reject out-of-taxonomy labels in finalization step.

Verification note:
- Validate output label membership against allowed taxonomy list.

---

## Entry 015 — Temporal Token Compliance

Metadata:
- confidence: medium
- datasets_seen: agnews, stockmarket, googlelocal
- expires_after_runs: 20

Failure pattern:
- Time-related answer fails because required temporal token format is missing (for example month-name form).

Root cause:
- Date normalized for computation but rendered in non-required textual format.

Correct approach:
- Separate compute format from render format.
- When prompt implies month-level wording, render explicit month-name token in final output.

Verification note:
- Run date-render regex check (month-name presence) before finalize.

---

## Entry 016 — Empty Answer Fallback

Metadata:
- confidence: high
- last_verified_run_id: 2026-04-16-001
- datasets_seen: yelp (q2, q4)
- owner: IO
- expires_after_runs: never

Failure pattern:
- Agent reaches max iterations or encounters repeated tool failures without ever calling `return_answer`. Final output is an empty string. Validator always fails on empty answers.

Root cause:
- Complex multi-step queries (especially those requiring cross-DB joins with text extraction) consume many iterations. If the agent gets stuck in a retry loop or pursues a wrong extraction path, it exhausts iterations without synthesizing a final answer from the data it already gathered.

Correct approach:
- If approaching the iteration limit (e.g., iteration 25 of 30), synthesize a best-effort answer from data gathered so far rather than attempting more tool calls.
- A partial answer that contains the correct entity name (e.g., state code, category name) is far better than an empty string — validators check for presence of key tokens, not full explanations.
- When a tool call returns an error or empty result, do not retry the same query more than twice. Switch to an alternative approach or return what you have.

Verification note:
- Check: is the final answer non-empty? If empty, this correction was not applied.

---

## Template

Metadata:
- confidence:
- last_verified_run_id:
- datasets_seen:
- owner:
- expires_after_runs:

Failure pattern:
- 

Root cause:
- 

Correct approach:
- 

Verification note:
- 

Promotion checklist (before marking a new rule as trusted):
- Rule validated in at least 2 independent runs.
- Rule improves strict pass behavior, not only repaired behavior.
- Rule is phrased as reusable method, not query-specific hint.
- Rule passes leakage lint checks.
