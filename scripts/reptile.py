#!/usr/bin/env python3
"""reptile (Reptile): Greptile-style review of a PR or branch with Claude Code or Codex CLI.

  reptile.py [review] [--pr N | --base REF --head REF]   review a diff, write findings.md
  reptile.py index [--sha REF]                            repo graph + wiki for a commit
  reptile.py memory [--since YYYY-MM-DD]                  past PR review threads -> team rules
  reptile.py refresh                                      index the default branch + memory of the last 2 days
  reptile.py post --out RUN --pr N [--role auto]          post findings as one GitHub review by Reptile
  reptile.py reply --pr N --comment ID --status fixed     answer (and resolve) one posted comment

Data (graph, wiki, memory): ${REPTILE_HOME:-~/.cache/reptile}/<owner-repo>/.
Engine: --engine or REPTILE_ENGINE (claude | codex)."""
import argparse, datetime, json, os, re, shutil, subprocess, sys

HOME = os.path.expanduser(os.environ.get("REPTILE_HOME", "~/.cache/reptile"))
VENV = os.path.join(HOME, "venv")
MODES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "modes")
COMMANDS = ("review", "index", "memory", "refresh", "post", "reply")


def reexec_in_venv():
    """Runs under the venv install.sh made, so tree-sitter is importable."""
    py = os.path.join(VENV, "bin", "python")
    if os.path.exists(py) and os.path.realpath(sys.prefix) != os.path.realpath(VENV):
        os.execv(py, [py, *sys.argv])


def git(repo, *args, check=True):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    if check and r.returncode:
        sys.exit(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()


def name_with_owner(repo):
    url = git(repo, "remote", "get-url", "origin", check=False)
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    return f"{m.group(1)}/{m.group(2)}" if m else None


def setup(args):
    """Resolves the repo, its data dir and the engine; shared by every subcommand."""
    import graph, llm
    args.repo = git(args.repo or os.getcwd(), "rev-parse", "--show-toplevel")
    args.nwo = name_with_owner(args.repo)
    graph.use(os.path.join(HOME, args.nwo.replace("/", "-") if args.nwo else os.path.basename(args.repo)))
    llm.ENGINE, llm.DRY_RUN = args.engine, getattr(args, "dry_run", False)


def default_branch(repo):
    ref = git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False)
    if ref:
        return ref
    for r in ("origin/main", "origin/master", "main", "master"):
        if git(repo, "rev-parse", "--verify", "-q", r, check=False):
            return r
    sys.exit("no default branch found: pass --base")


def sha_of(repo, ref):
    return git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")


def pr_info(args):
    r = subprocess.run(["gh", "pr", "view", str(args.pr), "--json", "number,title,body,baseRefName,headRefOid,createdAt"],
                       cwd=args.repo, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"gh pr view {args.pr}: {r.stderr.strip()}")
    return json.loads(r.stdout)


def resolve_range(args):
    """Sets args.sha, args.base (the merge-base) and args.created; returns the PR context text."""
    args.created = "9999"
    if args.pr:
        pr = pr_info(args)
        git(args.repo, "fetch", "-q", "origin", pr["baseRefName"], f"pull/{pr['number']}/head", check=False)
        head, base_ref, args.created = args.head or pr["headRefOid"], args.base or f"origin/{pr['baseRefName']}", pr["createdAt"]
        context = f"# PR #{pr['number']}: {pr['title']}\n\n{pr['body'] or '(no description)'}\n"
    else:
        head, base_ref = args.head or "HEAD", args.base or default_branch(args.repo)
    args.sha = sha_of(args.repo, head)
    args.base = git(args.repo, "merge-base", sha_of(args.repo, base_ref), args.sha)
    if not args.pr:
        log = git(args.repo, "log", "--reverse", "--format=- %s%n%w(0,2,2)%b", f"{args.base}..{args.sha}")
        branch = git(args.repo, "rev-parse", "--abbrev-ref", head, check=False) or head
        context = f"# Branch {branch}\n\nNo PR description; the branch's commit messages:\n\n{log or '(no commits)'}\n"
    return context


def worktree(args):
    """A detached checkout of the head commit, so reviewers read exactly what is reviewed."""
    import graph
    path = os.path.join(graph.DATA, "worktrees", args.sha[:12])
    if git(path, "rev-parse", "HEAD", check=False) != args.sha:
        shutil.rmtree(path, ignore_errors=True)
        git(args.repo, "worktree", "prune")
        git(args.repo, "worktree", "add", "-q", "--detach", path, args.sha)
    return path


