# Code review: challenge what the reviewers passed

The reviewers' merged result is below: findings (`F<n>` lines) and the points they checked and passed (`SAFE`), could not settle (`NOT CONFIRMED`) or set aside as `out-of-scope`. A strict outside reviewer will read the same diff next and comment on anything that looks like it can fail. Your job is to catch what it would catch and the reviewers let through.

## Method

1. Read the pull request, the earlier rounds (when given) and the diff below. The worktree is at the PR's head commit; read any file you need, and `git show <base>:<path>` for the base.
2. For each `SAFE`, `NOT CONFIRMED` and `out-of-scope` line that names a concrete way the code could fail (a race or late result, an error or early-return path, another variant of the same input, another caller or adapter, a value that differs between two places), open the code once more and decide whether a skeptical reviewer who reads only the diff and the code around it would still post it.
3. Promote it to a finding when any of these hold:
   - the argument for safety depends on timing, on the order two tasks finish, or on undocumented behaviour of an external API or SDK;
   - it depends on every caller never doing something, and nothing in the code enforces it;
   - it takes more than two steps of reasoning, or a comment, to see why it is safe;
   - the same problem was found as a defect in a sibling (one adapter, platform, host or branch fixed, the other not);
   - the PR description or a code comment promises something the code does not do;
   - it calls a behaviour change "intended" or "out of scope" although neither the PR description nor the ticket says so (a wider or narrower condition, an attribution, a default, a removed path);
   - it says two async operations cannot overlap or race, and no explicit guard in the code (a generation or request id, a cancellation check, a single-flight flag, a serial queue) makes that so;
   - it assumes the author or product owner meant this behaviour, without quoting the ticket, the description or a code comment that says so;
   - it is about code an earlier review round's fix wrote (see the earlier rounds and `git log`): fixes are where later reviewers find most defects;
   - it is `NOT CONFIRMED` because it "needs a device", although the code shows a reachable sequence of events (a second dictation, a relaunch, a call, a route change, a slow response) that leads to the wrong state: the code decides it, not a device.
4. Keep it passed only when the code makes the safety obvious at the line itself.
5. Then read the diff once more for anything nobody mentioned in the categories that most often slip through: a missed caller of a changed API, behaviour the replaced code had and the new code lost, a latch or flag never reset, a state write after an `await` without an identity check, an error treated as absence or success, an event logged before the outcome. Also ordering-sensitive or contract-like logic (a state machine, a dismissal cascade, a wire format, callback order) that the diff adds with no focused test: that is a P2 finding naming the regression a test would catch.

## Output

First, one line for every numbered passed line (`P<n>`) in the input, in order, none skipped:

```
P<n> | KEEP | <why the code makes it obviously safe, with file:line>
P<n> | PROMOTE | F<m>
```

Then the new finding lines, numbered after the last existing `F<n>`, most severe first:

```
F<n> | challenge | path:start-end | P1 or P2 | <category> | <confidence> | <problem as a concrete scenario> | <concrete fix, or "make it self-evident: ..." when the code is right but looks wrong>
```

If there is nothing to promote or add, the `P<n>` lines are followed by exactly `NONE`.
