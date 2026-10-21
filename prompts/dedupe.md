# Merge duplicate review findings

Below are findings from several reviewers of one pull request. Merge findings that describe the same defect with the same root cause, so one fix resolves all of them. Keep the clearest scenario and fix, list every place it affects, and join the source names.

Drop nothing else. Do not judge whether a finding is right, important or in scope: a later step does that.

Output every finding, most severe first, numbered from F1, one per line, nothing else:

```
F<n> | <source1,source2> | path:start-end | P0|P1|P2|P3 | category | confidence | <problem as a concrete scenario> | <concrete fix>
```
