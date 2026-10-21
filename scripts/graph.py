#!/usr/bin/env python3
"""Repo graph of a commit, Greptile-style: every Swift declaration with its range, enclosing type,
inheritance list, the names it calls and the string literals it uses. Cached per sha in <data>/graph/<sha>.json.
Library: use(data), build(repo, sha), load(sha), enclosing(graph, path, line), callers(worktree, graph, name)."""
import json, os, re, subprocess, sys
from concurrent.futures import ProcessPoolExecutor

DATA = CACHE = None


def use(data):
    """Sets the per-repo data directory (graph, wiki, memory)."""
    global DATA, CACHE
    DATA, CACHE = data, os.path.join(data, "graph")

TYPE_NODES = {"class_declaration", "protocol_declaration"}
MEMBER_NODES = {"function_declaration", "init_declaration", "property_declaration", "subscript_declaration",
                "protocol_function_declaration", "protocol_property_declaration", "deinit_declaration"}

_parser = None


def parser():
    global _parser
    if _parser is None:
        import tree_sitter as t
        import tree_sitter_swift as ts
        _parser = t.Parser(t.Language(ts.language()))
    return _parser


def text(node, src):
    return src[node.start_byte:node.end_byte].decode("utf-8", "replace")


def type_info(node, src):
    kind = src[node.start_byte:node.end_byte].split(b"{", 1)[0].strip().split()
    word = next((w.decode() for w in kind if w in (b"class", b"struct", b"enum", b"actor", b"extension", b"protocol")), "type")
    name_node = node.child_by_field_name("name")
    name = text(name_node, src) if name_node else "?"
    inherits = [text(c, src) for c in node.children if c.type == "inheritance_specifier"]
    return word, name.split("<")[0], inherits


def member_name(node, src):
    if node.type == "init_declaration":
        return "init"
    if node.type == "deinit_declaration":
        return "deinit"
    if node.type == "subscript_declaration":
        return "subscript"
    n = node.child_by_field_name("name")
    if n is None:
        return "?"
    if n.type == "pattern":
        b = n.child_by_field_name("bound_identifier")
        n = b or n
    return text(n, src)


def calls_and_strings(node, src):
    calls, strings, members, types = set(), set(), set(), set()
    stack = [node]
    while stack:
        n = stack.pop()
        if n.type == "call_expression" and n.children:
            callee = n.children[0]
            if callee.type == "navigation_expression":
                suffix = callee.children[-1]
                ident = [c for c in suffix.children if c.type == "simple_identifier"] if suffix.children else []
                if ident:
                    calls.add(text(ident[-1], src))
            elif callee.type == "simple_identifier":
                calls.add(text(callee, src))
        elif n.type == "type_identifier":
            types.add(text(n, src))
        if n.type == "navigation_suffix":
            ident = [c for c in n.children if c.type == "simple_identifier"]
            if ident:
                members.add(text(ident[-1], src))
            if ident and re.search(r"(Key|Keys|Notification|Flag|Event|Defaults|Name)$", text(ident[-1], src)):
                strings.add(text(ident[-1], src))
        elif n.type == "line_string_literal":
            s = text(n, src).strip('"')
            if 3 <= len(s) <= 80 and re.fullmatch(r"[A-Za-z0-9_.\-: ]+", s):
                strings.add(s)
        stack.extend(n.children)
    return sorted(calls), sorted(strings), sorted(members)[:60], sorted(types)[:40]


def index_file(args):
    root, path = args
    try:
        src = open(os.path.join(root, path), "rb").read()
    except OSError:
        return path, []
    return path, index_source(src)


def index_source(src):
    tree = parser().parse(src)
    out = []

    def walk(node, owner):
        for c in node.children:
            if c.type in TYPE_NODES:
                kind, name, inherits = type_info(c, src)
                out.append({"k": kind, "n": name, "t": owner, "s": c.start_point[0] + 1, "e": c.end_point[0] + 1,
                            "i": inherits})
                body = c.child_by_field_name("body")
                if body is not None:
                    walk(body, name)
            elif c.type in MEMBER_NODES:
                calls, strings, members, types = calls_and_strings(c, src)
                sig = text(c, src).split("{", 1)[0].strip().replace("\n", " ")[:200]
                out.append({"k": c.type.replace("_declaration", ""), "n": member_name(c, src), "t": owner,
                            "s": c.start_point[0] + 1, "e": c.end_point[0] + 1, "sig": sig, "c": calls, "str": strings, "m": members, "ty": types})
            elif c.type in ("class_body", "protocol_body", "enum_class_body", "statements"):
                walk(c, owner)

    walk(tree.root_node, None)
    return out


