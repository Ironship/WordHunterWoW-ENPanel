#!/usr/bin/env python3
"""Turn collected English names into Lua the addon can load.

Spells and creatures are small enough to ship inside the panel itself. Items are
not -- 168k of them are 90% of the whole payload -- so they go to their own
optional addon and register themselves when present.

    python Tools/build_names_lua.py --kind spell    --out ../WordHunterWoW-ENPanel/Data
    python Tools/build_names_lua.py --kind creature --out ../WordHunterWoW-ENPanel/Data
    python Tools/build_names_lua.py --kind item     --out ../WordHunterWoW-ENPanel-Items/Data --chunk 40000
"""
import argparse, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
VARS = {"item": "WordHunterWoW_ENNames_Item",
        "spell": "WordHunterWoW_ENNames_Spell",
        "creature": "WordHunterWoW_ENNames_NPC"}
STEMS = {"item": "NamesItem", "spell": "NamesSpell", "creature": "NamesNPC"}
DESC_VARS = {"item": "WordHunterWoW_ENDesc_Item", "spell": "WordHunterWoW_ENDesc_Spell"}
DESC_STEMS = {"item": "DescItem", "spell": "DescSpell"}


def quote(value):
    return '"' + (value.replace("\\", "\\\\").replace('"', '\\"')
                       .replace("\r", "").replace("\n", "\\n")) + '"'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=VARS, required=True)
    ap.add_argument("--out", required=True, help="Data directory to write into")
    ap.add_argument("--chunk", type=int, default=0, help="split into files of N entries")
    ap.add_argument("--desc", action="store_true",
                    help="build the description table instead of the name table")
    args = ap.parse_args()

    if args.desc and args.kind not in DESC_VARS:
        sys.exit(f"no descriptions exist for {args.kind}")
    src = ROOT / (f"Data/cache/desc_{args.kind}.jsonl" if args.desc
                  else f"Data/cache/names_{args.kind}.jsonl")
    rows = []
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        text = (r.get("text") if args.desc else r.get("name")) or ""
        text = text.strip()
        if text:
            rows.append((int(r["id"]), text))
    rows.sort()

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    var = DESC_VARS[args.kind] if args.desc else VARS[args.kind]
    stem = DESC_STEMS[args.kind] if args.desc else STEMS[args.kind]

    # Clear any files a previous, longer run left behind, so a shrinking data set
    # cannot leave a stale tail loaded alongside the fresh files.
    for stale in out_dir.glob(f"{stem}_*.lua"):
        stale.unlink()
    single = out_dir / f"{stem}.lua"
    if single.exists():
        single.unlink()

    chunk = args.chunk or len(rows)
    written = []
    for index in range(0, len(rows), chunk):
        part = rows[index:index + chunk]
        name = (f"{stem}_{index // chunk:03d}.lua" if args.chunk else f"{stem}.lua")
        lines = [f"{var} = {var} or {{}}"]
        lines += [f"{var}[{qid}] = {quote(text)}" for qid, text in part]
        (out_dir / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append(name)

    total = sum((out_dir / n).stat().st_size for n in written)
    print(f"{args.kind}: {len(rows):,} names -> {len(written)} file(s), {total/1048576:.1f} MB")
    for n in written:
        print(f"  {n}")
    print("\ntoc lines:")
    for n in written:
        print(f"Data/{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
