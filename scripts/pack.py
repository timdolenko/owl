#!/usr/bin/env python3
"""Context packs, Greptile-style: for every declaration a PR changes, the code around it that a reviewer needs.
  main(worktree, base, sha, out)     writes <out>/packs/<file-id>.md, facts.md, files.json
Packs are built for Swift only; other source files are reviewed from the diff without a pack.
Per changed symbol: base version, callees, callers / usage sites, other users of the same keys and events,
sibling implementations (same protocol), same-named functions elsewhere."""
import json, os, re, subprocess
import graph

SKIP_NAMES = {"body", "init", "id", "view", "value", "count", "name", "title", "type", "data", "state", "error", "result",
              "description", "content", "text", "url", "image", "action", "handle", "update", "run", "start", "stop", "load",
              "reset", "make", "build", "configure", "setup", "isEnabled", "isEmpty", "subscript", "deinit", "?"}
CODE_EXT = (".swift", ".m", ".h")
NOT_REVIEWED = re.compile(r"(\.lock|-lock\.json|lock\.yaml|\.resolved|\.pbxproj|\.svg|\.snap|\.min\.js|\.map)$"
                          r"|(^|/)(vendor|node_modules|Pods|Carthage|dist|build|Derived|xcuserdata)/")
SYMBOL_CAP, FILE_CAP = 5000, 24000


def git(wt, *args):
    return subprocess.run(["git", "-C", wt, *args], capture_output=True, text=True, errors="replace").stdout


def changed_files(wt, base, sha):
    files = []
    for line in git(wt, "diff", "--numstat", f"{base}..{sha}").splitlines():
        a, d, path = line.split("\t", 2)
        if "=>" in path:
            path = re.sub(r"\{.*? => (.*?)\}", r"\1", path).split(" => ")[-1]
        files.append({"path": path, "add": int(a) if a != "-" else 0, "del": int(d) if d != "-" else 0})
    return files


def hunks(wt, base, sha, path):
    """Changed line ranges in the head and in the base."""
    head, old = [], []
    for line in git(wt, "diff", "-U0", f"{base}..{sha}", "--", path).splitlines():
        m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
        if m:
            os_, oc, ns, nc = int(m.group(1)), int(m.group(2) or 1), int(m.group(3)), int(m.group(4) or 1)
            if nc:
                head.append((ns, ns + nc - 1))
            if oc:
                old.append((os_, os_ + oc - 1))
    return head, old


def overlapping(decls, ranges):
    out = []
    for lo, hi in ranges:
        best = None
        for d in decls:
            if d["s"] <= hi and lo <= d["e"] and d["k"] not in ("class", "struct", "enum", "actor", "extension", "protocol"):
                if best is None or d["e"] - d["s"] < best["e"] - best["s"]:
                    best = d
        if best is None:
            best = next((d for d in decls if d["s"] <= lo <= d["e"]), None)
        if best is not None and best not in out:
            out.append(best)
    return out


class Index:
    def __init__(self, g):
        self.g = g
        self.by_name = {}
        for path, ds in g["files"].items():
            for d in ds:
                self.by_name.setdefault(d["n"], []).append((path, d))

    def owner_protocols(self, path, owner):
        protos = set()
        for p, d in self.by_name.get(owner, []):
            if d["k"] in ("class", "struct", "enum", "actor", "extension"):
                protos.update(i.split("<")[0].strip() for i in d.get("i", []))
        return protos


def lines_of(wt, sha, path, s, e):
    src = git(wt, "show", f"{sha}:{path}").splitlines()
    return "\n".join(src[s - 1:e])


def base_version(wt, base, path, d):
    src = git(wt, "show", f"{base}:{path}")
    if not src:
        return "(file is new in this PR)"
    for b in graph.index_source(src.encode()):
        if b["n"] == d["n"] and b.get("t") == d.get("t") and b["k"] == d["k"]:
            body = src.splitlines()[b["s"] - 1:b["e"]]
            return "\n".join(body[:80]) + ("\n… (cut)" if len(body) > 80 else "")
    return "(no declaration with this name in the base: new symbol)"


