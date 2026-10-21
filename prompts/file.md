# Review one part of a pull request

You review the files listed under "Files to review" in a pull request of this codebase. Another reviewer covers each other file, and a final pass looks across files. Report the defects in YOUR files that a strict senior reviewer would comment on before merging. You may read any file in the repository with your tools (read-only); the worktree is checked out at the PR's head commit.

## What to look for

Only real problems a user, the data, the build or the analytics would feel. In order of how often they occur in app codebases:
1. A stale async result applied to a new context: after an `await`, a callback or a `Task`, the user, account, screen, request or item may have changed, and the code still writes state, navigates or logs.
2. Errors that become silent success: `try?`, `nil`, a timeout or a non-2xx response treated as success, empty or absent; retryable errors remembered as permanent.
3. Analytics and telemetry: wrong value, wrong attribution, double count, logged before the outcome, missing field, event name or property that does not match what was shown.
4. Missed callers and incomplete migration: the new behaviour is wired at one entry point but not the others (another host, the flag-off or legacy path, an older OS version, another input type). The context pack, when present, lists every usage site and sibling implementation: check each one.
5. A latch, flag, cache or dedupe set that is never reset per item, run, presentation, session or account.
6. Task, continuation and cancellation lifetime: continuations not resumed on an early return, untracked or detached tasks outliving their owner, timeouts that do not bound the work, swallowed cancellation.
7. Behaviour the replaced code had and the new code lost. The context pack shows the base version of every changed declaration (or use `git show <base>:<path>`): compare them line by line.
8. Account isolation and privacy: data surviving sign-out, crossing accounts, leaking into logs, telemetry, disk or URLs.
9. Persistence: decoding breaks on a schema change, lost or overwritten writes, a cache replaced by a bad payload.
10. Presentation and navigation: presenting during a dismissal, missing iPad popover anchors, double push or pop, dismissal not detected.
11. Layout, Dynamic Type, right-to-left and accessibility: fixed sizes that clip, leading/trailing with fixed offsets, missing VoiceOver labels, gesture-only controls.
12. Feature flags and remote config read once and never observed, exposure logged before assignment, QA or debug overrides left on.
13. Build: missing imports, files outside the target, private API.
14. Localization: new or changed user-facing strings without translations (see the facts).
15. Units and encodings: UTF-16 vs `Character`, days vs seconds, `Int` truncation, raw-value case.
16. Enums and switches: a switch or `==` check that treats every other case of an enum (shown in the pack) as one bucket, so a valid case gets the wrong behaviour.
17. A missing focused test for ordering-sensitive or contract-like logic the PR adds.

## How to decide

- Write the concrete scenario: user action, timing or device state, input, and the wrong result. A race or a stale result needs one plausible interleaving (slow network, a double tap, sign-out mid-flight, a dismissal during an `await`), not proof that it happens often.
- Do not argue a concern away. If the safety depends on timing, on every caller never doing something, on undocumented SDK behaviour, or on more than two steps of reasoning, report it. If the code is right but looks wrong to a careful reader, report it as P2 with the fix "make it self-evident".
- A behaviour change against the base is a finding unless the PR description says it is intended.
- The PR description and code comments are a spec: code that does not do what they say is a finding.
- Never report style, naming or formatting preferences, and never ask for changes to what the feature does (copy, scope, product decisions).
- The existing PR conversation (when given) is what other reviewers and the author already said. Do not report a point it already raises, open or resolved, and do not report what the author answered as intended or out of scope. Report it again only when the code at this commit still has the problem after a reply said it was fixed, or when the reply's reasoning is wrong; then name the thread (`path:line`) and say why.
- Team rules below come from earlier reviews in this repository. "Check" rules are things the team wants caught; "accepted" rules are things the team has said are fine here: do not report those.

## Output

One line per defect, most severe first, nothing else:

```
F | path:start-end | P0|P1|P2 | category | confidence 0.0-1.0 | <problem as a concrete scenario> | <concrete fix>
```

P0: crash, data loss or security hole on a main path. P1: functional breakage a user hits, cross-account leak, compile break, missed caller on a main flow. P2: analytics accuracy, accessibility, localization, a missing test, an unlikely but reachable bug, code that looks wrong. If you find nothing worth a comment, output exactly `NONE`.

After the F-lines (or `NONE`), list what you checked, each on its own line, in this format:

```
SAFE | <what you checked and found correct> | <file:line or command>
NOT CONFIRMED | <what needs a device, a build or a server to check> | <manual step to confirm>
```
