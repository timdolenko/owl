# Fix verified review findings

The findings below were raised on this pull request and each was verified as true and worth changing. You work in the PR's checkout, on its branch. Fix them one by one, in the order given.

- Make the smallest change that removes the defect. Follow the repository's `AGENTS.md` / `CLAUDE.md` and the style of the code around it. Change nothing else.
- Keep every acceptance criterion in the PR context working, and every other caller of the code you change.
- After each fix, run the quickest check the repository offers for the touched code (a unit test or a build of that module) when it takes under 10 minutes. If the fix breaks it and you cannot correct it, undo that fix and report it as NOT FIXED.
- Commit each fix on its own: `{prefix}<what changed>`. No co-author lines. Do not push.
- When the code shows that a finding is wrong after all, do not change anything for it: report it as NOT FIXED with the reason.

Reply with one line per finding and nothing else:

```
F<n> | FIXED <commit sha> | <what changed, one sentence>
F<n> | NOT FIXED | <why, with file:line>
```
