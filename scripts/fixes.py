"""Earlier Owl rounds on one PR as one markdown file: what each round fixed (with the verifier's fix and the commit),
what it verified and left unfixed, and what its verifiers rejected. Fed to the next round's fix-delta reviewer, the
challenge step and the verifier's appeal."""
import json, os, re

NOT_FIXED = "Verified as valid, but not fixed:"


def load(path, default):
    return json.load(open(path)) if os.path.exists(path) else default


def round_text(run):
    lines = {m.group(1): l for l in open(f"{run}/findings.md").read().splitlines() if (m := re.match(r"^(F\d+) \|", l))}
    verdicts, posted = load(f"{run}/verdicts.json", {}), load(f"{run}/posted.json", {})
    fixed, declined = posted.get("fixed", {}), posted.get("declined", {})
    out = [f"### Round {os.path.basename(run.rstrip('/'))}"]
    out += [f"- FIXED in {x['sha'][:10]}: {lines.get(i, i)}\n  Verifier fix: {verdicts.get(i, {}).get('fix', '')}\n  Fixer: {x['what']}"
            for i, x in fixed.items()]
    out += [f"- VERIFIED, NOT FIXED: {lines.get(i, i)}\n  Verifier fix: {verdicts.get(i, {}).get('fix', '')}\n  Why: {why[len(NOT_FIXED):].strip()}"
            for i, why in declined.items() if why.startswith(NOT_FIXED)]
    out += [f"- REJECTED: {lines.get(i, i)}\n  Verifier: {why}" for i, why in declined.items() if not why.startswith(NOT_FIXED)]
    return "\n".join(out)


def text(runs):
    return "\n\n".join(round_text(r) for r in runs if os.path.exists(f"{r}/findings.md"))


def run(args):
    body = text(args.runs)
    open(args.out, "w").write(f"## Earlier Owl rounds on this PR\n\n{body}\n" if body else "")
    print(args.out)