def ignore_runs(repo):
    """Keeps run output out of commits; notes/ stays committable."""
    path = os.path.join(repo, ".reptile", ".gitignore")
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").write("/*\n!/notes/\n")


def cmd_review(args):
    import review
    setup(args)
    for m in filter(None, args.modes.split(",")):
        if not os.path.exists(os.path.join(MODES, f"{m}.md")):
            sys.exit(f"unknown mode {m}: modes are {', '.join(f[:-3] for f in sorted(os.listdir(MODES)) if f != 'common.md')}")
    context = resolve_range(args)
    ignore_runs(args.repo)
    args.out = os.path.abspath(args.out or os.path.join(args.repo, ".reptile", args.sha))
    os.makedirs(args.out, exist_ok=True)
    args.context = os.path.join(args.out, "context.md")
    open(args.context, "w").write(context)
    args.worktree = worktree(args)
    try:
        count = review.run(args)
    finally:
        git(args.repo, "worktree", "remove", "--force", args.worktree, check=False)
    print(f"FINDINGS={count}\n{args.out}/findings.md")


def cmd_index(args):
    import graph, wiki
    setup(args)
    sha = sha_of(args.repo, args.sha or default_branch(args.repo))
    print(graph.build(args.repo, sha))
    if not args.no_wiki:
        wiki.refresh(sha)


def cmd_memory(args):
    import fetch_threads, memory
    setup(args)
    if not args.nwo:
        sys.exit("memory needs a GitHub remote named origin")
    fetch_threads.run(args.nwo, args.since)
    memory.build()


def cmd_refresh(args):
    """What a daily job runs. Each step is incremental: graph parses only new file contents, wiki rewrites only areas
    whose declarations changed, memory sends only comments it has not processed."""
    setup(args)
    git(args.repo, "fetch", "-q", "origin", check=False)
    args.sha, args.no_wiki = None, False
    cmd_index(args)
    if args.nwo:
        args.since = days_ago(2)
        cmd_memory(args)


def cmd_post(args):
    import llm, post
    setup(args)
    llm.DRY_RUN = args.no_llm
    if not args.nwo:
        sys.exit("post needs a GitHub remote named origin")
    args.out = os.path.abspath(args.out)
    post.run(args)


def cmd_reply(args):
    import reply
    setup(args)
    if not args.nwo:
        sys.exit("reply needs a GitHub remote named origin")
    args.sha = args.sha or git(args.repo, "rev-parse", "--short=10", "HEAD")
    reply.run(args)


def days_ago(n):
    return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()


def parser():
    base = argparse.ArgumentParser(add_help=False)
    base.add_argument("--repo", help="git repository (default: the one containing the current directory)")
    base.add_argument("--engine", choices=("claude", "codex"), default=os.environ.get("REPTILE_ENGINE", "claude"))
    common = argparse.ArgumentParser(add_help=False, parents=[base])
    common.add_argument("--dry-run", action="store_true", help="build everything and write every prompt, call no model")
    p = argparse.ArgumentParser(prog="reptile.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", metavar="{review,index,memory,refresh,post,reply}")
    r = sub.add_parser("review", parents=[common], help="review a PR or branch diff (default)")
    r.add_argument("--base", help="base ref (default: merge-base with origin's default branch, or the PR's base)")
    r.add_argument("--head", help="head ref (default: HEAD, or the PR's head commit)")
    r.add_argument("--pr", type=int, help="GitHub PR number: title, body and base come from `gh pr view`")
    r.add_argument("--out", help="run directory (default: <repo>/.reptile/<head-sha>)")
    r.add_argument("--modes", default="clean-code,regressions", help="single-mode reviewers, comma separated ('' for none)")
    for flag, text in (("--no-wiki", "skip the per-area wiki pages"), ("--no-memory", "skip team rules from past reviews"),
                       ("--no-packs", "skip the graph context packs"), ("--no-dedupe", "keep every raw candidate"),
                       ("--filter", "drop and rank with a strict filter pass instead of the dedupe (posts fewer, misses more)")):
        r.add_argument(flag, action="store_true", help=text)
    i = sub.add_parser("index", parents=[common], help="build the repo graph (and wiki) for a commit")
    i.add_argument("--sha", help="commit or ref (default: origin's default branch)")
    i.add_argument("--no-wiki", action="store_true", help="graph only, no model calls")
    m = sub.add_parser("memory", parents=[common], help="fetch past PR review threads with gh and build team rules")
    m.add_argument("--since", default=days_ago(180), help="PRs updated since this date (default: 180 days ago)")
    sub.add_parser("refresh", parents=[common], help="index the default branch and add the last 2 days of review threads")
    po = sub.add_parser("post", parents=[base], help="post a run's findings to its PR as one review by Reptile")
    po.add_argument("--out", required=True, help="run directory of the review")
    po.add_argument("--pr", type=int, required=True)
    po.add_argument("--role", choices=("author", "reviewer", "auto"), default="auto",
                    help="author: comments + PR description block; reviewer: stricter bar, block in the review (auto: by gh user)")
    po.add_argument("--dry-run", action="store_true", help="print the review JSON and the description block; no GitHub writes")
    po.add_argument("--no-llm", action="store_true", help="plain comments from the F-lines, no model call")
    po.add_argument("--force", action="store_true", help="post again although posted.json exists")
    rp = sub.add_parser("reply", parents=[base], help="reply to one posted comment and optionally resolve its thread")
    rp.add_argument("--pr", type=int, required=True)
    rp.add_argument("--comment", type=int, required=True, help="comment id from <run>/posted.json")
    rp.add_argument("--status", choices=("fixed", "declined"), required=True)
    rp.add_argument("--text", required=True, help="what changed, or why not")
    rp.add_argument("--sha", help="commit of the fix (default: HEAD)")
    rp.add_argument("--resolve", action="store_true", help="resolve the review thread")
    return p


def main(argv):
    if not argv or (argv[0] not in COMMANDS and argv[0] not in ("-h", "--help")):
        argv = ["review", *argv]
    args = parser().parse_args(argv)
    {"review": cmd_review, "index": cmd_index, "memory": cmd_memory, "refresh": cmd_refresh, "post": cmd_post,
     "reply": cmd_reply}[args.cmd](args)


if __name__ == "__main__":
    reexec_in_venv()
    main(sys.argv[1:])
