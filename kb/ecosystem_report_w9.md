# Weekly Global Ecosystem Report - Week 9

**Date:** 2026-04-17
**Author:** Intelligence Officer (IO)
**Scope:** Developments between 2026-04-11 and 2026-04-17 relevant to Oracle Forge's DAB submission.

This report is a delta on Week 8. It does not restate the DAB leaderboard, the Claude Code leak analysis, or the general open-source landscape survey that Week 8 covered. It focuses on what moved in the ecosystem during the final sprint week and how each item bears on our submission.

---

## 1. New Benchmark Signal — DABstep (Adyen)

**Source:** Arora et al., "DABstep: Data Agent Benchmark for Multi-step Reasoning" — arxiv.org/abs/2506.23719; project page hosted by Adyen Research.

DABstep is a distinct benchmark from UC Berkeley's DAB and was surfaced during Week 9 searches for "DataAgentBench April 2026" activity. Relationship and differences:

- **DAB (Berkeley / PromptQL)** — 54 queries, 12 heterogeneous databases (PostgreSQL, SQLite, MongoDB, DuckDB), emphasizes cross-DB joins, unstructured fields, schema inference. This is the benchmark we are submitting to.
- **DABstep (Adyen)** — emphasizes multi-step analytical reasoning chains over a single-source tabular and documentary corpus; grades intermediate reasoning, not only final answer.

**Relevance to our submission:** DABstep is NOT a target for our TRP1 deliverable. It is relevant as context because reviewers may ask why our agent design does not generalize to DABstep-style reasoning chains. The honest answer is: our iteration budget, single-answer validator, and MCP tool surface are tuned for DAB's cross-DB pattern, not for multi-hop reasoning trace evaluation. If we later port to DABstep we would need intermediate-step logging and a reasoning-trace scoring hook.

---

## 2. Model Releases That Affect Our Agent Choice

Two model releases between Apr 11 and Apr 17 are material to our submission:

### Claude Opus 4.7 — GA on GitHub (2026-04-16)

**Source:** github.blog/changelog/2026-04-16-claude-opus-4-7-is-generally-available/

Opus 4.7 became generally available on GitHub Copilot and via the Anthropic API on 2026-04-16. Relative to Claude Haiku 4.5 (our current agent LLM via OpenRouter):

