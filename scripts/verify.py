"""Checks each finding before anything is posted: one verifier per finding decides whether it is true and worth
changing. On the author's own PR, one fixer then fixes the valid findings in the checkout, commits each and pushes."""
import json, os, re, subprocess
from concurrent.futures import ThreadPoolExecutor
import llm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARALLEL = 6


def verdicts(args, findings):
    """{id: {"valid", "reason", "fix", "suggestion"}}, saved as <out>/verdicts.json."""
    os.makedirs(f"{args.out}/verify", exist_ok=True)
    head = checkout(args)
    try:
        with ThreadPoolExecutor(PARALLEL) as ex:
            found = dict(zip([f["id"] for f in findings], ex.map(lambda f: verdict(args, f, head), findings)))
    finally:
        git(args.repo, "worktree", "remove", "--force", head)
    json.dump(found, open(f"{args.out}/verdicts.json", "w"), indent=1)
    return found


def checkout(args):
    """A detached checkout of the reviewed head commit, so verifiers read the PR's code, not the local branch."""
    path, sha = f"{args.out}/head", json.load(open(f"{args.out}/meta.json"))["head"]
    git(args.repo, "fetch", "-q", "origin", f"pull/{args.pr}/head")
    git(args.repo, "worktree", "remove", "--force", path)
    git(args.repo, "worktree", "add", "-q", "--detach", path, sha)
    return path


def git(repo, *a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True).stdout


def verdict(args, f, head):
    text, _ = llm.ask(verify_prompt(args, f), f"{args.out}/verify/{f['id']}", cwd=head, tools=True)
    field = lambda name: (m.group(1).strip() if (m := re.search(rf"^{name}:\s*(.+)$", text, re.M)) else "")
    suggestion = re.search(r"```suggestion\n(.*?)```", text, re.S)
    return {"valid": field("VERDICT").upper().startswith("VALID"), "reason": field("REASON"), "fix": field("FIX"),
            "suggestion": suggestion.group(1) if suggestion else ""}


def verify_prompt(args, f):
    meta = json.load(open(f"{args.out}/meta.json"))
    conversation = f"{args.out}/conversation.md"
    return "\n".join([open(f"{ROOT}/prompts/verify.md").read(), f"\nBase commit: {meta['base']}\nHead commit: {meta['head']}\n",
                      "## The finding\n", f["line"], "\n## Pull request\n", open(f"{args.out}/context.md").read()[:20000],
                      "\n## PR conversation\n", open(conversation).read()[:20000] if os.path.exists(conversation) else "(none)"])


def fix(args, valid, verdict_of, title):
    """Fixes the valid findings in the checkout and pushes: ({id: {"sha", "what"}}, {id: why not fixed})."""
    if not valid:
        return {}, {}
    prefix = m.group(0) + " " if (m := re.match(r"\[[A-Z]+-\d+\]", title or "")) else ""
    items = [f"{f['line']}\n  Verified: {verdict_of[f['id']]['reason']} Fix: {verdict_of[f['id']]['fix']}" for f in valid]
    prompt = "\n".join([open(f"{ROOT}/prompts/fix.md").read().replace("{prefix}", prefix), "\n## Pull request\n",
                        open(f"{args.out}/context.md").read()[:20000], "\n## Findings to fix\n", *items])
    text, _ = llm.ask(prompt, f"{args.out}/fix", cwd=args.repo, tools="write")
    fixed = {m.group(1): {"sha": m.group(2), "what": m.group(3).strip()}
             for m in re.finditer(r"^(F\d+) \| FIXED (\w+) \| (.+)$", text, re.M)}
    skipped = {m.group(1): m.group(2).strip() for m in re.finditer(r"^(F\d+) \| NOT FIXED \| (.+)$", text, re.M)}
    if fixed:
        subprocess.run(["git", "-C", args.repo, "push", "-q", "origin", "HEAD"], check=True)
    return fixed, skipped
