#!/usr/bin/env python3
"""Team memory, Greptile-style: review comments of past PRs (Greptile's and humans', with the replies) turned into
dated rules: "check" rules the team wants caught, and "accepted" rules for things the team said are fine.
  build()        writes <data>/memory/rules.json from the threads fetch_threads.py saved
Library: select(created, paths, diff) -> rules text, using only comments made before `created` (no leakage)."""
import glob, json, os, re, time
from concurrent.futures import ThreadPoolExecutor
import graph, llm, wiki

BATCH = 30


def mem(*parts):
    return os.path.join(graph.DATA, "memory", *parts)


PROMPT = """Below are review comments from past pull requests of this codebase, each with its replies.
Turn each into a reusable review rule, or skip it.

- "check": the comment points at a class of defect worth catching again (a bot comment nobody rejected, or a human reviewer's request). Write a general rule: "When <code pattern>, check <risk>". Keep shared infrastructure names (for example a shared AnalyticsService, SettingsStore or NetworkClient) because they recur; drop names only this PR had.
- "accepted": a human reply rejected the comment (intended, by design, won't fix, not an issue, false positive, out of scope) and nothing changed. Write what the team accepts: "<pattern> is accepted here because <reason>".
- "skip": too specific to recur, a nit, a question, a thank-you, or bot boilerplate.

Reply with JSON only: {"rules":[{"i":0,"kind":"check|accepted|skip","rule":"one sentence","keywords":["identifier or term", "..."]}]}

{items}
"""


def threads():
    for f in sorted(glob.glob(mem("threads", "*.json"))):
        d = json.load(open(f))
        by_parent = {}
        for c in d["comments"]:
            if c["reply_to"]:
                by_parent.setdefault(c["reply_to"], []).append(c)
        for c in d["comments"]:
            if c["reply_to"] or len(c["body"]) < 40:
                continue
            body = re.split(r"<details><summary>Prompt To Fix", c["body"])[0]
            body = re.sub(r"<a href=\"#\"><img alt=\"(P\d)\"[^>]*></a>", r"\1", body)[:1500]
            replies = [f"  reply by {r['user']}: {r['body'][:400]}" for r in by_parent.get(c["id"], [])]
            yield {"id": c["id"], "pr": d["pr"], "date": c["created"], "path": c["path"], "user": c["user"],
                   "text": f"PR #{d['pr']} {c['path']}\n{c['user']}: {body}\n" + "\n".join(replies)}


def build():
    """Incremental: only comments not processed before go to the model; new rules are appended."""
    rules_path, processed = mem("rules.json"), mem("processed.json")
    done = set(json.load(open(processed))) if os.path.exists(processed) else set()
    items = [it for it in threads() if it["id"] not in done]
    old = json.load(open(rules_path)) if os.path.exists(rules_path) else []
    stamp = time.strftime("%Y%m%d%H%M%S")
    batches = [items[i:i + BATCH] for i in range(0, len(items), BATCH)]
    os.makedirs(mem("batches"), exist_ok=True)

    def run(b):
        n, batch = b
        text = "\n\n".join(f"[{i}] {it['text']}" for i, it in enumerate(batch))
        out, _ = llm.ask(PROMPT.replace("{items}", text), mem("batches", f"{stamp}-b{n:03d}"), model=llm.MEMORY)
        try:
            rows = json.loads(out[out.index("{"):out.rindex("}") + 1])["rules"]
        except ValueError:
            return []
        return [{**batch[r["i"]], "kind": r["kind"], "rule": r["rule"], "keywords": r.get("keywords", [])}
                for r in rows if r.get("kind") in ("check", "accepted") and 0 <= r.get("i", -1) < len(batch)]

    with ThreadPoolExecutor(6) as ex:
        rules = [r for rs in ex.map(run, enumerate(batches)) for r in rs]
    for r in rules:
        r.pop("text", None)
    if llm.DRY_RUN:
        print(len(items), "new comments; dry run: prompts written to", mem("batches"))
        return
    json.dump(old + rules, open(rules_path, "w"), indent=1)
    json.dump(sorted(done | {it["id"] for it in items}), open(processed, "w"))
    print(len(items), "new comments ->", len(rules), "new rules;", len(old) + len(rules), "in total")


def select(created, paths, diff, checks=20, accepted=8):
    """Empty when the repo has no memory yet."""
    if not os.path.exists(mem("rules.json")):
        return ""
    rules = [r for r in json.load(open(mem("rules.json"))) if r["date"] < created]
    areas = {wiki.area_of(p) for p in paths}
    tops = {"/".join(p.split("/")[:2]) for p in paths}
    words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", diff))

    def score(r):
        s = 3 * (wiki.area_of(r["path"]) in areas) + (("/".join(r["path"].split("/")[:2])) in tops)
        return s + sum(1 for k in r["keywords"] for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", k) if w in words)

    def top(kind, n):
        seen, out = set(), []
        for r in sorted((r for r in rules if r["kind"] == kind), key=score, reverse=True):
            key = r["rule"][:60].lower()
            if score(r) > 0 and key not in seen:
                seen.add(key)
                out.append(f"- {r['rule']} (PR #{r['pr']})")
            if len(out) == n:
                break
        return out

    c, a = top("check", checks), top("accepted", accepted)
    return ("Check:\n" + "\n".join(c) if c else "") + ("\n\nAccepted here, do not report:\n" + "\n".join(a) if a else "")
