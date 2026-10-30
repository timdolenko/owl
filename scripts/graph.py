#!/usr/bin/env python3
"""Repo graph of a commit, Greptile-style: every declaration in a language of languages.py with its range, enclosing
type, inheritance list, the names it calls and the string literals it uses. Cached per sha in <data>/graph/<sha>.json.
Library: use(data), build(repo, sha), load(sha), enclosing(graph, path, line), callers(worktree, graph, name)."""
import importlib, json, os, re, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
import languages

DATA = CACHE = None


def use(data):
    """Sets the per-repo data directory (graph, wiki, memory)."""
    global DATA, CACHE
    DATA, CACHE = data, os.path.join(data, "graph")

KIND_WORDS = (b"class", b"struct", b"enum", b"actor", b"extension", b"protocol", b"interface", b"object")
KIND_OF_WORD = {"interface": "protocol", "object": "class"}
IDENTIFIERS = {"simple_identifier", "identifier", "property_identifier", "field_identifier", "type_identifier"}
NOT_NAMES = {"type_arguments", "keyword_argument", "arguments", "argument_list", "value_arguments", "call_suffix",
             "token_tree"}
DECLARATORS = {"variable_declarator", "variable_declaration"}
IMPLICIT_MEMBER_CALLEES = {"prefix_expression"}
NOT_INDEXED = re.compile(r"(^|/)(Derived|node_modules|vendor|Pods|dist|build)/|\.min\.js$")
CODE_GLOBS = [f"*{e}" for e in languages.EXTENSIONS]

_parsers = {}


def parser(lang):
    key = (lang.module, lang.grammar)
    if key not in _parsers:
        import tree_sitter as t
        grammar = getattr(importlib.import_module(lang.module), lang.grammar)
        _parsers[key] = t.Parser(t.Language(grammar()))
    return _parsers[key]


def text(node, src):
    return src[node.start_byte:node.end_byte].decode("utf-8", "replace")


def parent_name(inherited):
    return re.split(r"[<(\[]", inherited)[0].strip()


def type_info(node, src, lang):
    kind = lang.types[node.type]
    if kind == languages.KEYWORD:
        words = src[node.start_byte:node.end_byte].split(b"{", 1)[0].strip().split()
        word = next((w.decode() for w in words if w in KIND_WORDS), "type")
        kind = KIND_OF_WORD.get(word, word)
    name_node = node.child_by_field_name("name") or node.child_by_field_name("type")
    name = text(name_node, src) if name_node else "?"
    return kind, name.split("<")[0], parents(node, src, lang)


def parents(node, src, lang):
    found = [text(n, src) for n in map(node.child_by_field_name, lang.parent_fields) if n]
    for c in node.children:
        if c.type in lang.parents:
            found.append(text(c, src))
        elif c.type in lang.heritage:
            found += heritage_parents(c, src, lang)
    return found


def heritage_parents(node, src, lang):
    found = []
    for c in node.named_children:
        if c.type in lang.heritage:
            found += heritage_parents(c, src, lang)
        elif c.type not in NOT_NAMES:
            found.append(text(c, src))
    return found


def member_name(node, src, lang):
    if node.type in lang.names:
        return lang.names[node.type]
    n = node.child_by_field_name("name") or declared_name(node)
    if n is None:
        return "?"
    if n.type == "pattern":
        b = n.child_by_field_name("bound_identifier")
        n = b or n
    return text(n, src)


def declared_name(node):
    for c in node.named_children:
        if c.type in DECLARATORS:
            return c.child_by_field_name("name") or next((i for i in c.named_children if i.type in IDENTIFIERS), None)
    return None


def callee(call):
    return (call.child_by_field_name("name") or call.child_by_field_name("function")
            or call.child_by_field_name("macro") or call.named_children[0])


