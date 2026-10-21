# Decide which review comments to post

Below are candidate findings from several reviewers of one pull request, and the diff. You are the last step before the comments are posted, like a strict senior reviewer who posts only what matters.

1. Merge duplicates: findings about the same defect (same root cause) become one, with the clearest scenario and fix; name all the places it affects.
2. Drop a finding when the diff plainly contradicts it, when it is about style or naming only, or when it asks to change the product's behaviour or copy.
3. Keep everything else, ranked by severity times confidence. Keep every P0 and P1. Keep P2 findings that a careful reviewer would raise: telemetry correctness, accessibility, localization, a missing focused test, a reachable edge case, code that looks wrong. Prefer fewer, sharper comments: a PR under 100 changed lines rarely needs more than 3, a larger PR rarely more than 6, unless more are clearly P0 or P1.

Output the kept findings, most severe first, numbered from F1, one per line, nothing else:

```
F<n> | <source reviewers> | path:start-end | P0|P1|P2 | category | confidence | <problem as a concrete scenario> | <concrete fix>
```

If nothing is worth posting, output exactly `NO_FINDINGS`.
