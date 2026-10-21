---
name: reptile
description: Reptile, a deep Greptile-style code review of a pull request or branch diff. Builds a repository graph and context packs per changed declaration (Swift), adds codebase wiki pages and team rules mined from past PR review threads, runs parallel read-only reviewers (per file, whole PR, clean-code, regressions) through Claude Code or Codex CLI, merges duplicates, and can post the result as one GitHub review and answer each comment after fixing. Use before requesting human or bot review of a PR or branch, when asked for a deep or thorough review, or as the review step of a pipeline. Costs about $5-7 per PR with Claude Opus; takes 5-20 minutes.
---

# reptile (Reptile)

Reptile reviews a diff the way Greptile does, then posts the result to the PR. It never changes code itself. You (the agent) fix the findings afterwards.

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
- Author: findings with confidence >= 0.5 become inline comments; the rest are one "Low confidence" list in the review summary (in benchmarks most of them were declined), and the PR description gets a Reptile block with the SAFE and unsure items.
- Reviewer (someone else's PR): only P0-P2 with confidence >= 0.75 inline. Nothing else is posted: no description edit, no notes block; the rest stays in the run directory.
- All comments go out as one review. `<run dir>/posted.json` maps each finding id (`F3`) to its comment id. A second post of the same run is refused unless `--force`.

## 3. Fix and reply (when you are the author or the fixer)

For each comment in `posted.json`, in severity order:

1. Verify the finding against the code. Read the cited lines and the scenario. A finding is a claim, not a fact.
2. If it is real, make the smallest fix that removes it. Never change product behavior, copy, scope or an acceptance criterion to resolve a finding; if only a product decision can fix it, decline and say so.
3. If it is wrong, already handled, or out of scope, decline it with a one-sentence reason that cites `file:line`.
4. Commit the fixes, then reply on each comment:

```bash
"$SKILL_DIR/scripts/reptile.py" reply --pr <number> --comment <id> --status fixed --text "<what changed>" --resolve
"$SKILL_DIR/scripts/reptile.py" reply --pr <number> --comment <id> --status declined --text "<reason, file:line>"
```

`--sha` defaults to `HEAD`. Resolve only the threads you fixed. Then push.

Also look at the findings that were not posted (the unsure list in the Reptile block) and the `NOT CONFIRMED` lines: fix the real ones the same way, and run the manual steps you can run.

## Setup

`install.sh` (in the repository of this skill) creates the venv with `tree-sitter` and `tree-sitter-swift`. The scripts need `git`, `gh` (logged in) for `--pr`, `post`, `reply` and `memory`, and `claude` or `codex` on `PATH`. Optional, once per repository and then daily: `reptile.py memory --since <YYYY-MM-DD>` (team rules from past PR review threads) and `reptile.py refresh`.
