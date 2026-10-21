"""The PR's existing conversation, so reviewers do not repeat what was already said or settled: top-level comments,
review summaries and every inline thread with its replies and whether it is resolved or outdated."""
import json, re, subprocess

THREADS = """
query($owner: String!, $name: String!, $pr: Int!, $after: String) {
  repository(owner: $owner, name: $name) { pullRequest(number: $pr) {
    reviewThreads(first: 50, after: $after) {
      pageInfo { hasNextPage endCursor }
      nodes { isResolved isOutdated path line originalLine
        comments(first: 50) { nodes { author { login } body createdAt } } }
    } } }
}"""
CAP = 3000


def gh(*args):
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None


def threads(nwo, pr):
    owner, name = nwo.split("/")
    out, after = [], None
    while True:
        args = ["api", "graphql", "-f", f"query={THREADS}", "-f", f"owner={owner}", "-f", f"name={name}", "-F", f"pr={pr}"]
        page = gh(*args, *(["-f", f"after={after}"] if after else []))
        if not page:
            return out
        t = page["data"]["repository"]["pullRequest"]["reviewThreads"]
        out += t["nodes"]
        if not t["pageInfo"]["hasNextPage"]:
            return out
        after = t["pageInfo"]["endCursor"]


def said(c):
    body = re.sub(r"<details>.*?</details>|<img[^>]*>|<a href=\"#\">\s*</a>", "", c.get("body") or "", flags=re.S).strip()
    return f"**{(c.get('author') or c.get('user') or {}).get('login', '?')}**: {body[:CAP]}"


def text(nwo, pr):
    issue = gh("api", "--paginate", f"repos/{nwo}/issues/{pr}/comments") or []
    reviews = [r for r in gh("api", "--paginate", f"repos/{nwo}/pulls/{pr}/reviews") or [] if (r.get("body") or "").strip()]
    parts = []
    for t in threads(nwo, pr):
        state = "resolved" if t["isResolved"] else "open"
        state += ", outdated" if t["isOutdated"] else ""
        parts.append(f"### `{t['path']}:{t['line'] or t['originalLine']}` ({state})\n\n" +
                     "\n\n".join(said(c) for c in t["comments"]["nodes"]))
    parts += [f"### Review summary ({r['state'].lower()})\n\n{said(r)}" for r in reviews]
    parts += [f"### Comment\n\n{said(c)}" for c in issue]
    return "\n\n".join(parts)
