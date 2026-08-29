#!/usr/bin/env python3
"""Collect item, spell and creature names from Blizzard's Game Data API.

Everything here comes from the official API on this project's own credentials.

Two things make this cheap enough to be worth doing. The search endpoints return
the full record for each hit, and a record asked for without a `locale` carries
every language at once -- so one request yields up to 1000 entities in all six
languages, not one entity in one language. And search accepts a range filter on
`id`, which sidesteps the 1000-result cap: walk the id space in windows small
enough that no window overflows, and nothing is missed.

That turns roughly 700,000 detail requests into a few thousand search requests.

    python Tools/fetch_names.py --kind item
    python Tools/fetch_names.py --kind spell
    python Tools/fetch_names.py --kind creature

Results are appended to Data/cache/names_<kind>.jsonl and the run resumes from
whatever is already there, so an interrupted run costs nothing.
"""
import argparse, base64, json, pathlib, sys, threading, time
import urllib.error, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "Data/cache"
LOCALES = ("en_US", "de_DE", "fr_FR", "es_ES", "es_MX", "it_IT", "pt_BR")
PAGE_SIZE = 1000            # the per-query result cap
KINDS = {
    # kind: (search path, id ceiling to walk to, starting window)
    "item":     ("/data/wow/search/item",     260000, 4000),
    "spell":    ("/data/wow/search/spell",    500000, 4000),
    "creature": ("/data/wow/search/creature", 260000, 8000),
}


def load_keys():
    env = {}
    for line in (ROOT / "Tools/keys.env").read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env["BLIZZARD_CLIENT_ID"], env["BLIZZARD_CLIENT_SECRET"]


def get_token():
    cid, secret = load_keys()
    auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    req = urllib.request.Request("https://oauth.battle.net/token",
                                 data=b"grant_type=client_credentials",
                                 headers={"Authorization": f"Basic {auth}"})
    return json.load(urllib.request.urlopen(req, timeout=30))["access_token"]


class Api:
    def __init__(self, region="eu"):
        self.region = region
        self.token = get_token()
        self.lock = threading.Lock()

    def search(self, path, lo, hi, page):
        params = {"namespace": f"static-{self.region}", "id": f"[{lo},{hi}]",
                  "orderby": "id", "_page": page, "_pageSize": PAGE_SIZE}
        url = f"https://{self.region}.api.blizzard.com{path}?" + urllib.parse.urlencode(params)
        for attempt in range(5):
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.token}"})
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.load(resp)
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    with self.lock:
                        self.token = get_token()
                elif e.code in (429, 500, 502, 503, 504):
                    time.sleep(2 ** attempt)
                else:
                    return None
            except Exception:
                time.sleep(2 ** attempt)
        return None


def names_from(record):
    """Pull the localized name off a search hit, dropping locales it lacks."""
    name = record.get("name")
    if isinstance(name, str):
        return {"en_US": name}
    if not isinstance(name, dict):
        return {}
    return {loc: name[loc] for loc in LOCALES if name.get(loc)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=KINDS, required=True)
    ap.add_argument("--region", default="eu")
    ap.add_argument("--max-id", type=int, help="override the id ceiling")
    args = ap.parse_args()

    path, ceiling, window = KINDS[args.kind]
    if args.max_id:
        ceiling = args.max_id
    CACHE.mkdir(parents=True, exist_ok=True)
    out_path = CACHE / f"names_{args.kind}.jsonl"

    have = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    have.add(json.loads(line)["id"])
                except Exception:
                    pass
    print(f"kind={args.kind} already cached={len(have):,} ceiling={ceiling:,}")

    api = Api(args.region)
    lo, written, queries = 0, 0, 0
    started = time.monotonic()
    with out_path.open("a", encoding="utf-8") as fh:
        while lo < ceiling:
            span = window
            while True:
                hi = min(lo + span, ceiling)
                data = api.search(path, lo, hi, 1)
                queries += 1
                if data is None:
                    print(f"  ! giving up on [{lo},{hi}]")
                    break
                results = data.get("results", [])
                # pageCount is useless here: the API caps a result set at 1000 and
                # the page size is already 1000, so an overflowing window still
                # reports a single page. A full page is the only honest signal
                # that entries were left behind -- halve and look again.
                if len(results) >= PAGE_SIZE or data.get("resultCountCapped"):
                    if span > 100:
                        span //= 2
                        continue
                    print(f"  ! [{lo},{hi}] still full at the minimum window; "
                          f"ids beyond the first {len(results)} may be missing")
                for result in results:
                    rec = result.get("data", {})
                    rid = rec.get("id")
                    if rid is None or rid in have:
                        continue
                    names = names_from(rec)
                    if not names.get("en_US"):
                        continue
                    have.add(rid)
                    fh.write(json.dumps({"id": rid, "names": names}, ensure_ascii=False) + "\n")
                    written += 1
                break
            lo = hi
            if queries % 25 == 0:
                rate = written / max(time.monotonic() - started, 1)
                print(f"  id<{lo:,} queries={queries} collected={len(have):,} (+{written:,}) "
                      f"{rate:.0f}/s", flush=True)
        fh.flush()

    print(f"done: {len(have):,} {args.kind} names in {out_path} "
          f"({queries} queries, {time.monotonic()-started:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
