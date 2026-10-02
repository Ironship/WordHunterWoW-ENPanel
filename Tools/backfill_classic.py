#!/usr/bin/env python3
"""Fill empty Classic quest descriptions from the Retail dataset.

Blizzard's Game Data API has no quest endpoint for Classic, so Data/Classic is
extracted from a local quest database that carries a title and an objective
line but no offer text -- and every Classic quest shows "no English opening
text" in the panel, even the thousands whose English text ships in Data/.
Quest ids are stable across game versions, so where the Retail record for the
same id has a description, it is copied over verbatim: Blizzard's own words,
not invented ones. Ids with no Retail description keep the empty string and
the panel keeps telling the truth about them.

Reads the committed Data/QuestEN_*.lua and rewrites Data/Classic/QuestEN_*.lua
in place. Chunk files, order and manifest are untouched; only description = ""
fields that gained a Retail twin change.

Run from the addon root:  python Tools/backfill_classic.py
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]

RECORD = re.compile(
    r'WordHunterWoW_QuestEN\[(?P<id>\d+)\] = \{ title = "(?P<title>(?:[^"\\]|\\.)*)", '
    r'description = "(?P<desc>(?:[^"\\]|\\.)*)", '
    r'objectives = "(?P<obj>(?:[^"\\]|\\.)*)"'
)


def read_lua(path):
    # Bytes, not text: universal-newline translation would rewrite every line
    # ending in the file and turn a 3,590-line change into a whole-file one.
    return path.read_bytes().decode("utf-8")


def descriptions(files):
    found = {}
    for path in files:
        for match in RECORD.finditer(read_lua(path)):
            desc = match.group("desc")
            if desc:
                found.setdefault(int(match.group("id")), match.group("desc"))
    return found


def main():
    retail = descriptions(sorted((ROOT / "Data").glob("QuestEN_*.lua")))
    classic_dir = ROOT / "Data" / "Classic"
    filled, already, missing = 0, 0, 0

    def backfill(match):
        nonlocal filled, already, missing
        qid = int(match.group("id"))
        if match.group("desc"):
            already += 1
            return match.group(0)
        desc = retail.get(qid)
        if not desc:
            missing += 1
            return match.group(0)
        filled += 1
        # Only the empty description is swapped; title, objectives and any
        # trailing progress/completion fields stay exactly as extracted.
        return match.group(0).replace('description = ""', f'description = "{desc}"', 1)

    for path in sorted(classic_dir.glob("QuestEN_*.lua")):
        text = read_lua(path)
        path.write_bytes(RECORD.sub(backfill, text).encode("utf-8"))
    print(f"classic descriptions filled from retail: {filled}")
    print(f"classic records that already had one: {already}")
    print(f"classic records with no retail description: {missing}")


if __name__ == "__main__":
    main()
