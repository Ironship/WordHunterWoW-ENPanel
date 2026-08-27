#!/usr/bin/env python3
import argparse, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

def quote(value):
    return '"' + str(value or "").replace('\\', '\\\\').replace('"', '\\"').replace('\r', '').replace('\n', '\\n') + '"'

def main():
    p = argparse.ArgumentParser(); p.add_argument("--cache", default=str(ROOT / "Data/cache/quests_enUS.jsonl")); p.add_argument("--chunk", type=int, default=1000); args = p.parse_args()
    entries = {}
    for line in pathlib.Path(args.cache).read_text(encoding="utf-8").splitlines():
        record = json.loads(line); entries[int(record["id"])] = record
    data_dir = ROOT / "Data"
    for old in data_dir.glob("QuestEN_*.lua"): old.unlink()
    names = []
    ordered = sorted(entries.items())
    for start in range(0, len(ordered), args.chunk):
        name = f"QuestEN_{start // args.chunk:03d}.lua"; names.append(name)
        lines = ["WordHunterWoW_QuestEN = WordHunterWoW_QuestEN or {}"]
        for qid, r in ordered[start:start + args.chunk]:
            lines.append(f"WordHunterWoW_QuestEN[{qid}] = {{ title = {quote(r.get('title'))}, description = {quote(r.get('description'))}, objectives = {quote(r.get('objectives'))} }}")
        (data_dir / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
        toc = ROOT / "WordHunterWoW-ENPanel.toc"
        header = []
        for line in toc.read_text(encoding="utf-8").splitlines():
            if line.startswith("##") or line.strip() == "":
                header.append(line)
            else:
                break
        while header and header[-1].strip() == "":
            header.pop()
        toc.write_text("\n".join(header) + "\n\n" + "\n".join(f"Data/{n}" for n in names) + "\nENPanel.lua\n", encoding="utf-8")
    print(f"generated {len(entries)} quests in {len(names)} chunks")

if __name__ == "__main__": main()
