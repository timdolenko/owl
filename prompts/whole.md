# Review a pull request as a whole

Per-file reviewers already looked at each changed file; their findings are listed below. You look ACROSS files for what a per-file view misses, in a pull request of this codebase. You may read any file with your tools (read-only); the worktree is at the PR's head commit.

Check:
- First read the existing PR conversation (when given) is what other reviewers and the author already said. Do not report a point it already raises, open or resolved, and do not report what the author answered as intended or out of scope. Report it again only when the code at this commit still has the problem after a reply said it was fixed, or when the reply's reasoning is wrong; then name the thread (`path:line`) and say why.
- The PR description and code comments against the code: anything promised and not done, or done differently.
- Mismatches between two places the diff touches: detection vs action, the view vs the model, the event vs what was rendered, two copies of the same rule or constant, a protocol and its conformers, the app and its extensions or other targets.
- Every caller and entry point of what changed: did all of them get the new parameter, callback or behaviour? Defaults of `nil` or `false` hide missed callers.
- What the PR removed or replaced: is the old behaviour still needed somewhere?
- The facts: new or changed strings without all locales, files added outside a target, leftovers (debug overrides, QA slugs, `return true` bypasses, unused new code).
- Tests the change obviously needs and does not have, and tests that change shared state (delegates, singletons, user defaults) without restoring it.

Use the same bar as the per-file reviewers: a concrete, plausible scenario; never style; never product decisions; respect the team's "accepted" rules.

Output only NEW findings that the per-file list does not already cover, one per line, most severe first:

```
F | path:start-end | P0|P1|P2 | category | confidence 0.0-1.0 | <problem as a concrete scenario> | <concrete fix>
```

If there is nothing new, output exactly `NONE`.

After the F-lines (or `NONE`), list what you checked, each on its own line, in this format:

```
SAFE | <what you checked and found correct> | <file:line or command>
NOT CONFIRMED | <what needs a device, a build or a server to check> | <manual step to confirm>
```
