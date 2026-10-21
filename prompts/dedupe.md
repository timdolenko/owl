# Merge duplicate review findings

Below are findings from several reviewers of one pull request. Merge findings that describe the same defect with the same root cause, so one fix resolves all of them. Keep the clearest scenario and fix, list every place it affects, and join the source names.

Also merge:
- all findings that ask for missing or better tests into one test finding that lists each case to cover, with the highest severity among them;
- a P3 finding on lines a P0-P2 finding already covers with the same fix, into that finding;
- findings that are the same problem in sibling places (two adapters, two views, two copies of a rule) into one that names every place.

Drop a finding that repeats a point the existing PR conversation below already raises (open or resolved) or that the author answered there, unless the finding says why that answer is wrong or the code still has the problem.

Drop nothing else. Do not judge whether a finding is right, important or in scope: a later step does that.

Output every finding, most severe first, numbered from F1, one per line, nothing else:

```
F<n> | <source1,source2> | path:start-end | P0|P1|P2|P3 | category | confidence | <problem as a concrete scenario> | <concrete fix>
```
