# Verify one review finding

A reviewer raised the finding below on a pull request. Before anyone sees it, decide whether it is true and worth changing. Most wrong findings fail one of the checks below, so do every check against the real code. Do not trust the finding's own description of the code.

The working directory is the repository at the PR's head commit. The base commit is given below. Read any file and run any read-only command you need: `git show <base>:<path>`, `git log`, `rg`.

## Checks

1. **True?** Open the cited lines and the code around them: callers, other writers of the same state, and the types and APIs involved. Is the claimed behaviour real? Is the scenario reachable (platform, targets, flags, build settings)? In a library, SDK or package, any public entry point called with inputs its API accepts is reachable: "no current host calls it this way" never makes a finding INVALID.
2. **Caused by this PR?** Run the same scenario on the base version. The finding is pre-existing, and INVALID, only when the PR changes neither the order of the steps involved, nor how the code is reached, nor the consequence, and you quote the identical base line (`git show <base>:<path>`). A PR that claims to fix exactly that defect, adds a new way to reach it (a new state, option, flag or entry path), reorders it, widens it or makes its consequence worse owns it. Quote the ticket or description when you call a behaviour intended; never infer intent from what the PR left unchanged.
3. **Allowed by the ticket?** If the PR description, the ticket context, the PR conversation or the codebase notes decided this behaviour on purpose, the finding is INVALID. A description that scopes a change to one entry point does not make a hang, crash or data loss on another entry point intended.
4. **Worth changing?** INVALID when it asks for a test of trivial or private logic, a refactor of code the PR does not change, or a matter of taste with no written repository rule. These are never reasons for INVALID:
   - "No caller does this today", in app code as in a library: code that can be reached through its own API with inputs it accepts is reachable.
   - "Contrived" or "rare" input: repeated text, whitespace, empty strings, emoji, non-Latin scripts, a second account, a double tap, a slow network and an app relaunch are normal.
   - "Only a redundant call" or "only a log line", when you have not ruled out a worse consequence. Judge the worst consequence the scenario can reach, not only the one the reviewer wrote: a stale capture, a reordered await or a second activation can break state, tests or another owner.
5. **The fix is right?** The proposed fix must remove the defect without breaking an acceptance criterion or another caller. When the finding is true but its fix is wrong, it is still VALID: describe the right fix. A wrong or risky proposed fix never makes a true finding INVALID. When the finding offers alternatives, keep only one that fully removes the defect, and check the API behaviour it relies on.

## Answer

Reply in exactly this form, nothing before it:

```
VERDICT: VALID or INVALID
REASON: <one or two sentences with the file:line that proves it>
FIX: <for VALID: the smallest fix that removes the defect on every path the scenario names, concrete; list each path or case the fix must cover>
```

For VALID, when the fix replaces only the finding's commented lines (under 8 lines), add the exact replacement text of those head-side lines, with the original indentation:

````
```suggestion
<replacement lines>
```
````
