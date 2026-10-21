#!/usr/bin/env python3
"""Greptile-style review of one PR: graph context packs + wiki + team memory -> one reviewer per file group ->
one whole-PR pass + single-mode reviewers -> dedupe (or filter). Writes <out>/findings.md (F-lines) and
<out>/findings.raw.md (every candidate). run(args) takes the namespace reptile.py builds."""
import json, os, re, subprocess, time
from concurrent.futures import ThreadPoolExecutor
import graph, llm, pack, wiki

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPTS = os.path.join(ROOT, "prompts")
MODES = os.path.join(ROOT, "modes")
MAX_UNITS = 8
UNIT_TURNS = 30


def git(wt, *args):
    return subprocess.run(["git", "-C", wt, *args], capture_output=True, text=True, errors="replace").stdout


def units_of(files):
    """Each sizeable code file is its own unit; small ones are grouped by directory; at most MAX_UNITS units."""
    code = files
    big = [[f] for f in code if f["add"] + f["del"] >= 8]
    small = {}
    for f in code:
        if f["add"] + f["del"] < 8:
            small.setdefault(os.path.dirname(f["path"]), []).append(f)
    units = big + [g[i:i + 4] for g in small.values() for i in range(0, len(g), 4)]
    units.sort(key=lambda u: -sum(f["add"] + f["del"] for f in u))
    while len(units) > MAX_UNITS:
        tail = units.pop()
        units[-1] = units[-1] + tail
    return units


def findings_lines(text, base=""):
    """F-lines of a reviewer answer; an answer with neither F-lines nor the explicit NONE is a failed call, never zero findings."""
    lines = [l.strip() for l in text.splitlines() if re.match(r"^\s*F\d*\s*\|", l)]
    if not lines and not re.search(r"^\s*`?(NONE|NO_FINDINGS)`?\s*$", text, re.M):
        raise llm.CallFailed(f"{base}: answer has no finding lines and no NONE: {text[:200]!r}")
    return lines


def notes(args, name):
    """The repo's own reviewer notes: $REPTILE_NOTES/<name>.md, else <repo>/.reptile/notes/<name>.md."""
    path = os.path.join(os.environ.get("REPTILE_NOTES") or os.path.join(args.repo, ".reptile", "notes"), f"{name}.md")
    return open(path).read() if os.path.exists(path) else ""


PASSED = re.compile(r"^\s*`?(SAFE|NOT CONFIRMED|out-of-scope)\s*\|")


def passed_lines(text, source):
    """SAFE, NOT CONFIRMED and out-of-scope lines: what a reviewer checked, for the summary."""
    return [f"{l.strip().strip('`')} | {source}" for l in text.splitlines() if PASSED.match(l)]


def conversation(args, cap=30000):
    """The PR's comments and threads so far: points already raised, answered or settled are not raised again."""
    path = getattr(args, "conversation", "")
    text = open(path).read().strip() if path and os.path.exists(path) else ""
    return ["\n## Existing PR conversation (already raised or settled: do not repeat)\n", text[:cap]] if text else []


def unit_prompt(args, unit, packs_dir, wiki_pages, rules, facts):
    paths = [f["path"] for f in unit]
    diff = git(args.worktree, "diff", f"{args.base}..{args.sha}", "--", *paths)
    parts = [open(f"{PROMPTS}/file.md").read(), "\n## Pull request\n", open(args.context).read()[:12000], *conversation(args),
             "\n## Files to review\n", "\n".join(f"- {p}" for p in paths), "\n## Diff of these files\n```diff", diff[:60000], "```"]
    if not args.no_packs:
        parts += ["\n## Context packs (from the repository graph at the head commit)\n"]
        parts += [open(f"{packs_dir}/{f['id']}.md").read() for f in unit if f["id"] and os.path.exists(f"{packs_dir}/{f['id']}.md")]
    if notes(args, "all"):
        parts += ["\n## Codebase notes\n", notes(args, "all")]
    pages = {wiki.area_of(p) for p in paths}
    if wiki_pages:
        parts += ["\n## Codebase wiki\n"] + [f"### {a}\n{wiki_pages[a]}" for a in pages if wiki_pages.get(a)]
    if rules:
        parts += ["\n## Team rules from earlier reviews\n", rules]
    if facts.strip():
        parts += ["\n## Facts about the rest of the diff\n", facts[:6000]]
    return "\n".join(parts)


