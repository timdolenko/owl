"""Verifies each finding (verify.py), then publishes. Author role (your own PR): Reptile fixes the valid findings,
commits and pushes, and posts no comments; what it fixed, what it checked and did not change, and what it could not
check go folded into the PR description, for the author and for Greptile. Reviewer role (someone else's PR): only
verified P0-P2 findings are posted inline, with a suggestion when the fix is small; with none, Reptile approves the PR.
Writes <out>/posted.json."""
import json, os, re, subprocess, sys
from urllib.parse import quote
import llm, verify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START, END = "<!-- reptile:start -->", "<!-- reptile:end -->"
RANGE = re.compile(r"^([^|]+?\.[A-Za-z0-9]+):(\d+)(?:-(\d+))?")


def gh(*args, stdin=None):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, input=stdin)
    if r.returncode:
        sys.exit(f"gh {' '.join(args[:3])}: {r.stderr.strip()}")
    return r.stdout


def confidence(text):
    m = re.search(r"\d*\.?\d+", text)
    return float(m.group()) if m else 0.0


def parse_findings(text):
    """F-lines of findings.md: `F<n> | sources | path:start-end | P | category | confidence | problem | fix`."""
    out = []
    for line in text.splitlines():
        if not re.match(r"^F\d+ \|", line):
            continue
        f = [x.strip() for x in line.split(" | ")]
        i = next((k for k, x in enumerate(f) if RANGE.match(x)), None)
        if i is None:  # a file with no line: the comment goes on its first changed line
            i = next((k for k, x in enumerate(f) if k > 1 and re.match(r"^[^ ]*/[^|]*\.\w+$", x)), None)
        if i is None or len(f) < i + 6:
            continue
        m = RANGE.match(f[i]) or re.match(r"^(.*)()()$", f[i])
        out.append({"id": f[0], "path": m.group(1), "start": int(m.group(2) or 0), "end": int(m.group(3) or m.group(2) or 0),
                    "sev": f[i + 1], "category": f[i + 2], "confidence": confidence(f[i + 3]), "problem": f[i + 4],
                    "fix": " | ".join(f[i + 5:]), "line": line})
    return out


def right_side(diff):
    """{path: [hunk lines]}: the head-side line numbers (added and context) GitHub accepts comments on."""
    files, path, hunk, line = {}, None, None, 0
    for l in diff.splitlines():
        if l.startswith("diff --git"):
            path = hunk = None
        elif hunk is None and l.startswith("+++ "):
            path = l[6:].rstrip("\t") if l.startswith("+++ b/") else None
        elif (m := re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", l)) and path:
            hunk, line = [], int(m.group(1))
            files.setdefault(path, []).append(hunk)
        elif hunk is not None and l.startswith(("+", " ")):
            hunk.append(line)
            line += 1
    return {p: [h for h in hs if h] for p, hs in files.items()}


def place(f, files):
    """(start or None, end, moved) on the right side of the diff, or None when the file is not in the diff."""
    hunks = files.get(f["path"])
    if not hunks:
        return None
    hunk = min(hunks, key=lambda h: min(abs(x - f["end"]) for x in h))
    end = min(hunk, key=lambda x: abs(x - f["end"]))
    start = min(hunk, key=lambda x: abs(x - f["start"]))
    return (start if start < end else None), end, (start, end) != (f["start"], f["end"])


def written_comments(findings, out):
    """One cheap call turns F-lines into review comments; a finding the model skipped keeps a plain comment."""
    by_id = {}
    if findings:
        prompt = open(f"{ROOT}/prompts/comment.md").read() + "\n".join(f["line"] for f in findings)
        text, _ = llm.ask(prompt, f"{out}/post-comments", model=llm.MEMORY)
        try:
            by_id = {c["id"]: c for c in json.loads(text[text.index("{"):text.rindex("}") + 1])["comments"]}
        except (ValueError, KeyError, TypeError):
            pass
    return {f["id"]: by_id.get(f["id"]) or {"body": f"**{f['sev']} {f['category']}**\n\n{f['problem']}\n\nFix: {f['fix']}"}
            for f in findings}


def review_comment(f, written, spot):
    start, end, moved = spot
    body = written["body"].rstrip()
    if written.get("suggestion") and not moved:
        body += f"\n\n```suggestion\n{written['suggestion'].rstrip()}\n```"
    c = {"path": f["path"], "line": end, "side": "RIGHT", "body": body}
    if start:
        c.update(start_line=start, start_side="RIGHT")
    return c


def passed_rows(out):
    path = f"{out}/passed.md"
    return [[x.strip() for x in l.split(" | ")] for l in open(path).read().splitlines() if l.strip()] if os.path.exists(path) else []


def summary_block(findings, fixed, declined, passed):
    by_id = {f["id"]: f for f in findings}
    row = lambda i: f"- {by_id[i]['sev']} `{by_id[i]['path'].rsplit('/', 1)[-1]}:{by_id[i]['start']}` {by_id[i]['problem'][:300]}"
    done = [f"{row(i)} **Fixed** in {x['sha'][:10]}: {x['what']}" for i, x in fixed.items() if i in by_id]
    kept = [f"{row(i)} **Not changed:** {why}" for i, why in declined.items() if i in by_id]
    unsure = [f"- {r[1]}. Manual step: {r[2] if len(r) > 2 else 'unknown'}" for r in passed if r[0] == "NOT CONFIRMED"]
    safe = sum(r[0] == "SAFE" for r in passed)
    fold = lambda title, rows: ["", f"<details><summary>{title} ({len(rows)})</summary>", "", *rows, "", "</details>"] if rows else []
    return "\n".join([START, f"**Code review done by Reptile**: {len(done)} found and fixed · {len(kept)} checked and not changed"
                      f" · {safe} checked and safe · {len(unsure)} unsure", *fold("Fixed", done),
                      *fold("Checked and not changed", kept), *fold("Unsure", unsure), END])


def with_block(body, block):
    body = body or ""
    if START in body and END in body:
        return re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, body, flags=re.S)
    return f"{body.rstrip()}\n\n{block}\n".lstrip()


