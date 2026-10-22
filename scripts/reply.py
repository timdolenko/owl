"""Answers one posted review comment ("Fixed in <sha>: ..." or the reason) and optionally resolves its thread."""
import json
from post import gh

THREADS = """query($o: String!, $r: String!, $n: Int!) { repository(owner: $o, name: $r) { pullRequest(number: $n) {
  reviewThreads(first: 100) { nodes { id comments(first: 100) { nodes { databaseId } } } } } } }"""
RESOLVE = "mutation($id: ID!) { resolveReviewThread(input: {threadId: $id}) { thread { isResolved } } }"


def thread_of(nwo, pr, comment):
    owner, name = nwo.split("/")
    data = json.loads(gh("api", "graphql", "-f", f"query={THREADS}", "-f", f"o={owner}", "-f", f"r={name}", "-F", f"n={pr}"))
    for t in data["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]:
        if any(c["databaseId"] == comment for c in t["comments"]["nodes"]):
            return t["id"]
    raise SystemExit(f"no review thread holds comment {comment}")


def run(args):
    text = f"Fixed in {args.sha}: {args.text}" if args.status == "fixed" else args.text
    gh("api", f"repos/{args.nwo}/pulls/{args.pr}/comments/{args.comment}/replies", "-f", f"body={text}")
    if args.resolve:
        gh("api", "graphql", "-f", f"query={RESOLVE}", "-f", f"id={thread_of(args.nwo, args.pr, args.comment)}")
    print(f"replied to {args.comment}" + (" and resolved its thread" if args.resolve else ""))