def mode_lines(args, diff, packs_dir, mode, passed):
    """One of the skill's single-mode reviewers, given the clone's context packs. clean-code catches the small suggestion
    comments the clone misses; regressions compares against the base versions the packs hold."""
    rules = [open(f"{MODES}/common.md").read(), open(f"{MODES}/{mode}.md").read()]
    rules += [f"\n## Codebase notes\n\n{n}" for n in (notes(args, "all"), notes(args, mode)) if n]
    packs = [open(f"{packs_dir}/{f}").read() for f in sorted(os.listdir(packs_dir))] if os.path.isdir(packs_dir) else []
    prompt = "\n".join(rules + [
        f"\n## This run\n\nMode: {mode}\nBase commit: {args.base}\nThe worktree is at the PR's head commit; read any file you need.\n",
        "\n## Pull request\n", open(args.context).read()[:12000], *conversation(args), "\n## Diff\n```diff", diff[:90000], "```",
        "\n## Context packs\n", "\n".join(packs)[:60000]])
    text, _ = llm.ask(prompt, f"{args.out}/{mode}", model=llm.MODEL, cwd=args.worktree, tools=True, max_turns=UNIT_TURNS)
    found = [l.strip() for l in text.splitlines() if re.match(r"^\s*[^|]+?\.\w+:\d+(-\d+)?\s*\|", l)]
    if not found and "NO_FINDINGS" not in text:
        raise llm.CallFailed(f"{mode} answered without findings or NO_FINDINGS: {text[:200]!r}")
    passed.extend(passed_lines(text, mode))
    return [f"F | {l} | {mode}" for l in found]


def dedupe(args, raw):
    """Merges findings with the same root cause; drops only repeats of the PR conversation (the filter dropped real hits)."""
    text, _ = llm.ask("\n".join([open(f"{PROMPTS}/dedupe.md").read(), *conversation(args), "\n## Candidate findings\n", raw]),
                      f"{args.out}/dedupe",
                      model=llm.MODEL)
    kept = [l for l in text.splitlines() if re.match(r"^F\d+ \|", l)]
    if not kept:
        raise llm.CallFailed(f"dedupe answered without findings: {text[:200]}")
    return "\n".join(kept)


class Steps:
    """Wall time of each step, for the review page."""
    def __init__(self, out):
        self.path, self.rows, self.t = f"{out}/steps.json", [], time.time()

    def done(self, name):
        now = time.time()
        self.rows.append({"step": name, "seconds": round(now - self.t, 1)})
        self.t = now
        json.dump(self.rows, open(self.path, "w"))


