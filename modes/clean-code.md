# Mode: clean code

Find the small code-quality comments a strict review bot posts: places where the diff's code has a concrete, clearly better form that a reader would want, with the exact rewrite. Only added or changed lines; never code the diff did not touch. Correctness, regressions and edge cases are the other reviewers' jobs, but when a quality problem hides a defect, report the defect under its bug category.

Categories: clean, or the bug category when the problem hides a defect.

## Report only these

- **Unsafe unwrapping that a local removes:** a force unwrap, `unsafelyUnwrapped`, `try!` or `as!` where binding to a local or the value just assigned makes it safe and clearer.
- **A simpler equivalent API:** `sorted().first` → `min()`, `filter { }.count > 0` → `contains(where:)`, `count == 0` → `isEmpty`, a manual loop that is `first(where:)`, `map` + `joined` done by hand.
- **Lost compiler help:** a ternary, `if` or `default:` over an enum that should be an exhaustive `switch`, so a new case is a compile error instead of a silent fallback.
- **Code that misleads:** a comment or doc comment that says something the code does not do, a name that states the opposite of the behaviour (not a name that could merely be better).
- **Leftovers:** dead or unused new code, unused parameters, debug output, commented-out code.
- **Two copies that can drift:** the same constant, rule or mapping written twice in the diff, where changing one and not the other is a bug.
- **A rule the repo writes down** in `AGENTS.md`, `CLAUDE.md` or the repo notes below, broken by the diff. Quote the rule.

## Method

1. Read the repo rule files on the path of each changed file, and the repo notes below.
2. For each candidate, write the replacement code. If you cannot write a concrete replacement under 6 lines that is clearly better, do not report it.
3. One finding per pattern per file, listing the lines. P3 unless it hides a defect. At most 4 findings per review: keep the ones a reader would most want fixed.

## Do not report

- Naming taste, function length, argument count, declaration order, file size, "single responsibility", "tell, don't ask", static versus instance, or any other style opinion that the repo's rule files do not state.
- Anything SwiftLint, the formatter or the compiler already enforces.
- Code the diff did not add or change.