def role_of(args, pr):
    if args.role != "auto":
        return args.role
    return "author" if gh("api", "user", "-q", ".login").strip() == pr["author"]["login"] else "reviewer"


def run(args):
    prev = json.load(open(f"{args.out}/posted.json")) if os.path.exists(f"{args.out}/posted.json") else None
    if prev and not args.force and not args.dry_run:
        sys.exit(f"{args.out}/posted.json exists: this run was posted already (--force posts the findings not posted yet)")
    done = (prev or {}).get("comments", {})
    pr = json.loads(gh("pr", "view", str(args.pr), "-R", args.nwo, "--json", "author,headRefOid,body,title"))
    role, meta = role_of(args, pr), json.load(open(f"{args.out}/meta.json"))
    if meta["head"] != pr["headRefOid"]:
        print(f"warning: run reviewed {meta['head'][:10]}, PR head is {pr['headRefOid'][:10]}; lines may be off", file=sys.stderr)
    findings = parse_findings(open(f"{args.out}/findings.md").read())
    verdict_of = verify.verdicts(args, findings)
    valid = [f for f in findings if verdict_of[f["id"]]["valid"]]
    declined = {f["id"]: verdict_of[f["id"]]["reason"] for f in findings if f not in valid}
    if role == "author":
        return publish_author(args, pr, findings, valid, verdict_of, declined)
    files = right_side(gh("pr", "diff", str(args.pr), "-R", args.nwo))
    spots = {f["id"]: place(f, files) for f in valid}
    inline = [f for f in valid if f["sev"] in ("P0", "P1", "P2") and spots[f["id"]] and f["id"] not in done]
    written = written_comments(inline, args.out)
    for f in inline:
        written[f["id"]]["suggestion"] = verdict_of[f["id"]]["suggestion"] or written[f["id"]].get("suggestion")
    comments = [review_comment(f, written[f["id"]], spots[f["id"]]) for f in inline]
    counts = ", ".join(f"{s}: {n}" for s in ("P0", "P1", "P2") if (n := sum(f["sev"] == s for f in inline)))
    body = f"Reptile: {len(comments)} comment{'' if len(comments) == 1 else 's'}" + (f" ({counts})" if counts else "")
    review = {"commit_id": pr["headRefOid"], "event": "COMMENT", "comments": comments, "body": body}
    if args.dry_run:
        print(f"role: {role}\n\n# review\n{json.dumps(review, indent=1)}")
        return
    publish(args, review, inline, done, meta["head"] == pr["headRefOid"])


def publish_author(args, pr, findings, valid, verdict_of, declined):
    if args.dry_run:
        print("role: author\n\n# would fix\n" + "\n".join(f["line"] for f in valid) +
              "\n\n# description block\n" + summary_block(findings, {}, declined, passed_rows(args.out)))
        return
    fixed, skipped = verify.fix(args, valid, verdict_of, pr["title"])
    declined.update({i: f"Verified as valid, but not fixed: {why}" for i, why in skipped.items()})
    block = summary_block(findings, fixed, declined, passed_rows(args.out))
    open(f"{args.out}/pr-body.md", "w").write(with_block(pr["body"], block))
    gh("pr", "edit", str(args.pr), "-R", args.nwo, "--body-file", f"{args.out}/pr-body.md")
    json.dump({"pr": args.pr, "role": "author", "fixed": fixed, "declined": declined}, open(f"{args.out}/posted.json", "w"), indent=1)
    print(f"Reptile fixed {len(fixed)} findings and pushed; {len(declined)} not changed; notes in the PR description")


def publish(args, review, inline, done, reviewed_head):
    posted = {"pr": args.pr, "role": "reviewer", "comments": dict(done)}
    if not review["comments"] and done:
        print("Reptile: no new verified P0-P2 finding; nothing posted")
        return
    if not review["comments"] and not reviewed_head:
        print("Reptile: no finding, but the PR head moved since the review; not approving. Review the new head.")
        return
    if not review["comments"]:
        review.update(event="APPROVE", body="")
    res = json.loads(gh("api", f"repos/{args.nwo}/pulls/{args.pr}/reviews", "--method", "POST", "--input", "-",
                        stdin=json.dumps(review)))
    made = json.loads(gh("api", f"repos/{args.nwo}/pulls/{args.pr}/reviews/{res['id']}/comments?per_page=100"))
    posted.update(review_id=res["id"], review_url=res.get("html_url"))
    for f, c in zip(inline, review["comments"]):
        hit = next((m for m in made if m["path"] == c["path"] and m["body"].strip() == c["body"].strip()), None)
        if hit:
            posted["comments"][f["id"]] = {"id": hit["id"], "path": hit["path"], "line": c["line"], "url": hit["html_url"]}
    json.dump(posted, open(f"{args.out}/posted.json", "w"), indent=1)
    verb = "approved" if review["event"] == "APPROVE" else f"posted {len(posted['comments'])} comments"
    print(f"Reptile {verb}: {posted['review_url']}")
