# Evaluation KB — Injection Test Results

## Test Protocol
Fresh LLM session with only the document as context. Ask a question it should answer. Grade pass/fail.

---

## Test 1: dab_benchmark.md

**Question:** "What is the current best score on the DAB benchmark and which agent achieved it?"

**Expected:** PromptQL with Gemini 3.1 Pro achieved 54.3% pass@1. The best baseline (non-proprietary) is Gemini 3 Pro at 38%.

**Result:** PASS — LLM correctly identified PromptQL's score and the baseline gap.

**Date:** 2026-04-15

---

## Test 2: dab_failure_modes.md

**Question:** "What percentage of DAB failures are due to incorrect planning vs incorrect implementation, and which is more common?"

**Expected:** FM2 (incorrect plan) = 40%, FM4 (incorrect implementation) = 45%. FM4 is slightly more common. Together they account for 85% of all failures.

**Result:** PASS — LLM provided exact percentages and noted the combined 85%.

**Date:** 2026-04-15

---

## Test 3: dab_failure_modes.md (applied to our agent)

**Question:** "How do the Oracle Forge Yelp probe results map to DAB failure modes?"

**Expected:** Corrections log entries 001-005 map to FM4 (implementation). Probes 009-013 map to FM2 (planning — wrong algorithmic approach). Probe 014 maps to FM3 (wrong data source selected).

**Result:** PASS — LLM used the mapping table in the document to correctly categorize the probes.

**Date:** 2026-04-15

---

## Summary
- **Total tests:** 3
- **Passed:** 3
- **Failed:** 0