def run(args):
    os.makedirs(args.out, exist_ok=True)
    start, steps = time.time(), Steps(args.out)
    files = pack.main(args.worktree, args.base, args.sha, args.out)
    steps.done("graph + packs")
    facts = open(f"{args.out}/facts.md").read()
    g = graph.load(args.sha)
    wiki_pages = {}
    if not args.no_wiki:
        areas = sorted({wiki.area_of(f["path"]) for f in files if f["path"].endswith(".swift")})[:6]
        with ThreadPoolExecutor(4) as ex:
            wiki_pages = dict(zip(areas, ex.map(lambda a: wiki.page(g, a, args.sha), areas)))
        json.dump(wiki_pages, open(f"{args.out}/wiki.json", "w"))
    steps.done("wiki")
    rules = ""
    if not args.no_memory:
        import memory
        rules = memory.select(args.created, [f["path"] for f in files], git(args.worktree, "diff", f"{args.base}..{args.sha}"))
        open(f"{args.out}/rules.md", "w").write(rules)
    steps.done("memory")
    units, passed = units_of(files), []
    os.makedirs(f"{args.out}/units", exist_ok=True)

    def review_unit(i_unit):
        i, unit = i_unit
        text, _ = llm.ask(unit_prompt(args, unit, f"{args.out}/packs", wiki_pages, rules, facts), f"{args.out}/units/u{i}",
                          model=llm.MODEL, cwd=args.worktree, tools=True, max_turns=UNIT_TURNS)
        passed.extend(passed_lines(text, f"unit{i}"))
        return [f"{l} | unit{i}" for l in findings_lines(text, f"unit{i}")]

    diff = git(args.worktree, "diff", f"{args.base}..{args.sha}")
    modes = [m for m in args.modes.split(",") if m]
    with ThreadPoolExecutor(3 + len(modes)) as ex:
        by_mode = [ex.submit(mode_lines, args, diff, f"{args.out}/packs", m, passed) for m in modes]
        per_file = [l for ls in ex.map(review_unit, enumerate(units)) for l in ls]
        steps.done("per-file units")
        stat = git(args.worktree, "diff", "--stat", f"{args.base}..{args.sha}")
        whole_prompt = "\n".join([open(f"{PROMPTS}/whole.md").read(), "\n## Pull request\n", open(args.context).read()[:12000],
                                  *conversation(args),
                                  "\n## Diffstat\n```", stat[-6000:], "```", "\n## Full diff\n```diff", diff[:90000], "```",
                                  "\n## Facts\n", facts[:8000], "\n## Team rules\n", rules or "(none)",
                                  "\n## Codebase notes\n", notes(args, "all") or "(none)",
                                  "\n## Per-file findings already raised\n", "\n".join(per_file) or "(none)"])
        text, _ = llm.ask(whole_prompt, f"{args.out}/whole", model=llm.MODEL, cwd=args.worktree, tools=True, max_turns=UNIT_TURNS)
        steps.done("whole-PR pass")
        candidates = per_file + [f"{l} | whole" for l in findings_lines(text, "whole")]
        passed.extend(passed_lines(text, "whole"))
        candidates += [l for f in by_mode for l in f.result()]
        steps.done("mode reviewers")
    open(f"{args.out}/passed.md", "w").write("".join(f"{l}\n" for l in dict.fromkeys(passed)))
    open(f"{args.out}/findings.raw.md", "w").write(
        "\n".join(f"F{n} | " + re.sub(r"^\s*F\d*\s*\|\s*", "", l) for n, l in enumerate(candidates, 1)) or "NO_FINDINGS")
    if not args.filter and not args.no_dedupe and candidates:
        final = dedupe(args, open(f"{args.out}/findings.raw.md").read())
    elif not args.filter or not candidates:
        final = open(f"{args.out}/findings.raw.md").read()
    else:
        fp = "\n".join([open(f"{PROMPTS}/filter.md").read(), "\n## Pull request\n", open(args.context).read()[:6000],
                        "\n## Diff\n```diff", diff[:60000], "```", "\n## Candidate findings\n", open(f"{args.out}/findings.raw.md").read()])
        final, _ = llm.ask(fp, f"{args.out}/filter", model=llm.MODEL)
        kept = [l for l in final.splitlines() if re.match(r"^F\d+ \|", l)]
        if not kept and "NO_FINDINGS" not in final:
            raise llm.CallFailed(f"filter answered without findings or NO_FINDINGS: {final[:200]}")
        final = "\n".join(kept) or "NO_FINDINGS"
    steps.done("filter" if args.filter else "dedupe")
    open(f"{args.out}/findings.md", "w").write(final + "\n")
    count = sum(1 for l in final.splitlines() if re.match(r"^F\d+ \|", l))
    open(f"{args.out}/count", "w").write(f"{count}\n")
    json.dump({"base": args.base, "head": args.sha, "engine": llm.ENGINE, "dry_run": llm.DRY_RUN, "units": len(units),
               "modes": modes, "candidates": len(candidates), "kept": count, "seconds": int(time.time() - start),
               "cost_usd": llm.cost_of(args.out)}, open(f"{args.out}/meta.json", "w"), indent=1)
    return count

