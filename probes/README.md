# probes/

Adversarial **probe library** (`probes.md`): failure mechanisms for multi-DB agents.

- Mechanism-focused definitions (strict **no benchmark query text / no ground-truth answers** in-repo).
- A **rubric five-field log** section maps probes to: scenario paraphrase, failure category, expected failure, observed pattern, fix + score note — without leaking DAB strings.

Update `probes.md` when a new failure class is discovered; run leakage lint if you add narrative that might quote validators.
