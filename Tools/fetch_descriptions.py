#!/usr/bin/env python3
"""Fill in English descriptions for names already collected.

fetch_names.py gets everything from the search endpoints, which is cheap because
one request returns a thousand entities. Descriptions are not in those results,
so this needs one request per entity -- 8,941 for spells, which is minutes, and
168,833 for items, which is hours. Run it for the kind you actually want.

    python Tools/fetch_descriptions.py --kind spell

Writes Data/cache/desc_<kind>.jsonl and resumes from whatever is already there.
An id that has no description is recorded as such so it is not asked for twice.
"""
import argparse, base64, json, pathlib, sys, threading, time
from products import PRODUCTS, namespace, cache_path
import urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "Data/cache"
PATHS = {"spell": "/data/wow/spell/{}", "item": "/data/wow/item/{}"}


def get_token():
    env = {}
    for line in (ROOT / "Tools/keys.env").read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    auth = base64.b64encode(
        f"{env['BLIZZARD_CLIENT_ID']}:{env['BLIZZARD_CLIENT_SECRET']}".encode()).decode()
    req = urllib.request.Request("https://oauth.battle.net/token",
                                 data=b"grant_type=client_credentials",
                                 headers={"Authorization": f"Basic {auth}"})
    return json.load(urllib.request.urlopen(req, timeout=30))["access_token"]


def describe(kind, record):
    """The line a player would actually want translated."""
    if kind == "spell":
        return (record.get("description") or "").strip()
    # An item's useful text is the effect its spells describe -- the "Use:" and
    # "Chance on hit:" lines. The rest of the tooltip is numbers the player can
    # already read.
    preview = record.get("preview_item") or {}
    parts = []
    for entry in preview.get("spells") or []:
        text = (entry.get("description") or "").strip()
        if text:
            parts.append(text)
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=PATHS, required=True)
    ap.add_argument("--product", default="retail", choices=sorted(PRODUCTS))
    ap.add_argument("--region", default="eu")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    names_path = cache_path(CACHE, args.product, f"names_{args.kind}.jsonl")
    if not names_path.exists():
        sys.exit(f"no names cached at {names_path}; run fetch_names.py --product {args.product} first")
    ids = [json.loads(l)["id"] for l in names_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    out_path = cache_path(CACHE, args.product, f"desc_{args.kind}.jsonl")
    done = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    done.add(json.loads(line)["id"])
                except Exception:
                    pass
    todo = [i for i in ids if i not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"product={args.product} kind={args.kind} known={len(ids):,} already described={len(done):,} to fetch={len(todo):,}")

    token = [get_token()]
    lock = threading.Lock()
    count = [0]
    started = time.monotonic()
    fh = out_path.open("a", encoding="utf-8")

    def fetch(entity_id):
        url = (f"https://{args.region}.api.blizzard.com"
               + PATHS[args.kind].format(entity_id)
               + f"?namespace={namespace(args.product, args.region)}&locale=en_US")
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token[0]}"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    record = json.load(resp)
                text = describe(args.kind, record)
                with lock:
                    fh.write(json.dumps({"id": entity_id, "text": text}, ensure_ascii=False) + "\n")
                return
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    with lock:
                        fh.write(json.dumps({"id": entity_id, "text": ""}) + "\n")
                    return
                if e.code == 401:
                    with lock:
                        token[0] = get_token()
                else:
                    time.sleep(2 ** attempt)
            except Exception:
                time.sleep(2 ** attempt)

    def run(entity_id):
        fetch(entity_id)
        with lock:
            count[0] += 1
            if count[0] % 500 == 0:
                rate = count[0] / max(time.monotonic() - started, 1)
                left = (len(todo) - count[0]) / max(rate, 0.01)
                print(f"  {count[0]:,}/{len(todo):,}  {rate:.0f}/s  ~{left/60:.0f} min left", flush=True)
                fh.flush()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(run, todo))
    fh.close()

    rows = [json.loads(l) for l in out_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    withtext = sum(1 for r in rows if r["text"])
    print(f"done: {len(rows):,} records, {withtext:,} with text "
          f"({time.monotonic()-started:.0f}s) -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
