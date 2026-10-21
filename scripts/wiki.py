"""Codebase wiki, Greptile-style: one cached summary per feature area a PR touches, written by a cheap model from the
area's declaration skeleton at the reviewed commit. Cached in <data>/wiki per area skeleton."""
import hashlib, os
import graph, llm

PROMPT = """You write a short internal wiki page for one area of this codebase, for a code reviewer who has never seen it.
From the file list and declaration skeleton below, write 150 to 300 words:
- Purpose: what this area does for the user.
- Main types and their responsibility (one line each, only the important ones).
- State: what it stores and where (UserDefaults, app group, disk, keychain, server), who else reads or writes it.
- Lifecycles and threading: who creates and owns the objects, main actor or background, async tasks, observers.
- Invariants and gotchas a reviewer must keep in mind (ordering, one-shot flags, account switch, feature flags, extensions and other hosts that share code).
Write only what the skeleton supports; say "unknown" rather than guess. Plain text, no preamble.

Area: {area}

{skeleton}
"""


def area_of(path):
    parts = path.split("/")
    depth = 5 if parts[0] == "Packages" else 4
    return "/".join(parts[:min(depth, len(parts) - 1)])


def skeleton(g, area, limit=24000):
    rows = []
    for path in sorted(p for p in g["files"] if p.startswith(area + "/")):
        rows.append(f"## {path}")
        for d in g["files"][path]:
            if d["k"] in ("class", "struct", "enum", "actor", "extension", "protocol"):
                rows.append(f"{d['k']} {d['n']}" + (f": {', '.join(d.get('i', []))}" if d.get("i") else ""))
            elif d.get("sig"):
                rows.append(f"  {d['sig'][:160]}")
    text = "\n".join(rows)
    return text[:limit] + ("\n… (cut)" if len(text) > limit else "")


def page(g, area, sha):
    """Keyed by the area's declaration skeleton: a page is written again only when the area's types or signatures change,
    not on every body edit or commit."""
    wiki_dir = os.path.join(graph.DATA, "wiki")
    os.makedirs(wiki_dir, exist_ok=True)
    skel = skeleton(g, area)
    if not skel:
        return ""
    base = os.path.join(wiki_dir, hashlib.sha1(f"{area}\n{skel}".encode()).hexdigest()[:16])
    text, _ = llm.ask(PROMPT.replace("{area}", area).replace("{skeleton}", skel), base, model=llm.CHEAP)
    return text


def refresh(sha):
    """Every area of a commit; a page is only written again where the area's declarations changed."""
    g = graph.load(sha)
    areas = sorted({area_of(p) for p in g["files"]})
    for a in areas:
        page(g, a, sha)
    print(len(areas), "areas current")
