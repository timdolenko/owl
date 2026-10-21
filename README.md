# deep-pr-review (Reptile)

A Greptile-style pull request reviewer packaged as an agent skill for Claude Code and Codex CLI. It reviews a PR or branch diff with several parallel read-only model reviewers, posts the result as one GitHub review by "Reptile", and gives the fixing agent a command to answer each comment.

## Install

```bash
git clone <this repository> deep-pr-review && cd deep-pr-review
./install.sh            # symlinks into ~/.claude/skills and ~/.codex/skills, creates the venv
./install.sh --claude   # or only one of them; --copy copies instead of linking
```

The venv lives at `${DEEP_REVIEW_HOME:-~/.cache/deep-pr-review}/venv`. Requires Python 3.10+, `git`, `gh` (logged in) and `claude` or `codex`.

Add the run output to the reviewed repo's `.gitignore` (Reptile also writes `.deep-review/.gitignore` itself):

```
.deep-review/*
!.deep-review/notes/
```

## Run

```bash
scripts/deep_review.py review --pr 123                      # or no --pr: the branch against origin's default branch
scripts/deep_review.py post --out .deep-review/<sha> --pr 123 --dry-run
scripts/deep_review.py post --out .deep-review/<sha> --pr 123
scripts/deep_review.py reply --pr 123 --comment <id> --status fixed --text "Guarded the await" --resolve
scripts/deep_review.py memory --since 2026-01-01            # optional: team rules from past PR threads
scripts/deep_review.py refresh                              # optional daily job: graph + wiki + new threads
```

## Configuration

| Variable | Default | |
|---|---|---|
| `DEEP_REVIEW_ENGINE` | `claude` | or `codex` (also `--engine`) |
| `DEEP_REVIEW_MODEL` | `claude-opus-5-5` | reviewers and dedupe (claude) |
| `DEEP_REVIEW_CHEAP_MODEL` | `claude-haiku-5-5` | wiki pages (claude) |
| `DEEP_REVIEW_MEMORY_MODEL` | `claude-sonnet-5-5` | team rules and comment writing (claude) |
| `DEEP_REVIEW_CODEX_MODEL` | Codex default | every call (codex) |
| `DEEP_REVIEW_CLAUDE_CMD` | `claude` | command prefix, for a wrapper: `my-proxy run --` |
| `DEEP_REVIEW_HOME` | `~/.cache/deep-pr-review` | venv, and per repo `<owner-repo>/` graph, wiki, memory |
| `DEEP_REVIEW_CALL_TIMEOUT` | `3600` | seconds per model call |

Per-repo reviewer notes, if present, go into the prompts: `.deep-review/notes/all.md` (every reviewer) and `.deep-review/notes/<mode>.md` (for example `regressions.md`).

## How it works

1. A tree-sitter graph of every Swift declaration at the head commit (cached per file blob).
2. A context pack per changed declaration: base version, callees, usage sites, sibling implementations, other users of the same keys; plus facts (localization keys, non-code files).
3. A short wiki page per touched area from a cheap model, cached until the area's declarations change.
4. Team rules ("check" and "accepted") mined from the repo's past PR review threads, if `memory` was run.
5. One Opus reviewer per file group (at most 8), read-only tools in a detached worktree, 30 turns each.
6. One whole-PR pass for cross-file issues, and the `clean-code` and `regressions` single-mode reviewers in parallel.
7. A dedupe pass merges findings with the same root cause and drops nothing; `--filter` instead drops and ranks (fewer comments, more misses).
8. `post` writes Greptile-style comments with a cheap model, maps each to a line on the diff's right side, and posts one review.

On unseen PRs of a large Swift app, this default configuration caught about 74-77% of Greptile's comments strictly (about 86% counting near matches), at about $5-7 per PR.

## Limits

- The graph and context packs are Swift only. Other languages are still reviewed from the diff, and reviewers can read any file, but they get no packs and no wiki.
- Reviews commits only; uncommitted changes are not seen.
- Claude reviewers run with `--dangerously-skip-permissions` and Edit, Write, NotebookEdit, Agent, WebFetch and WebSearch disallowed. Bash stays available for `git` and `rg`, so run it only on code you trust. Codex runs with `--sandbox read-only`.
- Cost is reported for Claude only (`meta.json` `cost_usd`); it is `null` for Codex.
- Review threads, `post` and `reply` need GitHub and `gh`.
