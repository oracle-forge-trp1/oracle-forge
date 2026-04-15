# AI-DLC Inception Document — Sprint 2
**Project:** Oracle Forge — Data Analytics Agent
**Sprint:** 2 of 2 (Week 9, Days 1–4)
**Focus:** Fix Yelp failures, extend to additional datasets, benchmark, DAB submission, demo video
**Date drafted:** 2026-04-14
**Sprint window:** April 14–18, 2026
**Approval status:** PENDING — must be approved at mob session before Construction begins

---

## 1. Press Release

The Oracle Forge team has submitted a working data analytics agent to the DataAgentBench leaderboard with scores across multiple datasets. The agent answers natural language questions against a heterogeneous multi-database setup — MongoDB, DuckDB, PostgreSQL, and SQLite — resolving cross-database join key mismatches automatically and returning verified answers with a full query trace. All 12 DAB datasets and all 4 database types were evaluated; Yelp improved from a 42.86% peak to at least 71% (5 of 7 queries) in a verified 5-trial benchmark run, and at least one additional dataset was benchmarked and scored. The agent was trained not through model fine-tuning but through adversarial probing: 15 targeted failure cases were written, each failure was diagnosed, and the fix was encoded directly into the agent's operating context. Every correction that was applied improved the score. The final submission includes a published knowledge base of 15 adversarial probes with observed failures and post-fix outcomes, a corrections log showing agent improvement across evaluation runs, and a demo video recorded on the shared EC2 server. This sprint completed in four days by one person operating under token budget constraints.

---

## 2. Honest FAQ — User

**Q1: Can the agent answer all 7 Yelp benchmark questions correctly now?**
Not reliably. At Sprint 1's best, it answered 3 of 7 correctly in a single run. With the documented fixes now in AGENT.md, it should answer at least 5 of 7 correctly — but two queries (query5: WiFi state + average rating, query7: top 5 categories from 2016 users) have never fully passed in any run. Those fixes are documented but unvalidated due to token exhaustion before any re-run could be completed. Sprint 2 exists specifically to run those re-validations.

**Q2: Will this be submitted to the real DataAgentBench leaderboard?**
Yes, that is the goal. DAB accepts submissions via pull request to their public repository. The submission requires the agent module, a reproducible run script, and documented scores. Whether the PR is merged and the score appears on the public leaderboard depends on DAB's review timeline, which is outside our control — but the PR itself will be submitted by April 18.

**Q3: What is a realistic final score?**
For Yelp (7 queries): honest range 5–6 passing. Queries 1 and 6 are reliable. Query 3 was passing before a regression and should re-pass with the documented fix. Queries 2, 4, and 7 are likely to pass with fixes already in AGENT.md. Query 5 (WiFi avg — 3-step per-state algorithm) has not passed in any run yet and is the hardest remaining failure.

For additional datasets: the infrastructure (PostgreSQL, SQLite, all 12 datasets loaded) is already in place. Datasets whose queries don't require complex cross-database joins or Yelp-specific unstructured text parsing should be achievable with the existing agent and minimal context additions. Realistically, 1–3 additional datasets will be benchmarked in Sprint 2; how many pass depends on their query complexity. A score of 0% on a new dataset is still a valid benchmark result — it tells us what the next probe set needs to target.

---

## 3. Honest FAQ — Technical

**Q1: Why did the Sprint 1 score collapse from 3/7 to 0/7 at the end?**
OpenRouter weekly token limit was exhausted after run 006. The 403 error ("Key limit exceeded") hit every query in runs 006–007. This was not a logic regression — the agent's reasoning was the same — but once the key was exhausted, the agent returned only the error string for every query, which the validator correctly scored as a failure. Sprint 2 cannot begin any benchmark run until this token access issue is resolved. The options are: obtain a new OpenRouter key, raise the existing key's weekly limit, or switch to direct Anthropic API access (which has per-request pricing rather than a weekly cap).

**Q2: The fixes for queries 2, 5, 7 are already in AGENT.md — why haven't they been validated?**
Because the token budget ran out before any post-fix re-run could be completed. The fix sequence for Sprint 1 was: write probe → diagnose failure → add correction to AGENT.md → re-run harness → observe result. We completed the first three steps for all 15 probes but only completed the fourth step (re-run) for about half of them. The remaining 7 probes have fixes that are logically correct based on observed failure analysis but have not yet been confirmed by a passing harness run.

**Q3: What is the biggest remaining technical risk?**
Query 5 (WiFi state + average rating). The fix requires the agent to follow a precise 3-step algorithm: (1) find all WiFi businesses with their states, (2) identify the top state and filter to only that state's businesses, (3) compute average rating for only those businesses — not globally. In every Sprint 1 run, the agent correctly identified PA as the top state but then computed the average over all WiFi businesses across all states (returning 3.69–3.72 instead of the correct 3.48 for PA only). The CORRECTION 3 algorithm is now fully specified in AGENT.md §8. The risk is that the agent still shortcuts to the global average despite the correction — which would require a tighter prompt engineering fix or a hard-coded Python execution step rather than relying on the LLM to follow the algorithm.

---

## 4. Key Decisions

**Decision 1 — Token access before any benchmark run**
**Chosen:** Resolve OpenRouter key exhaustion before running any evaluation. Do not attempt a benchmark run until at least one test query returns a real answer (not a 403 error).
**Rationale:** Benchmark runs with exhausted keys produce misleading 0/7 scores that pollute the score log and waste time diagnosing apparent regressions that are actually just billing failures. One verification query first.