def tail_name(node, src):
    """Rightmost identifier of a callee or member access: `fetch` in `self.api.fetch`."""
    while node.type not in IDENTIFIERS:
        kids = [c for c in node.named_children if c.type not in NOT_NAMES]
        if not kids:
            return None
        node = kids[-1]
    return text(node, src)


def calls_and_strings(node, src, lang):
    calls, strings, members, types = set(), set(), set(), set()
    stack = [node]
    while stack:
        n = stack.pop()
        if n.type in lang.calls and n.named_children and callee(n).type not in IMPLICIT_MEMBER_CALLEES:
            name = tail_name(callee(n), src)
            if name:
                calls.add(name)
        elif n.type == "type_identifier":
            types.add(text(n, src))
        if n.type in lang.accesses:
            name = tail_name(n, src)
            if name:
                members.add(name)
            if name and re.search(r"(Key|Keys|Notification|Flag|Event|Defaults|Name)$", name):
                strings.add(name)
        elif n.type in lang.strings:
            s = re.sub(r"^[A-Za-z]*[\"'`]+|[\"'`]+$", "", text(n, src))
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
    return path, index_source(src, path)


def index_source(src, path):
    lang = languages.of(path)
    if lang is None:
        return []
    tree = parser(lang).parse(src)
    out = []

    def walk(node, owner):
        for c in node.children:
            if c.type in lang.types:
                kind, name, inherits = type_info(c, src, lang)
                out.append({"k": kind, "n": name, "t": owner, "s": c.start_point[0] + 1, "e": c.end_point[0] + 1,
                            "i": inherits})
                walk(c.child_by_field_name("body") or c, name)
            elif c.type in lang.members:
                calls, strings, members, types = calls_and_strings(c, src, lang)
                sig = text(c, src).split(lang.body_opener, 1)[0].strip().replace("\n", " ")[:200]
                out.append({"k": lang.members[c.type], "n": member_name(c, src, lang), "t": owner,
                            "s": c.start_point[0] + 1, "e": c.end_point[0] + 1, "sig": sig, "c": calls, "str": strings, "m": members, "ty": types})
            elif c.type in lang.containers:
                walk(c, owner)

    walk(tree.root_node, None)
    return out


def blob_path(cache, blob):
    return os.path.join(cache, "blobs", blob[:2], f"{blob}.json")


def index_blob(args):
    """Parses one file content (by blob hash) unless an earlier commit already parsed the same content."""
    repo, blob, path, cache = args
    dest = blob_path(cache, blob)
    if os.path.exists(dest):
        return blob, json.load(open(dest))
    src = subprocess.run(["git", "-C", repo, "cat-file", "blob", blob], capture_output=True).stdout
    decls = index_source(src, path)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    json.dump(decls, open(dest + ".tmp", "w"))
    os.replace(dest + ".tmp", dest)
    return blob, decls


def tree_blobs(repo, sha):
    rows = subprocess.check_output(["git", "-C", repo, "ls-tree", "-r", sha], text=True).splitlines()
    out = {}
    for r in rows:
        meta, path = r.split("\t", 1)
        if path.endswith(languages.EXTENSIONS) and not NOT_INDEXED.search(path):
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
        paths = {b: path for path, b in blobs.items()}
        parsed = dict(ex.map(index_blob, [(worktree, b, path, CACHE) for b, path in paths.items()], chunksize=64))
    decls = {path: parsed[b] for path, b in blobs.items()}
    print(f"graph {sha[:8]}: {len(blobs)} files, {new} parsed, {len(blobs) - new} from cache", file=sys.stderr)
    conformers = {}
    for path, ds in decls.items():
        for d in ds:
            if d["k"] in ("class", "struct", "enum", "actor", "extension"):
                for inh in d.get("i", []):
                    conformers.setdefault(parent_name(inh), []).append([path, d["n"]])
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
    out = subprocess.run(["git", "-C", worktree, "grep", "-n", "-w", "-I", "--", word, *CODE_GLOBS, "*.m", "*.h", "*.plist"],
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
