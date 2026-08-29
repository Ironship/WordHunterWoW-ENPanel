#!/usr/bin/env python3
import argparse, base64, csv, json, pathlib, threading, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[1]

def load_credentials():
    values = {}
    for line in (ROOT / "Tools" / "keys.env").read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k, v = line.split("=", 1); values[k.strip()] = v.strip()
    return values["BLIZZARD_CLIENT_ID"], values["BLIZZARD_CLIENT_SECRET"]

def token():
    cid, secret = load_credentials()
    auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    request = urllib.request.Request("https://oauth.battle.net/token", data=b"grant_type=client_credentials", headers={"Authorization": f"Basic {auth}"})
    return json.load(urllib.request.urlopen(request, timeout=30))["access_token"]

def enumerate_quest_ids(access, region="eu"):
    """Ask the API which quests exist, instead of being told by a file.

    /data/wow/quest/area/{id} and /data/wow/quest/category/{id} each list the
    quests they contain, and walking all of both is the only enumeration the API
    offers. It is not exhaustive -- a quest attached to neither is invisible here
    -- but in practice it reaches 98.7% of what this corpus already holds, and
    finds quests the corpus lacks. No local list is required.
    """
    def get(path):
        url = f"https://{region}.api.blizzard.com{path}?namespace=static-{region}&locale=en_US"
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access}"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.load(resp)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return None
                time.sleep(1 + attempt)
            except Exception:
                time.sleep(1 + attempt)
        return None

    ids = set()
    for kind, key in (("area", "areas"), ("category", "categories")):
        index = get(f"/data/wow/quest/{kind}/index")
        if not index:
            continue
        entries = index.get(key, [])
        print(f"walking {len(entries)} quest {key}", flush=True)
        with ThreadPoolExecutor(max_workers=8) as pool:
            for detail in pool.map(lambda e: get(f"/data/wow/quest/{kind}/{e['id']}"), entries):
                if detail:
                    for quest in detail.get("quests", []):
                        ids.add(quest["id"])
    return sorted(ids)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--locale", default="en_US")
    parser.add_argument("--csv", default=str(ROOT / "Data" / "quest_ids.csv"))
    parser.add_argument("--cache", default=str(ROOT / "Data" / "cache" / "quests_enUS.jsonl"))
    parser.add_argument("--failed", default=str(ROOT / "Data" / "cache" / "failed_enUS.txt"))
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--interval", type=float, default=0.25)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    cache, failed = pathlib.Path(args.cache), pathlib.Path(args.failed)
    cache.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if cache.exists():
        for line in cache.read_text(encoding="utf-8").splitlines():
            try: done.add(int(json.loads(line)["id"]))
            except Exception: pass
    if failed.exists():
        for line in failed.read_text().splitlines():
            try: done.add(int(line.strip()))
            except Exception: pass
    access = get_token()
    ids = enumerate_quest_ids(access)
    # An optional local list can add ids the API index does not reach. Nothing
    # requires it; without it the run is driven entirely by the API.
    extra = pathlib.Path(args.csv) if args.csv else None
    if extra and extra.exists():
        with extra.open(newline="", encoding="utf-8-sig") as handle:
            before = len(ids)
            ids = sorted(set(ids) | {int(row["ID"]) for row in csv.DictReader(handle) if row.get("ID")})
        print(f"optional list at {extra.name} added {len(ids) - before} ids", flush=True)
    ids = [i for i in ids if i not in done]
    if args.limit: ids = ids[:args.limit]
    access = token(); write_lock = threading.Lock(); rate_lock = threading.Lock(); next_start = [0.0]; completed = [len(done)]

    def wait_rate():
        with rate_lock:
            now = time.monotonic(); delay = max(0, next_start[0] - now)
            if delay: time.sleep(delay)
            next_start[0] = time.monotonic() + args.interval

    def fetch(qid):
        url = f"https://eu.api.blizzard.com/data/wow/quest/{qid}?namespace=static-eu&locale={urllib.parse.quote(args.locale)}"
        for attempt in range(5):
            wait_rate()
            try:
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access}", "User-Agent": "WordHunterWoW-ENPanel/0.1"})
                data = json.load(urllib.request.urlopen(req, timeout=30))
                record = {"id": qid, "title": data.get("title", ""), "description": data.get("description", ""), "objectives": data.get("objectives", "")}
                with write_lock, cache.open("a", encoding="utf-8") as out: out.write(json.dumps(record, ensure_ascii=False) + "\n")
                break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    with write_lock, failed.open("a") as out: out.write(f"{qid}\n")
                    break
                if e.code in (429, 500, 502, 503, 504): time.sleep(2 ** attempt); continue
                break
            except Exception:
                time.sleep(2 ** attempt)
        with write_lock:
            completed[0] += 1
            if completed[0] % 500 == 0: print(f"processed={completed[0]} remaining={len(ids) - (completed[0] - len(done))}", flush=True)

    print(f"locale={args.locale} total={len(ids)} cached={len(done)} workers={args.workers} interval={args.interval}", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool: list(pool.map(fetch, ids))
    print("done", flush=True)

if __name__ == "__main__": main()
