# owl (Owl)

A Greptile-style pull request reviewer packaged as an agent skill for Claude Code and Codex CLI. It reviews a PR or branch diff with several parallel read-only model reviewers, posts the result as one GitHub review by "Owl", and gives the fixing agent a command to answer each comment.

## Set up on any repo with Claude Code or Codex

Open Claude Code or Codex CLI in the repo and paste:

```text
Set up the Owl PR reviewer (https://github.com/timdolenko/owl) for this repository.

1. If ~/owl does not exist, clone the repo to ~/owl and run ./install.sh (it installs for both Claude Code and Codex).
2. Add `.owl/*` and `!.owl/notes/` to this repo's .gitignore.
3. In the background, run `~/owl/scripts/owl.py memory --since <the date 6 months ago>`
   from the repo root and wait for it to finish.
4. Write .owl/notes/all.md, .owl/notes/clean-code.md and .owl/notes/regressions.md, 5 to 10 short
   bullets each. Build them from ~/.cache/owl/<owner-repo>/memory/rules.json, the repo's
   CLAUDE.md / AGENTS.md / CONTRIBUTING.md, and its lint and CI configs.
   - all.md: what is never a finding in this repo.
   - clean-code.md: conventions reviewers enforce, minus anything a linter already enforces.
   - regressions.md: where changes here break things CI does not catch.
   Every bullet must come from a past review thread or a written rule. No generic advice.
5. Pick the most recently merged PR that had review comments and run
   `~/owl/scripts/owl.py review --pr <n>`. Compare its findings.md with the comments
   reviewers actually left, and list what Owl caught, missed, and raised that nobody did.
   Never post anything to GitHub.
6. Show me the notes and that comparison. Commit only the notes and .gitignore once I approve.
```

### Manual setup

What makes Owl review like your team is not the model but two inputs: team rules mined from the repo's past review threads, and short reviewer notes on what matters in this codebase. Setup builds both once.

**1. Install** (Python 3.10+, `git`, `gh` logged in, `claude` or `codex` on `PATH`):

```bash
git clone https://github.com/timdolenko/owl ~/owl && ~/owl/install.sh --claude
```

Any clone location works; `~/owl` is only the example used here. The venv lives at `${OWL_HOME:-~/.cache/owl}/venv`. `--codex` installs for Codex CLI instead; `--copy` copies instead of linking.

**2. Keep run output out of the reviewed repo** (Owl also writes `.owl/.gitignore` itself):

```
.owl/*
!.owl/notes/
```

**3. Gather the team's review history.** From inside the repo:

```bash
~/owl/scripts/owl.py memory --since 2026-01-01
```

It fetches every PR review thread (human and bot) since that date with `gh` and turns them into "check" rules (what reviewers flagged) and "accepted" rules (what they let through) in `~/.cache/owl/<owner-repo>/memory/rules.json`. Each review then gets the rules that match its files, only from threads older than the PR. The default window is 180 days. This is the slow step: one model call per batch of threads.

**4. Write the reviewer notes.** Short bullets, committed in the repo:

- `.owl/notes/all.md` (every reviewer and verifier): what is never a finding here, for example accepted conventions or what CI and linters already enforce.
- `.owl/notes/clean-code.md`: the conventions the team enforces in review.
- `.owl/notes/regressions.md`: where changes break things CI does not catch (build configurations, a second project file, several entry points into one flow, server contracts).

`OWL_NOTES=<dir>` reads them from somewhere else instead.

**5. Run it.** Commit first; Owl reviews commits only.

```bash
~/owl/scripts/owl.py review --pr 123                                  # writes .owl/<sha>/findings.md
~/owl/scripts/owl.py post --out .owl/<sha> --pr 123 --dry-run        # preview, no GitHub writes
~/owl/scripts/owl.py post --out .owl/<sha> --pr 123                  # author: fixes and pushes; reviewer: posts
```

Keep the inputs fresh with a daily `owl.py refresh` (graph, wiki and the last 2 days of review threads).

## Results

On unseen PRs of a large Swift app, the default configuration caught about 74-77% of Greptile's comments strictly (about 86% counting near matches), at about $5-7 per PR with Claude Opus and 5-20 minutes per review.

## Run

```bash
scripts/owl.py review --pr 123                      # or no --pr: the branch against origin's default branch
scripts/owl.py post --out .owl/<sha> --pr 123 --dry-run
scripts/owl.py post --out .owl/<sha> --pr 123
scripts/owl.py reply --pr 123 --comment <id> --status fixed --text "Guarded the await" --resolve
scripts/owl.py memory --since 2026-01-01            # optional: team rules from past PR threads
scripts/owl.py refresh                              # optional daily job: graph + wiki + new threads
```

## Configuration

| Variable | Default | |
|---|---|---|
| `OWL_ENGINE` | `claude` | or `codex` (also `--engine`) |
| `OWL_MODEL` | `claude-opus-5-5` | reviewers and dedupe (claude) |
| `OWL_CHEAP_MODEL` | `claude-haiku-5-5` | wiki pages (claude) |
| `OWL_MEMORY_MODEL` | `claude-sonnet-5-5` | team rules and comment writing (claude) |
| `OWL_CODEX_MODEL` | Codex default | every call (codex) |
| `OWL_CLAUDE_CMD` | `claude` | command prefix, for a wrapper: `my-proxy run --` |
| `OWL_HOME` | `~/.cache/owl` | venv, and per repo `<owner-repo>/` graph, wiki, memory |
| `OWL_CALL_TIMEOUT` | `3600` | seconds per model call |

Per-repo reviewer notes, if present, go into the prompts: `.owl/notes/all.md` (every reviewer) and `.owl/notes/<mode>.md` (for example `regressions.md`).

## How it works

1. A tree-sitter graph of every Swift declaration at the head commit (cached per file blob).
2. A context pack per changed declaration: base version, callees, usage sites, sibling implementations, other users of the same keys; plus facts (localization keys, non-code files).
3. A short wiki page per touched area from a cheap model, cached until the area's declarations change.
4. Team rules ("check" and "accepted") mined from the repo's past PR review threads, if `memory` was run.
5. One Opus reviewer per file group (at most 8), read-only tools in a detached worktree, 30 turns each.
6. One whole-PR pass for cross-file issues, and the `clean-code` and `regressions` single-mode reviewers in parallel.
7. A dedupe pass merges findings with the same root cause and drops nothing; `--filter` instead drops and ranks (fewer comments, more misses).
8. `post` writes Greptile-style comments with a cheap model, maps each to a line on the diff's right side, and posts one review.

## Limits

- The graph and context packs are Swift only. Other languages are still reviewed from the diff, and reviewers can read any file, but they get no packs and no wiki.
- Reviews commits only; uncommitted changes are not seen.
- Claude reviewers run with `--dangerously-skip-permissions` and Edit, Write, NotebookEdit, Agent, WebFetch and WebSearch disallowed. Bash stays available for `git` and `rg`, so run it only on code you trust. Codex runs with `--sandbox read-only`.
- Cost is reported for Claude only (`meta.json` `cost_usd`); it is `null` for Codex.
- Review threads, `post` and `reply` need GitHub and `gh`.