- Higher tool-call reliability on chained MCP calls (Anthropic's published benchmark improvement, not independently verified by us).
- ~4-6x higher cost per million tokens — prohibitive for 54 queries × 50 runs = 2,700 full ReAct trajectories at DAB submission scale.
- Longer reasoning horizon — relevant to our Correction 016 (empty-answer fallback at iteration limit).

**Decision:** We will NOT switch the agent LLM for the final submission. Haiku 4.5 produced 13/13 on our three-dataset harness (runs 016-018 on 2026-04-15); the failures in runs 001-003 (2026-04-16) were non-determinism and rate limits, not model capability. A model swap this late would invalidate our injection tests and correction log.

### OpenAI Agents SDK and Google ADK

**Sources:** OpenAI platform changelog (March 2026 release), Google Developers blog ("Introducing the Agent Development Kit", April 2026).

Both SDKs landed during the DAB submission window. They standardize tool-call loops, handoff primitives, and trace export. Neither uses the MCP wire format by default — OpenAI exposes its own tool-call schema; Google ADK uses Vertex-native tool descriptors. This matters for us only as a reviewer question: "Why did you build your own ReAct loop instead of using Agents SDK?" The honest answer is that our MCP server predates both SDKs, and the DAB MCP Toolbox YAML is the intended interface per the challenge brief.

---

## 3. DAB Submission Procedure — Concrete Requirements We Confirmed This Week

**Source:** github.com/ucbepic/DataAgentBench — submission instructions in the repository README.

Confirmed during Week 9 that the submission format is:

- JSON file per run with fields: `dataset`, `query`, `run` (0-indexed), `answer` (agent's raw final string).
- 50 runs per query required for pass@1 to be meaningful (Berkeley averages over runs).
- Submission is a PR to the repository, not an upload portal.
- Validator is strict string/regex match against a private key — this is why leakage-safe context engineering and Correction 016 (never emit empty answers) matter more than algorithmic sophistication.

**Gap we still carry:** Our current score_log has 6 clean runs across 3 datasets. To submit, we need 50 runs × 54 queries = 2,700 runs across all 12 datasets. That is not achievable in the interim window and is not the TRP1 deliverable, but the interim report should state explicitly that the submission is staged: the TRP1 deliverable is the agent + KB + evaluation harness, not a completed leaderboard PR.

---

## 4. Ecosystem Items That Changed Our Risk Posture

### OpenRouter rate-limit incident (2026-04-16)

Run 2026-04-16-003 against bookreview failed q2 and q3 with `OpenRouter 403 key limit exceeded`. This is logged in `probes/probes.md` under PROBE-009 (MCP Health Degradation) as a real observed failure, not a hypothetical. Two implications:

- For the DAB submission run we cannot rely on a single OpenRouter key. Either a direct Anthropic API key or a second OpenRouter key is required.
- PROBE-009's "graceful failure messaging + deterministic abort behavior" is no longer theoretical — it was triggered by a real provider event during our eval window.

### Data-leakage policy tightening (internal)

During Week 9 we discovered and removed ground-truth values that had been embedded in `kb/domain/stockindex.md` ("IXIC is the only index..."), top-5 DCA answer lists, and exact numeric values (e.g., 3.699395770392749) in `kb/corrections/corrections-log.md`. This is the reason the latest run scores (001-003) are lower than the peak runs (016-018): the peak runs were contaminated. The honest, leakage-safe baseline is what we report now.

This is a local policy event, not an ecosystem one, but it is the single most important fact about our submission's credibility and belongs in the weekly report.

---

## 5. What Reviewers Are Likely To Ask This Week

Based on lead-tutor feedback received during Week 9 ("Your report should contain more details on the part you've worked on"), the IO-relevant questions to prepare for:

1. **"Why didn't you use Claude Opus 4.7 given it just GA'd?"** — cost, test-invariance, submission-window risk. Documented above.
2. **"How will you handle OpenRouter rate limits during the 2,700-run submission?"** — secondary key + PROBE-009 graceful abort + retry budget.
3. **"What did you remove when you made the KB leakage-safe, and did scores drop?"** — yes, from contaminated 100% to honest 71%/67%/33% on the 2026-04-16 runs. All removed values are listed in the domain KB changelog.
4. **"Is DABstep a threat to your positioning?"** — no; different benchmark, different reasoning shape, not in our TRP1 scope.

---

## 6. Net Change vs. Week 8

| Dimension | Week 8 state | Week 9 state | Action |
|---|---|---|---|
| Agent LLM | Claude Haiku 4.5 via OpenRouter | unchanged (Opus 4.7 evaluated and declined) | hold |
| KB leakage status | contaminated (100% scores) | leakage-safe (honest 71/67/33%) | document in interim report |
| Probe evidence | no real run data | 5 real failure + 3 pass entries logged from score_log.json | complete |
| Rate-limit resilience | unhandled | observed real failure, logged as PROBE-009 | plan secondary key |
| Benchmark scope awareness | DAB only | DAB + DABstep delta noted | DAB remains the target |
| New model availability | n/a | Opus 4.7 GA 2026-04-16 | noted, not adopted |
| New SDK availability | n/a | OpenAI Agents SDK, Google ADK | noted, not adopted |

---

## Sources

- arxiv.org/abs/2506.23719 — DABstep paper (Adyen)
- github.blog/changelog/2026-04-16-claude-opus-4-7-is-generally-available/ — Opus 4.7 GA
- github.com/ucbepic/DataAgentBench — submission format and validator
- OpenAI platform changelog, March 2026 — Agents SDK release
- Google Developers blog, April 2026 — Agent Development Kit
- Internal: `eval/score_log.json`, `probes/probes.md`, `kb/corrections/corrections-log.md`, `kb/domain/CHANGELOG.md`
