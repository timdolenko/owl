# Verify one review finding

A reviewer raised the finding below on a pull request. Before anyone sees it, decide whether it is true and worth changing. Most wrong findings fail one of the checks below, so do every check against the real code. Do not trust the finding's own description of the code.

The working directory is the repository at the PR's head commit. The base commit is given below. Read any file and run any read-only command you need: `git show <base>:<path>`, `git log`, `rg`.

## Checks

1. **True?** Open the cited lines and the code around them: callers, other writers of the same state, and the types and APIs involved. Is the claimed behaviour real? Is the scenario reachable in this app (platform, targets, flags, build settings)?
2. **Caused by this PR?** Run the same scenario on the base version. If the base behaves the same way, the finding is pre-existing: INVALID, unless this PR claims to fix exactly that.
3. **Allowed by the ticket?** If the PR description, the ticket context, the PR conversation or the codebase notes decided this behaviour on purpose, the finding is INVALID.
4. **Worth changing?** INVALID when it asks for a test of trivial or private logic, a refactor of code the PR does not change, or a matter of taste with no written repository rule.
5. **The fix is right?** The proposed fix must remove the defect without breaking an acceptance criterion or another caller. When the finding is true but its fix is wrong, it is still VALID: describe the right fix. When the finding offers alternatives, keep only one that fully removes the defect, and check the API behaviour it relies on.

## Answer

Reply in exactly this form, nothing before it:

```
VERDICT: VALID or INVALID
REASON: <one or two sentences with the file:line that proves it>
FIX: <for VALID: the smallest correct fix, concrete>
```

For VALID, when the fix replaces only the finding's commented lines (under 8 lines), add the exact replacement text of those head-side lines, with the original indentation:

````
```suggestion
<replacement lines>
```
````
