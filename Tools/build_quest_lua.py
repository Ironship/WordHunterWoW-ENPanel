#!/usr/bin/env python3
import argparse, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[1]

def quote(value):
    return '"' + str(value or "").replace('\\', '\\\\').replace('"', '\\"').replace('\r', '').replace('\n', '\\n') + '"'

def main():
    p = argparse.ArgumentParser(); p.add_argument("--cache", default=str(ROOT / "Data/cache/quests_enUS.jsonl")); p.add_argument("--chunk", type=int, default=1000)
    p.add_argument("--out", help="Data directory to write into; the manifest is left alone when given")
    args = p.parse_args()
    entries = {}
    for line in pathlib.Path(args.cache).read_text(encoding="utf-8").splitlines():
        record = json.loads(line); entries[int(record["id"])] = record
    data_dir = pathlib.Path(args.out) if args.out else ROOT / "Data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for old in data_dir.glob("QuestEN_*.lua"): old.unlink()
    names = []
    ordered = sorted(entries.items())
    for start in range(0, len(ordered), args.chunk):
        name = f"QuestEN_{start // args.chunk:03d}.lua"; names.append(name)
        lines = ["WordHunterWoW_QuestEN = WordHunterWoW_QuestEN or {}"]
        for qid, r in ordered[start:start + args.chunk]:
            fields = [f"title = {quote(r.get('title'))}",
                      f"description = {quote(r.get('description'))}",
                      f"objectives = {quote(r.get('objectives'))}"]
            # Only written when present. Blizzard's API publishes neither, so on
            # most records these are absent and the panel says so rather than
            # showing the opening text in their place.
            for field in ("progress", "completion"):
                value = (r.get(field) or "").strip()
                if value:
                    fields.append(f"{field} = {quote(value)}")
            lines.append(f"WordHunterWoW_QuestEN[{qid}] = {{ " + ", ".join(fields) + " }")
        (data_dir / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not args.out:
        # Only the QuestEN block is regenerated. Everything else the manifest
        # loads -- Data/NamesSpell.lua, Data/NamesNPC.lua, Data/DescSpell.lua,
        # Names.lua -- is kept where it is. An earlier version rebuilt the whole
        # file from the header alone and dropped all four, which silently takes
        # the spell, NPC and item tooltips out of the addon.
        # The Retail manifest is the one that lists these chunks. The Classic
        # manifest lists Data/Classic and is left alone: its quest text comes
        # from somewhere else and has its own chunk count.
        toc = ROOT / "WordHunterWoW-ENPanel_Mainline.toc"
        quest = re.compile(r"^Data/QuestEN_\d+\.lua$")
        out, written = [], False
        for line in toc.read_text(encoding="utf-8").splitlines():
            if quest.match(line.strip()):
                if not written:
                    out.extend(f"Data/{n}" for n in names)
                    written = True
                continue
            out.append(line)
        if not written:
            raise SystemExit("the manifest lists no QuestEN file; refusing to guess where the block goes")
        toc.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"generated {len(entries)} quests in {len(names)} chunks")

if __name__ == "__main__": main()
