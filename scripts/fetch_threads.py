"""Review comment threads (bots and humans, with replies) of the repo's past PRs, for memory, via `gh`.
Writes <data>/memory/threads/<pr>.json."""
import json, os, subprocess, time
from concurrent.futures import ThreadPoolExecutor
import graph


def out_dir():
    return os.path.join(graph.DATA, "memory", "threads")


def fetch(nwo, pr, created):
    dest = f"{out_dir()}/{pr}.json"
    if os.path.exists(dest):
        return
    for attempt in range(3):
        r = subprocess.run(["gh", "api", "--paginate", f"repos/{nwo}/pulls/{pr}/comments?per_page=100"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            rows = [{"id": c["id"], "reply_to": c.get("in_reply_to_id"), "user": c["user"]["login"], "path": c["path"],
                     "line": c.get("line") or c.get("original_line"), "created": c["created_at"], "body": c["body"][:4000],
                     "hunk": c.get("diff_hunk", "")[-1500:]} for c in json.loads(r.stdout.replace("][", ","))]
            json.dump({"pr": pr, "created": created, "comments": rows}, open(dest, "w"))
            return
        time.sleep(20)


def updated_since(nwo, date, limit=1000):
    """PRs with review activity since `date`: their threads are fetched again, whole."""
    rows = json.loads(subprocess.check_output(["gh", "pr", "list", "-R", nwo, "--state", "all", "--limit", str(limit),
                                               "--search", f"updated:>={date}", "--json", "number,createdAt"], text=True))
    for r in rows:
        if os.path.exists(f"{out_dir()}/{r['number']}.json"):
            os.remove(f"{out_dir()}/{r['number']}.json")
    return {r["number"]: r["createdAt"] for r in rows}


def run(nwo, since):
    os.makedirs(out_dir(), exist_ok=True)
    prs = updated_since(nwo, since)
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda p: fetch(nwo, p, prs[p]), sorted(prs)))
    print(len(prs), "PRs,", len(os.listdir(out_dir())), "fetched")
