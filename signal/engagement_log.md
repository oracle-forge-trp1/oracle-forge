# Engagement Log — Oracle Forge Signal Corps

## Week 8 (April 9–13, 2026)

### April 9, 2026 — Infrastructure & Community Setup
- Set up Signal Corps infrastructure (GitHub, Cloudflare Workers free tier registered)
- Identified key X accounts to follow: @adityagp, @UCBEPIC, @tanmaigo, @rakyll
- Subscribed to DataAgentBench repository (All Activity notifications)
- Joined @oracle-forge-trp1 GitHub organization
- Joined r/MachineLearning and r/LocalLLaMA communities

**Daily Slack post:** Infrastructure day — EC2 server being set up, Yelp data loading, KB architecture docs started

### April 10, 2026 — First Community Engagement
- **X reply** to @karpathy post on LLM Knowledge Bases — applied the method to data agent context engineering
  Link: https://x.com/hibet_zemzem/status/2043623058984825082?s=20
  Topic: How Karpathy's "minimum content, maximum precision" KB method directly applies to the agent's AGENT.md context injection pattern

**Daily Slack post:** KB architecture docs merged; agent started on EC2; first external engagement on Karpathy thread

### April 11, 2026 — Substantive Reddit Engagement (x2)
- **Reddit comment** — r/MachineLearning — "Gary Marcus on the Claude Code leak [D]"
  Link: https://www.reddit.com/r/MachineLearning/comments/1sjb0qi/comment/ofwstt5/?utm_source=share&utm_medium=web3x&utm_name=web3xcss&utm_term=1&utm_content=share_button
  Content: Responded with specific technical observations from our study of the Claude Code architecture — three-layer memory pattern and tool scoping philosophy

- **Reddit comment** — r/LocalLLaMA — "DataAgentBench: frontier models score 38% on multi-DB queries"
  Link: https://www.reddit.com/r/LocalLLaMA/comments/1sjh8fr/comment/ofwwi8n/?utm_source=share&utm_medium=web3x&utm_name=web3xcss&utm_term=1&utm_content=share_button
  Content: Shared our team's observation about the ill-formatted join key problem — the 38% ceiling is partly a context engineering problem, not just a model capability problem. Committed to reporting back with our DAB results.

**Daily Slack post:** Agent hit 3/7 on Yelp (first passing run). Two Reddit comments live. Domain KB (6 docs) complete and injection-tested.

### April 12, 2026 — Evaluation Run & Probe Writing
- Internal: Ran all 7 Yelp queries; sprint peak 3/7 (42.86%). Probes library started.

**Daily Slack post:** Score peak 3/7. Adversarial probe library being written from failure analysis. 5 AGENT.md corrections in place.

### April 13, 2026 — First Standalone X Thread + Token Exhaustion
- **X Thread (standalone)** — Week 8 build update + DAB benchmark intro
  Link: https://x.com/hibet_zemzem/status/2043679905771053431?s=20
  Topic: Building a multi-database data agent against DAB, what cross-DB joins actually look like in practice, why 38% is the ceiling for frontier models without context engineering
  Impressions: [check X analytics]

- Internal: OpenRouter token limit exhausted mid-run (402/403 errors). Runs 006-007 scored 0/7 due to billing failure, not logic regression. Sprint 1 closed.

**Daily Slack post:** Week 8 X thread live. Token exhaustion hit. Sprint 1 peak 3/7 confirmed. 15 adversarial probes documented. Sprint 2 starts April 14.

---

## Sprint 2 Publication Plan (April 14–18, 2026)

### Planned Posts
- [ ] **X thread — adversarial probing methodology:** What we learned from writing 15 failure cases against our own agent. How each probe category (join keys, unstructured text, domain knowledge, multi-DB routing) maps to a specific AGENT.md correction. Benchmark before/after comparison.
- [ ] **Follow-up comment on r/LocalLLaMA DAB thread:** Report back with our actual scores as committed on April 11.
- [ ] **X post — DAB PR submission:** Announce benchmark submission with score, architecture summary, PR link.
- [ ] **LinkedIn/Medium article (Zemzem):** "What writing 15 adversarial probes taught us about context engineering" — minimum 600 words, specific failure modes, score progression from 0/7 to final score.

---

## Resource Acquisition Summary

| Resource | Status | Details |
|----------|--------|---------|
| Cloudflare Workers free tier | ✅ Account created | 100K requests/day; no developer credits available |
| OpenRouter API | ⚠️ Token limit exhausted (Week 8) | Weekly limit hit after run 005; Sprint 2 needs new key or direct Anthropic API |
| GitHub organization | ✅ Active | oracle-forge-trp1; all team members added |
| DataAgentBench repository | ✅ Watching | All activity notifications active; PR submission target for April 17–18 |
