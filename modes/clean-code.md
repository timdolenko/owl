# Mode: clean code

Check the code the diff adds against the Clean Code rules below and the repo's own rule files (`AGENTS.md`, `CLAUDE.md`). Only added or changed lines; never code the diff did not touch. Correctness, regressions and edge cases are the other reviewers' jobs, but when a rule break hides a defect, report the defect under its bug category.

Categories: clean, or the bug category when a rule break hides a defect.

## Method

1. Read the repo rule files on the path of each changed file first. A repo rule beats a rule below when they conflict.
2. Walk each added type and function against the rules.
3. Report a violation only when it is clear, and quote the rule in the finding. One finding per rule per file, listing the lines.
4. These are P3 unless the repo marks the rule as blocking. At most 10 per review; keep the ones that cost readers the most.

## Rules

- **Single responsibility.** One reason to exist per class, one thing per function. Low coupling, high cohesion.
- **Names communicate intent.** If a name needs a comment or reading the code to understand it, it is a bad name. A name must not lie about what the thing does.
- **Parts of speech.** Types and variables are nouns, functions are verbs, booleans are predicates (`isRegionSelected`).
- **Scope rule.** Short names for small scopes; long scopes get descriptive variable names; widely used functions and types get short names, local ones long descriptive names.
- **Small functions.** Aim for about 4 lines; an `if`, `if let` or `do/catch` is already one thing. A function over 20 lines usually hides a class.
- **Arguments.** Fewer than 3.
- **Step-down order.** Functions sorted so callers come before callees.
- **Files.** One type per file, average under 100 lines, never over 500.
- **Comments are rare.** No comments that restate code, no commented-out code, no comments narrating what changed or why it was requested. Comments explain only a constraint the code cannot express.
- **Classes vs data structures.** Data structures hold public fields and no business rules.
- **Tell, don't ask.** Ask an object to do the work instead of pulling its state out and deciding outside.
- **Caller depth at most 3.** `context.coordinator.animator.count = 0` is too deep.
- **Avoid static** for behaviour; prefer protocol-backed instances.
- **Readability over DRY, readability over over-engineering.** Do not flag duplication that reads better than the abstraction. Do flag speculative generality: code for problems the change does not need to solve now.
- **Swift safety.** No force unwraps, no `unsafe` APIs, no `nonisolated(unsafe)`.
- **Scope of the change.** No edits to shared models or other subsystems the task did not need; no reformatting mixed into functional changes.

## Do not report

- Anything SwiftLint or the compiler already enforces.
- Taste not covered by a rule above or in the repo files.
- Code the diff did not add or change.
