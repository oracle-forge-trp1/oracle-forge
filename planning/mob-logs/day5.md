# Mob Session — Day 5 (April 12–13, 2026)
**Attendees:** Birkity Yishak, Beamlak A, Atnabon Deressa, Yonas Eshete, Zemzem Hibet
**Duration:** ~50 min

## IO Update
Atnabon updated all CHANGELOGs and documented injection test evidence for all KB architecture documents. Yonas finalized the domain KB and began writing the adversarial probe library from the accumulated failure observations.

## Signal Corps Update
Zemzem compiled the engagement log with all published links and posts to date; submitted to `signal/engagement_log.md`.

## Driver Update
Birkity ran the final score pass across all datasets, wrote the Sprint 1 operations document, updated `README.md`, and verified the full repo structure for interim submission packaging. Score peak on Yelp was 3/7 (42.86%) in runs 003–004; run 006 hit the OpenRouter weekly token limit mid-run (402 error), and run 007 returned all errors (403). Sprint ended with 15 adversarial probes written, 5 corrections documented, 7 pending re-runs blocked by token exhaustion. Beamlak finalized eval README and score log; results JSON build in progress.

## Decisions Made
- Sprint 1 closes with Yelp score of 3/7. Token exhaustion was the binding constraint on all remaining fix validations — not logic failures.
- The 7 pending probe re-runs carry forward to Sprint 2 as the first P0 task once token access is restored.

## Gate Approvals
- Sprint 2 Inception document to be reviewed and approved at the first Sprint 2 mob session (April 14).

## Hardest Question
- Asked by: Yonas Eshete
- Question: The score dropped from 3/7 to 0/7 in the last two runs. How do we know the AGENT.md fixes are actually correct and we didn't introduce a regression?
- Answer: Runs 006–007 failed entirely due to OpenRouter 402/403 errors — the agent never executed any reasoning. The logic was not tested. The only confirmed regression is in run 005 (query 3 dropped from 35 to 23 due to `ast.literal_eval` being applied to the wrong object), and that fix is already documented and in AGENT.md. All other pending probes are "fix added, not yet re-run" — not confirmed regressions. Sprint 2's first task is a clean re-run with working token access to separate logic failures from billing failures.

## Tomorrow's Focus
- Birkity: Restore token access (new OpenRouter key or direct Anthropic API). Re-run Yelp queries 3, 5, 7 to validate fixes. Approve Sprint 2 Inception.
- Beamlak: Complete results JSON, begin multi-dataset 5-trial benchmark setup.
- Atnabon: Backfill kb/corrections log with structured entries for all 5 core corrections.
- Yonas: Complete adversarial probe library write-up; mark all 15 probes with post-fix status.
- Zemzem: Plan Sprint 2 publication schedule — at least one substantive post on adversarial probing methodology.