**Decision 2 — Fix-then-benchmark order**
**Chosen:** Run targeted fix validation for the 7 pending probes (queries 2, 3, 5, 7 specifically) before running the full 5-trial benchmark. Do not start the 5-trial run until the individual fixes have each passed at least once.
**Rationale:** The 5-trial benchmark is the final record for submission. Running it before fixes are validated risks locking in a lower score in the official record. Four days is enough time to validate fixes first, then benchmark.

**Decision 3 — DAB submission scope: Yelp first, then extend**
**Chosen:** Fix and benchmark Yelp first. Once Yelp reaches a stable score (target ≥5/7), extend to additional datasets using the infrastructure already in place. Submit with scores from all datasets that were evaluated.
**Rationale:** The infrastructure for all 12 datasets and 4 DB types is already configured on the server. Yelp has the most complex failure modes (cross-DB joins, unstructured text, serialised attributes) — fixes validated on Yelp make the agent more robust on other datasets too. The order matters: fix the hardest dataset first so corrections transfer forward, not the other way around. A multi-dataset submission is more compelling for the leaderboard and the demo than a single-dataset one, even if scores on newer datasets are low.

---

## 5. Definition of Done

Sprint 2 is complete when all of the following are verifiably true. "I think it works" is not evidence.

1. **Token access restored and verified:** At least one Yelp query runs to completion without a 403 or 402 error. Query 1 answer is 3.55 ± 0.01. Evidence: one harness run with a real answer in the score log.

2. **All 7 pending probe fixes validated:** Each of PROBE-002, 007, 008, 010, 012, 014, 015 has been re-run and the result (PASS or still-failing with new diagnosis) is recorded in `probes/probes.md`. No probe remains in "🔄 Fix added, pending re-run" status.

3. **Score improved from baseline:** The best 5-trial benchmark run achieves a higher pass@1 than the Sprint 1 peak of 42.86% (3/7). Minimum acceptable: 57.14% (4/7). Target: 71.43% (5/7). Evidence: at least 5 runs recorded in `eval/score_log.json` with `run_id` format `2026-04-1X-NNN`, all using `agent_module: agent.data_agent`.

4. **KB v3 corrections log shows agent improvement:** `kb/corrections/corrections-log.md` has at least 5 structured entries — one per core correction — in the documented format. Each entry includes the failed query, what was wrong, the correct approach, and the category. The log demonstrates the agent improved across sessions, not just that fixes were added to AGENT.md.

5. **Adversarial probe library is complete:** All 15 probes in `probes/probes.md` have a final status of ✅ PASS, ⚠️ Partial (documented why it cannot fully pass), or ❌ Known limitation (documented as a Sprint 3 item). No probe is left in "pending re-run" status.

6. **At least one additional dataset benchmarked:** The harness has been run against at least one non-Yelp dataset (e.g. stockmarket, googlelocal, or crmarenapro). Score — even 0% — is recorded in `eval/score_log.json`. If the score is 0%, at least one failure has been diagnosed and documented as a new probe in `probes/probes.md`.

7. **DAB pull request submitted:** A pull request is open against the DataAgentBench public repository containing: the agent module at `agent/data_agent.py`, a reproducible run script, benchmark scores for all evaluated datasets, and a README section describing the approach. PR URL committed to `signal/engagement_log.md`.

8. **Demo video recorded:** A screen recording (minimum 5 minutes) shows the agent answering at least 3 DAB queries live on the EC2 server — including at least one cross-database join query and at least one query from a non-Yelp dataset — with the full query trace visible. Video link committed to `signal/engagement_log.md`.

9. **Published articles:** At least one substantive post — X thread or LinkedIn article — describing the adversarial probe methodology, the score progression from 0/7 to final score, and the multi-dataset architecture is live. Link committed to `signal/engagement_log.md`.

---

## 6. Sprint 2 Task Sequence (April 14–18)

| Day | Priority | Task |
|---|---|---|
| Apr 14 (today) | P0 | Resolve token access — new OpenRouter key or direct Anthropic API. Verify with Yelp query 1. |
| Apr 14 | P0 | Re-run Yelp queries 3, 5, 7 individually to validate AGENT.md fixes. |
| Apr 15 | P1 | If query 5 still fails — tighten the 3-step algorithm prompt or implement as hard-coded Python. |
| Apr 15 | P1 | Backfill kb/corrections log with 5 structured entries from probes. |
| Apr 15 | P1 | Run harness against 1–2 additional datasets (stockmarket, googlelocal, or crmarenapro). Diagnose first failure in each — add to probes.md. |
| Apr 16 | P1 | Run 5-trial full Yelp benchmark (queries 1–7, 5 complete runs). Record in score log. |
| Apr 16 | P1 | Apply any quick fixes surfaced by additional dataset runs. Re-run those datasets once. |
| Apr 16 | P2 | Update probes.md — mark all probes with final status. |
| Apr 17 | P1 | Prepare and submit DAB pull request (all evaluated datasets). |
| Apr 17 | P2 | Record demo video (Yelp + at least one additional dataset). |
| Apr 18 | P2 | Publish X thread / LinkedIn article. Commit all links to engagement log. |
| Apr 18 | P2 | Sprint 2 close mob session — walk through final scores across datasets, probes, and submission. |