def usage_sites(wt, ix, path, d, cut):
    name = d["n"]
    if name in SKIP_NAMES or len(name) < 3:
        if not d.get("t"):
            return []
        name = d["t"]
    hits = graph.callers(wt, ix.g, name, exclude_path=path, exclude_lines=(d["s"], d["e"]))
    if d.get("t") and len(hits) > 40:
        owner_files = {p for p, x in ix.by_name.get(d["t"], [])}
        mention = set(git(wt, "grep", "-l", "-w", d["t"], "--", "*.swift").split())
        hits = [h for h in hits if h["path"] in mention or h["path"] in owner_files]
    if len(hits) > 18:
        cut.append(f"{d['n']}: {len(hits) - 18} more usage sites")
    return hits[:18]


def callees(ix, d, path, cut):
    out = []
    for name in d.get("c", []):
        if name in SKIP_NAMES or len(name) < 3:
            continue
        defs = [(p, x) for p, x in ix.by_name.get(name, []) if x["k"] not in ("class", "struct", "enum", "protocol", "extension")]
        if not defs or len(defs) > 6:
            continue
        defs.sort(key=lambda px: (px[1].get("t") != d.get("t"), px[0] != path))
        p, x = defs[0]
        out.append(f"- `{(x.get('t') or '') + '.' if x.get('t') else ''}{x['n']}` {p}:{x['s']}  `{x.get('sig', '')}`")
    if len(out) > 14:
        cut.append(f"{d['n']}: {len(out) - 14} more callees")
    return out[:14]


def shared_state(wt, path, d, cut):
    out = []
    for key in d.get("str", [])[:8]:
        hits = [h for h in graph.grep(wt, key, limit=60) if h[0] != path]
        if 0 < len(hits) <= 40:
            out.append(f"- `{key}` also used at: " + "; ".join(f"{p}:{l} `{c[:90]}`" for p, l, c in hits[:6])
                       + (f" (+{len(hits) - 6} more)" if len(hits) > 6 else ""))
    return out


def siblings(ix, path, d):
    if not d.get("t") or d["n"] in ("?",):
        return []
    protos = ix.owner_protocols(path, d["t"])
    out = []
    for proto in sorted(protos)[:6]:
        for cpath, ctype in ix.g["conformers"].get(proto, [])[:40]:
            if ctype == d["t"]:
                continue
            for p, x in ix.by_name.get(d["n"], []):
                if p == cpath and x.get("t") == ctype:
                    out.append(f"- `{ctype}.{x['n']}` ({proto}) {p}:{x['s']}  `{x.get('sig', '')}`")
    same = [(p, x) for p, x in ix.by_name.get(d["n"], []) if x.get("t") != d.get("t") and x["k"] == d["k"]]
    if d["n"] not in SKIP_NAMES and 0 < len(same) <= 8:
        out += [f"- same name in `{x.get('t')}`: {p}:{x['s']}  `{x.get('sig', '')}`" for p, x in same
                if not any(f"{p}:{x['s']}" in o for o in out)]
    return out[:12]


def enum_cases(wt, sha, ix, type_name):
    defs = [(p, x) for p, x in ix.by_name.get(type_name.split(".")[-1], []) if x["k"] == "enum"]
    if not defs or len(defs) > 2:
        return None
    p, x = defs[0]
    body = lines_of(wt, sha, p, x["s"], min(x["e"], x["s"] + 24))
    cases = [l.strip() for l in body.splitlines() if l.strip().startswith("case ")]
    return f"- enum `{x.get('t') + '.' if x.get('t') else ''}{x['n']}` ({p}:{x['s']}): " + " ".join(cases)[:400] if cases else None


def types_used(wt, sha, ix, d, cut):
    out, seen = [], set()
    for m in d.get("m", []):
        if m in SKIP_NAMES or len(m) < 3:
            continue
        props = [(p, x) for p, x in ix.by_name.get(m, []) if x["k"] == "property"]
        if 1 <= len(props) <= 3:
            p, x = props[0]
            out.append(f"- property `{x.get('t') + '.' if x.get('t') else ''}{x['n']}`: `{x.get('sig', '')[:140]}` ({p}:{x['s']})")
            for t in re.findall(r"\b([A-Z][A-Za-z0-9_]*(?:\.[A-Z][A-Za-z0-9_]*)?)", x.get("sig", "")):
                seen.add(t)
    seen.update(d.get("ty", []))
    for t in sorted(seen)[:20]:
        row = enum_cases(wt, sha, ix, t)
        if row:
            out.append(row)
    if len(out) > 16:
        cut.append(f"{d['n']}: {len(out) - 16} more types used")
    return out[:16]


