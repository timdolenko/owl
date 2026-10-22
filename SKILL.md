---
name: reptile
description: Reptile, a deep Greptile-style code review of a pull request or branch diff. Builds a repository graph and context packs per changed declaration (Swift), adds codebase wiki pages and team rules mined from past PR review threads, runs parallel read-only reviewers (per file, whole PR, clean-code, regressions) through Claude Code or Codex CLI, merges duplicates, verifies every finding with its own agent, then fixes and pushes the valid ones on your own PR or posts them with suggestions on someone else's. Use before requesting human or bot review of a PR or branch, when asked for a deep or thorough review, or as the review step of a pipeline. Costs about $5-7 per PR with Claude Opus; takes 5-20 minutes.
---

# reptile (Reptile)

Reptile reviews a diff the way Greptile does. Before anything goes to the PR, one verifier agent per finding checks it against the PR's code and decides if it is true and worth changing. On your own PR Reptile then fixes the valid findings itself; on someone else's PR it posts them.

`SKILL_DIR` below is the directory that holds this file. Run every command from inside the repository under review.

## 1. Review

Commit first. Reptile reviews commits, not uncommitted changes.

```bash
"$SKILL_DIR/scripts/reptile.py" review --pr <number>    # an open GitHub PR: title, body and base come from gh
"$SKILL_DIR/scripts/reptile.py" review                  # the current branch against origin's default branch
"$SKILL_DIR/scripts/reptile.py" review --base origin/develop --head HEAD
```

Useful options: `--engine codex` (or `REPTILE_ENGINE=codex`), `--out <dir>`, `--modes clean-code,regressions` (the default), `--no-wiki`, `--no-memory`, `--dry-run` (writes every prompt and calls no model). Run it in the background or with a long timeout: it takes 5-20 minutes. The last lines it prints are `FINDINGS=<n>` and the path of `findings.md`.

The run directory (default `<repo>/.reptile/<head-sha>/`) holds:

- `findings.md`: one line per finding, most severe first:
  `F<n> | sources | path:start-end | P0-P3 | category | confidence | problem | fix`.
  P0 and P1 block a merge, P2 should be fixed, P3 is a nit. `sources` names the reviewers that raised it.
- `passed.md`: `SAFE | ...` (checked and correct), `NOT CONFIRMED | ... | manual step`, `out-of-scope | ...`.
- `findings.raw.md` (every candidate before the merge), `steps.json`, `meta.json` (cost, counts), and every model call's `.prompt` and `.txt`.

A rerun on the same head commit reuses the answers already in the run directory. Delete the directory to review again from the start.

## 2. Post

```bash
"$SKILL_DIR/scripts/reptile.py" post --out <run dir> --pr <number>              # --role auto
"$SKILL_DIR/scripts/reptile.py" post --out <run dir> --pr <number> --dry-run    # preview, no GitHub writes
```

- `--role auto` is `author` when the gh user opened the PR, else `reviewer`.
- First, one verifier per finding (6 in parallel, on a detached checkout of the PR head) answers VALID or INVALID with a reason. Pre-existing issues, behaviour the ticket decided, unreachable cases, tests of trivial code and taste with no written rule are INVALID. `<run dir>/verdicts.json` keeps every verdict.
- Author (your own PR): one fixer agent fixes the valid findings in `--repo`, commits each fix (`[TICKET-n] ` prefix from the PR title) and pushes. Nothing is posted as a comment. The PR description gets a folded Reptile block: fixed, checked and not changed (with the reason), unsure. `posted.json` holds `fixed` and `declined`.
- Reviewer (someone else's PR): only valid P0-P2 findings are posted inline, with the verifier's suggestion when the fix is small. With no such finding, Reptile approves the PR as the gh user, but only when the PR head is still the reviewed commit. Nothing else is posted.
- A second post of the same run is refused unless `--force`.

## 3. After the post (author)

Read `posted.json` and Reptile's commits (`git log`). Build, run the tests for the touched code, and recheck the behaviour near the fixes. Never reply "not changed" on the PR: the reasons are already in the description block. Fix the `NOT CONFIRMED` lines in `passed.md` that are real, and run the manual steps you can run.

`reply` stays for comments Reptile posted as reviewer, or for human comments:

```bash
"$SKILL_DIR/scripts/reptile.py" reply --pr <number> --comment <id> --status fixed --text "<what changed>" --resolve
```

## Setup

`install.sh` (in the repository of this skill) creates the venv with `tree-sitter` and `tree-sitter-swift`. The scripts need `git`, `gh` (logged in) for `--pr`, `post`, `reply` and `memory`, and `claude` or `codex` on `PATH`. Optional, once per repository and then daily: `reptile.py memory --since <YYYY-MM-DD>` (team rules from past PR review threads) and `reptile.py refresh`.
