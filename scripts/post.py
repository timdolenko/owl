"""Posts a run's findings to its PR as one GitHub review by Reptile, with a summary of what was checked.
Author role: every finding inline (low confidence ones marked), summary block in the PR description. Reviewer role: only P0-P2 with
confidence >= 0.75 inline, summary block in the review body. Writes <out>/posted.json."""
import json, os, re, subprocess, sys
import llm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START, END = "<!-- reptile:start -->", "<!-- reptile:end -->"
LOW = 0.5
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


def is_inline(f, role):
    if role == "author":
        return True
    return f["sev"] in ("P0", "P1", "P2") and f["confidence"] >= 0.75


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
    title, _, rest = written["body"].partition("\n")
    if f["confidence"] < LOW:
        title += f"\n\n<sub>Low confidence ({f['confidence']:.2f}): check that the scenario is reachable before fixing.</sub>"
    body = f"{title}\n{rest}".rstrip()
    if written.get("suggestion") and not moved:
        body += f"\n\n```suggestion\n{written['suggestion'].rstrip()}\n```"
    body += fix_prompt(f, written["body"])
    c = {"path": f["path"], "line": end, "side": "RIGHT", "body": body}
    if start:
        c.update(start_line=start, start_side="RIGHT")
    return c


def fix_prompt(f, text):
    return ("\n\n<details><summary>Prompt to fix with AI</summary>\n\n`````markdown\n"
            f"This is a comment left during a code review.\nPath: {f['path']}\nLines: {f['start']}-{f['end']}\n\n{text.strip()}\n\n"
            "Verify the issue against the code first. If it is valid, fix it with the smallest change; if not, reply why.\n"
            "`````\n</details>")


def passed_rows(out):
    path = f"{out}/passed.md"
    return [[x.strip() for x in l.split(" | ")] for l in open(path).read().splitlines() if l.strip()] if os.path.exists(path) else []


def summary_block(posted, held, passed):
    unsure = [f"- {f['sev']} `{f['path']}:{f['start']}-{f['end']}` {f['problem']} Fix: {f['fix']} (confidence {f['confidence']})"
              for f in held]
    unsure = [f"- {r[1]}. Manual step: {r[2] if len(r) > 2 else 'unknown'}" for r in passed if r[0] == "NOT CONFIRMED"] + unsure
    safe = [f"- {r[1]}" + (f" ({r[2]})" if len(r) > 2 else "") for r in passed if r[0] == "SAFE"]
    return "\n".join([START, f"**Code review done by Reptile**: {posted} issues posted as comments · {len(safe)} checked and safe"
                      f" · {len(unsure)} unsure", "", f"<details><summary>Reptile review notes ({len(safe)} + {len(unsure)})</summary>",
                      "", "**Unsure**", "", *(unsure or ["- none"]), "", "**Checked and safe**", "", *(safe or ["- none"]), "",
                      "</details>", END])


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
    pr = json.loads(gh("pr", "view", str(args.pr), "-R", args.nwo, "--json", "author,headRefOid,body"))
    role, meta = role_of(args, pr), json.load(open(f"{args.out}/meta.json"))
    if meta["head"] != pr["headRefOid"]:
        print(f"warning: run reviewed {meta['head'][:10]}, PR head is {pr['headRefOid'][:10]}; lines may be off", file=sys.stderr)
    files = right_side(gh("pr", "diff", str(args.pr), "-R", args.nwo))
    findings = parse_findings(open(f"{args.out}/findings.md").read())
    spots = {f["id"]: place(f, files) for f in findings}
    inline = [f for f in findings if is_inline(f, role) and spots[f["id"]] and f["id"] not in done]
    held = [f for f in findings if f not in inline and f["id"] not in done]
    written = written_comments(inline, args.out)
    comments = [review_comment(f, written[f["id"]], spots[f["id"]]) for f in inline]
    block = summary_block(len(comments) + len(done), held, passed_rows(args.out))
    counts = ", ".join(f"{s}: {n}" for s in ("P0", "P1", "P2", "P3") if (n := sum(f["sev"] == s for f in inline)))
    body = f"Reptile: {len(comments)} comment{'' if len(comments) == 1 else 's'}" + (f" ({counts})" if counts else "")
    review = {"commit_id": pr["headRefOid"], "event": "COMMENT", "comments": comments,
              "body": body if role == "author" else f"{body}\n\n{block}"}
    if args.dry_run:
        print(f"role: {role}\n\n# review\n{json.dumps(review, indent=1)}\n\n# description block" +
              (f"\n{block}" if role == "author" else ": none (reviewer role, the block is in the review body)"))
        return
    publish(args, role, review, inline, pr, block, done)


def publish(args, role, review, inline, pr, block, done):
    posted = {"pr": args.pr, "role": role, "comments": dict(done)}
    if review["comments"] or role == "reviewer":
        res = json.loads(gh("api", f"repos/{args.nwo}/pulls/{args.pr}/reviews", "--method", "POST", "--input", "-",
                            stdin=json.dumps(review)))
        made = json.loads(gh("api", f"repos/{args.nwo}/pulls/{args.pr}/reviews/{res['id']}/comments?per_page=100"))
        posted.update(review_id=res["id"], review_url=res.get("html_url"))
        for f, c in zip(inline, review["comments"]):
            hit = next((m for m in made if m["path"] == c["path"] and m["body"].strip() == c["body"].strip()), None)
            if hit:
                posted["comments"][f["id"]] = {"id": hit["id"], "path": hit["path"], "line": c["line"], "url": hit["html_url"]}
    if role == "author":
        open(f"{args.out}/pr-body.md", "w").write(with_block(pr["body"], block))
        gh("pr", "edit", str(args.pr), "-R", args.nwo, "--body-file", f"{args.out}/pr-body.md")
        posted["description_updated"] = True
    json.dump(posted, open(f"{args.out}/posted.json", "w"), indent=1)
    print(f"Reptile posted {len(posted['comments'])} comments as {role}: {posted.get('review_url', 'description only')}")
