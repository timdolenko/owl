# Fix verified review findings

The findings below were raised on this pull request and each was verified as true and worth changing. You work in the PR's checkout, on its branch. Fix them one by one, in the order given.

- Make the smallest change that removes the defect on EVERY path, case and symptom the finding and its `Verified ... Fix:` text name. Implement every part of that fix, not only the first or cheapest one. If you cannot cover a named path or case, fix what you can and report the rest as NOT FIXED with what remains.
- Before committing a fix, find every other writer and reader of the state, flag or value you change (`rg`, not the name alone) and every other path that reaches the same end state (another event, the other side of a stack, an early return, teardown, a cancelled or replaced owner). Cover them or report them as NOT FIXED.
- A new `await`, callback or queued work must recheck, when it resumes, every way its owner can have ended meanwhile (cancel, invalidate, teardown, release, a newer request), not only one of them.
- Follow the repository's `AGENTS.md` / `CLAUDE.md` and the style of the code around it. Change nothing else.
- Keep every acceptance criterion in the PR context working, and every other caller of the code you change.
- After each fix, run the quickest check the repository offers for the touched code (a unit test or a build of that module) when it takes under 10 minutes. If the fix breaks it and you cannot correct it, undo that fix and report it as NOT FIXED.
- Commit each fix on its own: `{prefix}<what changed>`. No co-author lines. Do not push.
- When the code shows that a finding is wrong after all, do not change anything for it: report it as NOT FIXED with the reason.

Reply with one line per finding and nothing else:

```
F<n> | FIXED <commit sha> | <what changed, one sentence>
F<n> | NOT FIXED | <why, with file:line; for a partial fix, what remains>
```