def blob_path(cache, blob):
    return os.path.join(cache, "blobs", blob[:2], f"{blob}.json")


def index_blob(args):
    """Parses one file content (by blob hash) unless an earlier commit already parsed the same content."""
    repo, blob, cache = args
    dest = blob_path(cache, blob)
    if os.path.exists(dest):
        return blob, json.load(open(dest))
    src = subprocess.run(["git", "-C", repo, "cat-file", "blob", blob], capture_output=True).stdout
    decls = index_source(src)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    json.dump(decls, open(dest + ".tmp", "w"))
    os.replace(dest + ".tmp", dest)
    return blob, decls


def tree_blobs(repo, sha):
    rows = subprocess.check_output(["git", "-C", repo, "ls-tree", "-r", sha], text=True).splitlines()
    out = {}
    for r in rows:
        meta, path = r.split("\t", 1)
        if path.endswith(".swift") and "/Derived/" not in path:
            out[path] = meta.split()[2]
    return out


def build(worktree, sha):
    """Graph of a commit. Incremental: only file contents (blobs) never seen before are parsed, like Greptile re-indexing a push."""
    os.makedirs(CACHE, exist_ok=True)
    dest = os.path.join(CACHE, f"{sha}.json")
    if os.path.exists(dest):
        return dest
    blobs = tree_blobs(worktree, sha)
    new = sum(1 for b in set(blobs.values()) if not os.path.exists(blob_path(CACHE, b)))
    with ProcessPoolExecutor(6) as ex:
        parsed = dict(ex.map(index_blob, [(worktree, b, CACHE) for b in set(blobs.values())], chunksize=64))
    decls = {path: parsed[b] for path, b in blobs.items()}
    print(f"graph {sha[:8]}: {len(blobs)} files, {new} parsed, {len(blobs) - new} from cache", file=sys.stderr)
    conformers = {}
    for path, ds in decls.items():
        for d in ds:
            if d["k"] in ("class", "struct", "enum", "actor", "extension"):
                for inh in d.get("i", []):
                    conformers.setdefault(inh.split("<")[0].strip(), []).append([path, d["n"]])
    json.dump({"sha": sha, "files": decls, "conformers": conformers}, open(dest + ".tmp", "w"))
    os.replace(dest + ".tmp", dest)
    return dest


def load(sha):
    return json.load(open(os.path.join(CACHE, f"{sha}.json")))


def enclosing(graph, path, line):
    """Innermost member (or type) declaration covering path:line."""
    best = None
    for d in graph["files"].get(path, []):
        if d["s"] <= line <= d["e"] and (best is None or d["e"] - d["s"] < best["e"] - best["s"]):
            best = d
    return best


def definitions(graph, name):
    return [(p, d) for p, ds in graph["files"].items() for d in ds if d["n"] == name]


def grep(worktree, word, limit=400):
    out = subprocess.run(["git", "-C", worktree, "grep", "-n", "-w", "-I", "--", word, "*.swift", "*.m", "*.h", "*.plist"],
                         capture_output=True, text=True).stdout.splitlines()
    hits = []
    for l in out[:limit]:
        m = re.match(r"(.+?):(\d+):(.*)", l)
        if m:
            hits.append((m.group(1), int(m.group(2)), m.group(3).strip()[:200]))
    return hits


def callers(worktree, graph, name, exclude_path=None, exclude_lines=None):
    """Usage sites of a name with their enclosing declaration."""
    hits = []
    for path, line, code in grep(worktree, name):
        if path == exclude_path and exclude_lines and exclude_lines[0] <= line <= exclude_lines[1]:
            continue
        enc = enclosing(graph, path, line)
        hits.append({"path": path, "line": line, "code": code,
                     "in": f"{enc['t'] + '.' if enc and enc.get('t') else ''}{enc['n']}" if enc else None})
    return hits
