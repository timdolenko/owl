# Mode: fix-delta

Earlier review rounds on this pull request fixed findings with their own commits, and some commits answer other reviewers. Defects in those fix commits are the ones this review misses most: a later reviewer finds them in lines the fixer wrote. Review every fix, not the feature.

Categories: incomplete-fix, fix-regression, lifecycle, race, state, test.

## Inputs

- **Earlier rounds** (below, when given): each finding an earlier round fixed, with the verifier's fix and the commit; the findings verified but left unfixed; the findings the verifiers rejected.
- **Fix commits:** `git log --format='%h %s' <base>..HEAD`. Treat every commit whose message fixes, guards, keeps, drops, reports or covers something as a fix, including commits from responders to other reviewers. Read each with `git show <sha>`.

## Method

For each fix:

1. **Complete?** List every path, case and symptom the original finding and the verifier's fix named. Does the commit cover each one? The same end state is often reached another way: the other event (`removed` vs `belowRemoved`, cancel vs invalidate), the other side (the owner above vs below), another caller or host, a retry. A fix that handles one of them and not the others is a finding.
2. **Who else touches it?** For every flag, field, latch, captured value or stack entry the fix adds or changes, `rg` every writer and reader (by the storage, not the name). Can another writer set it at the wrong time, or a reader see it stale?
3. **New awaits and queued work.** For every `await`, callback, `Task` or queued closure the fix adds: when it resumes, does it recheck every way its owner can have ended or changed meanwhile (cancel, invalidate, teardown, release, a newer request, a reordered stack, changed preferences)? A value captured before the hop and re-read after it is a race.
4. **What did the fix change for everyone else?** A fix that reorders work, moves an owner, re-activates, retries or adds a log line at `.error` can break other owners, callers or tests. Name the ones you checked.
5. **Its test.** Would the test the fix added fail with the fix reverted? Does it exercise the configuration the name says?
6. **Still open.** Each finding listed as verified but not fixed: is it still there at this commit? Report it again, with the full fix, so this round fixes it.
7. **Rejected more than once.** A concern the verifiers rejected in an earlier round that you can still show a concrete scenario for: report it with the scenario, and say which round rejected it and why that reason is wrong.

Report findings in the format of the shared rules. Name the fix commit in the problem text (`fix <sha>:`).
