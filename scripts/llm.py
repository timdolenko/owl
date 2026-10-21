"""One model call through Claude Code or Codex CLI, with its prompt, raw output and text saved next to each other
for cost and audit."""
import json, os, re, shlex, subprocess, tempfile, time

LIMIT = re.compile(r"rate.?limit|\b429\b|quota|overloaded|usage limit|temporarily limiting|Proxy not running|ECONNREFUSED|socket hang up", re.I)
API_ERROR = re.compile(r"^\s*API Error\b", re.I)
MAX_WAIT = 4 * 3600
CALL_TIMEOUT = int(os.environ.get("REPTILE_CALL_TIMEOUT", 3600))
DRY = "(dry run: no model was called)\nNONE\nNO_FINDINGS"


class CallFailed(RuntimeError):
    pass

ENGINE = os.environ.get("REPTILE_ENGINE", "claude")
MODEL = os.environ.get("REPTILE_MODEL", "claude-opus-5-5")
CHEAP = os.environ.get("REPTILE_CHEAP_MODEL", "claude-haiku-5-5")
MEMORY = os.environ.get("REPTILE_MEMORY_MODEL", "claude-sonnet-5-5")
DRY_RUN = False


def ask(prompt, base, model=None, cwd=None, tools=False):
    """Returns (text, cost). Files: <base>.prompt, <base>.claude.json or .codex.jsonl, <base>.txt.
    Cached: an existing .txt is reused."""
    if os.path.exists(base + ".txt") and os.path.getsize(base + ".txt"):
        cached = open(base + ".txt").read()
        if not API_ERROR.search(cached):
            return cached, 0.0
        os.remove(base + ".txt")
    open(base + ".prompt", "w").write(prompt)
    if DRY_RUN:
        return DRY, 0.0
    call = codex_call if ENGINE == "codex" else claude_call
    waited, delay, failures = 0, 60, 0
    while True:
        text, cost, out = call(prompt, base, model or MODEL, cwd or tempfile.gettempdir(), tools)
        if text is not None:
            open(base + ".txt", "w").write(text)
            return text, cost
        open(base + ".err", "a").write(f"--- {time.ctime()}\n{out[-3000:]}\n")
        if LIMIT.search(out) and waited < MAX_WAIT:
            time.sleep(delay)
            waited += delay
            delay = min(delay * 2, 900)
            continue
        failures += 1
        if failures >= 3:
            raise CallFailed(f"{base}: no answer after {failures} tries")


def claude_call(prompt, base, model, cwd, tools):
    """`claude -p` with read-only tools; REPTILE_CLAUDE_CMD replaces the `claude` prefix (a wrapper or proxy)."""
    args = shlex.split(os.environ.get("REPTILE_CLAUDE_CMD", "claude"))
    args += ["-p", prompt, "--model", model, "--output-format", "json", "--dangerously-skip-permissions"]
    args += ["--disallowedTools", "Edit", "Write", "NotebookEdit", "Agent", "WebFetch", "WebSearch"] if tools else ["--tools", ""]
    try:
        r = subprocess.run(args, capture_output=True, text=True, cwd=cwd, timeout=CALL_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, 0.0, f"timed out after {CALL_TIMEOUT}s"
    out = r.stdout + "\n" + r.stderr
    line = next((l for l in out.splitlines() if l.startswith("{") and '"result"' in l), None)
    res = json.loads(line) if line else {}
    text = res.get("result", "") or ""
    if line and text.strip() and not res.get("is_error") and not API_ERROR.search(text):
        open(base + ".claude.json", "w").write(line)
        return text, res.get("total_cost_usd", 0.0), out
    return None, 0.0, text or out


def codex_call(prompt, base, model, cwd, tools):
    """`codex exec` in a read-only sandbox; the model is REPTILE_CODEX_MODEL or Codex's default. No cost report."""
    last = base + ".last.txt"
    args = ["codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral", "-C", cwd,
            "--json", "--output-last-message", last]
    if os.environ.get("REPTILE_CODEX_MODEL"):
        args += ["--model", os.environ["REPTILE_CODEX_MODEL"]]
    if os.path.exists(last):
        os.remove(last)
    try:
        r = subprocess.run(args + ["-"], input=prompt, capture_output=True, text=True, timeout=CALL_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, 0.0, f"timed out after {CALL_TIMEOUT}s"
    open(base + ".codex.jsonl", "w").write(r.stdout)
    text = open(last).read() if os.path.exists(last) else ""
    if r.returncode == 0 and text.strip():
        return text, 0.0, ""
    return None, 0.0, r.stdout[-2000:] + "\n" + r.stderr


def cost_of(dir_):
    """USD of every Claude call under dir_; None for Codex, which reports no cost."""
    if ENGINE == "codex":
        return None
    total = 0.0
    for root, _, files in os.walk(dir_):
        for f in files:
            if f.endswith(".claude.json"):
                try:
                    total += json.load(open(os.path.join(root, f))).get("total_cost_usd", 0.0)
                except ValueError:
                    pass
    return total
