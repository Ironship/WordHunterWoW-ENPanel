#!/usr/bin/env python3
import argparse, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[1]

def quote(value):
    return '"' + str(value or "").replace('\\', '\\\\').replace('"', '\\"').replace('\r', '').replace('\n', '\\n') + '"'

def main():
    p = argparse.ArgumentParser(); p.add_argument("--cache", default=str(ROOT / "Data/cache/quests_enUS.jsonl")); p.add_argument("--chunk", type=int, default=1000)
    p.add_argument("--out", help="Data directory to write into; the manifest is left alone when given")
    p.add_argument("--toc", help="with --out: the manifest whose QuestEN lines should list the files written there")
    p.add_argument("--flavor", help="also publish the records as this game's own table, "
                   "WordHunterWoW_QuestDataByFlavor.<flavor>.enUS (see below)")
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
        if args.flavor:
            # The base addon reads a game's English text from that game's own
            # table when one exists, and then from nothing else; and the German
            # Dictionary swaps WordHunterWoW_QuestEN for its own table of the
            # same game. A record that lives only in WordHunterWoW_QuestEN is
            # therefore never read when the Dictionary is installed. Putting
            # the records into the game's table -- and pointing the old name at
            # it -- is what makes them visible with and without the Dictionary.
            # The Dictionary's own records for the game are loaded later and
            # replace these by id; they never need to be copied from here.
            flavor = args.flavor
            lines = ["WordHunterWoW_QuestDataByFlavor = WordHunterWoW_QuestDataByFlavor or {}",
                     f"WordHunterWoW_QuestDataByFlavor.{flavor} = WordHunterWoW_QuestDataByFlavor.{flavor} or {{}}",
                     f"WordHunterWoW_QuestDataByFlavor.{flavor}.enUS = WordHunterWoW_QuestDataByFlavor.{flavor}.enUS or {{}}",
                     f"WordHunterWoW_QuestEN = WordHunterWoW_QuestDataByFlavor.{flavor}.enUS"]
        for qid, r in ordered[start:start + args.chunk]:
            fields = [f"title = {quote(r.get('title'))}",
                      f"description = {quote(r.get('description'))}",
                      f"objectives = {quote(r.get('objectives'))}"]
            # Only written when present. Blizzard's API publishes neither, so on
            # most records these are absent and the panel says so rather than
            # showing the opening text in their place.
            # descriptionSource says where an opening text was copied from when it
            # is not the game's own (Tools/build_forever_quests.py sets it to
            # "retail"); the base addon leaves such a text out on a client that
            # is not Retail.
            for field in ("progress", "completion", "descriptionSource"):
                value = (r.get(field) or "").strip()
                if value:
                    fields.append(f"{field} = {quote(value)}")
            lines.append(f"WordHunterWoW_QuestEN[{qid}] = {{ " + ", ".join(fields) + " }")
        # Bytes, not text: on Windows a text write turns every newline into
        # CRLF and the next run diffs all fifty files against the shipped LF.
        (data_dir / name).write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    if not args.out:
        # Only the QuestEN block is regenerated. Everything else the manifest
        # loads -- Data/NamesSpell.lua, Data/NamesNPC.lua, Data/DescSpell.lua,
        # Names.lua -- is kept where it is. An earlier version rebuilt the whole
        # file from the header alone and dropped all four, which silently takes
        # the spell, NPC and item tooltips out of the addon.
        # The Retail manifest is the one that lists these chunks. The Classic
        # manifest lists Data/Classic and is left alone: its quest text comes
        # from somewhere else and has its own chunk count.
        sync_manifest(ROOT / "WordHunterWoW-ENPanel_Mainline.toc", "Data", names)
    elif args.toc:
        # A manifest that lists this directory's chunks (Camelot lists Data/Forever)
        # is kept in step, so a run that produces a different number of chunks
        # cannot leave it naming files that are gone or missing new ones -- the
        # game loads exactly what the manifest says and nothing else.
        directory = data_dir.resolve().relative_to(ROOT).as_posix()
        sync_manifest(pathlib.Path(args.toc), directory, names)
    print(f"generated {len(entries)} quests in {len(names)} chunks")

def sync_manifest(toc, directory, names):
    """Replace the manifest's QuestEN lines under directory with names."""
    quest = re.compile(r"^" + re.escape(directory) + r"/QuestEN_\d+\.lua$")
    out, written = [], False
    for line in toc.read_text(encoding="utf-8").splitlines():
        if quest.match(line.strip()):
            if not written:
                out.extend(f"{directory}/{n}" for n in names)
                written = True
            continue
        out.append(line)
    if not written:
        raise SystemExit(f"{toc.name} lists no {directory}/QuestEN file; refusing to guess where the block goes")
    toc.write_bytes(("\n".join(out) + "\n").encode("utf-8"))

if __name__ == "__main__": main()