def symbol_pack(wt, base, sha, ix, path, d, cut):
    title = f"{d['t'] + '.' if d.get('t') else ''}{d['n']}"
    parts = [f"### `{title}` ({d['k']}, {path}:{d['s']}-{d['e']})", f"`{d.get('sig', '')}`"]
    parts += ["", "Base version:", "```swift", base_version(wt, base, path, d), "```"]
    for label, rows in (("Calls (definitions)", callees(ix, d, path, cut)),
                        ("Usage sites (callers and references)", [f"- {h['path']}:{h['line']} in `{h['in']}`: `{h['code']}`"
                                                                  for h in usage_sites(wt, ix, path, d, cut)]),
                        ("Properties and enums it uses", types_used(wt, sha, ix, d, cut)),
                        ("Other users of the same keys, events and constants", shared_state(wt, path, d, cut)),
                        ("Sibling implementations and same-named functions", siblings(ix, path, d))):
        if rows:
            parts += ["", f"{label}:"] + rows
    out = "\n".join(parts)
    if len(out) > SYMBOL_CAP:
        cut.append(f"{title}: pack cut from {len(out)} chars")
        out = out[:SYMBOL_CAP] + "\n… (cut)"
    return out


def removed_symbols(wt, base, path, old_ranges):
    src = git(wt, "show", f"{base}:{path}")
    if not src:
        return []
    return overlapping(graph.index_source(src.encode()), old_ranges)


def l10n_facts(wt, base, sha, path):
    """New or changed xcstrings keys and how many locales each has in the head."""
    try:
        head = json.loads(git(wt, "show", f"{sha}:{path}") or "{}").get("strings", {})
        old = json.loads(git(wt, "show", f"{base}:{path}") or "{}").get("strings", {})
    except ValueError:
        return []
    locales = max((len(v.get("localizations", {})) for v in head.values()), default=0)
    rows = []
    for k, v in head.items():
        if k not in old or v != old.get(k):
            n = len(v.get("localizations", {}))
            state = "new" if k not in old else "changed"
            rows.append(f"- {path}: {state} key `{k[:70]}` has {n} of {locales} locales")
    for k in old:
        if k not in head:
            rows.append(f"- {path}: removed key `{k[:70]}`")
    return rows[:60]


def main(wt, base, sha, out):
    os.makedirs(f"{out}/packs", exist_ok=True)
    graph.build(wt, sha)
    ix = Index(graph.load(sha))
    files, facts = [], []
    for i, f in enumerate(changed_files(wt, base, sha)):
        path = f["path"]
        if path.endswith(".xcstrings"):
            facts += l10n_facts(wt, base, sha, path)
            continue
        binary = f["add"] == f["del"] == 0
        if not path.endswith(CODE_EXT) and not binary and not NOT_REVIEWED.search(path):
            files.append({**f, "id": None, "symbols": 0, "cut": []})
            continue
        if not path.endswith(CODE_EXT):
            facts.append(f"- non-code file changed: {path} (+{f['add']} -{f['del']})")
            continue
        head_r, old_r = hunks(wt, base, sha, path)
        cut, parts = [], []
        decls = ix.g["files"].get(path, [])
        for d in overlapping(decls, head_r):
            parts.append(symbol_pack(wt, base, sha, ix, path, d, cut))
        head_names = {(d.get("t"), d["n"]) for d in decls}
        for d in removed_symbols(wt, base, path, old_r):
            if (d.get("t"), d["n"]) not in head_names:
                hits = graph.callers(wt, ix.g, d["n"]) if d["n"] not in SKIP_NAMES else []
                parts.append(f"### REMOVED `{d.get('t') or ''}.{d['n']}` (was {path}:{d['s']}-{d['e']} in the base)\n"
                             f"Remaining references in the head: " + ("; ".join(f"{h['path']}:{h['line']}" for h in hits[:10]) or "none"))
        text = "\n\n".join(parts)
        if len(text) > FILE_CAP:
            cut.append(f"file pack cut from {len(text)} chars")
            text = text[:FILE_CAP] + "\n… (cut)"
        fid = f"{i:02d}-" + re.sub(r"[^A-Za-z0-9]+", "-", os.path.basename(path))[:50]
        open(f"{out}/packs/{fid}.md", "w").write(f"# Context pack: {path}\n\n{text}\n" + (f"\nCut: {'; '.join(cut)}\n" if cut else ""))
        files.append({**f, "id": fid, "symbols": text.count("\n### "), "cut": cut})
    open(f"{out}/facts.md", "w").write("\n".join(facts) + "\n")
    json.dump(files, open(f"{out}/files.json", "w"), indent=1)
    return files
