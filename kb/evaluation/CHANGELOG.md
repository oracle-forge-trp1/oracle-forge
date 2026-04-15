# Changelog — kb/evaluation

## 2026-04-09
- Initial directory created; evaluation KB scope defined — DAB query format, scoring methodology, harness schema, failure categories

## 2026-04-11
- `evaluation-methodology.md` drafted — covers: (1) harness execution flow (MCP startup, subprocess isolation, query loop, validation, score aggregation), (2) validator architecture with 4 failure categories (forbidden value contamination, proximity validator, silent join failure, silent date drop), (3) pass@1 scoring with strict vs. repaired variants, (4) reproducibility checklist, (5) harness CLI usage, (6) known gaps and limitations
- Document structured as single comprehensive reference covering all 5 required KB evaluation topics (DAB query format, scoring, submission requirements, harness schema, failure categories)

## 2026-04-13
- Document reviewed at Day 5 mob session; confirmed sufficient for injection as agent context
- Failure categories in §2 cross-referenced with probes/probes.md — each probe maps to one of the 4 categories
- Reproducibility checklist (§4) cross-checked against eval/harness.py — all steps confirmed accurate
