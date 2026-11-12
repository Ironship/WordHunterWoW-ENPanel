#!/usr/bin/env python3
"""Read quest text out of the game client's own cache.

Every time the client is told about a quest -- an NPC offers it, it shows up in
the log, an addon asks for its title -- the server answers with the whole quest
record, and the client keeps that answer in

    <game>/Cache/WDB/<locale>/questcache.wdb

It is written when the game closes or reloads. What is in it is exactly what
the game shows, in the language the client ran in, for quests the player never
took as well as the ones they did. This script reads it.

    python Tools/wdb_quests.py "<game>/Cache/WDB/enUS/questcache.wdb"
    python Tools/wdb_quests.py <questcache.wdb> --locale enUS --jsonl Data/cache/forever/native_enUS.jsonl

Layout, as found in the Forever (Camelot) 70xxx builds and checked against the
enUS, deDE and ruRU caches of a real install:

  header   24 bytes: magic 'TSQW', build u32, locale (4 bytes, reversed), 3 x u32
  records  id u32, length u32, data; an empty id and length ends the file
  data     starts with the quest id again, then a fixed block of numbers, then a
           12-byte MSB-first bit field holding the lengths of nine strings
           (title 9 bits, log 12, description 12, area 9, giver text 10, giver
           name 8, turn-in text 10, turn-in name 8, completion log 11), then the
           objective entries, then the nine strings back to back

The fixed block has changed between builds before, so the bit field is not
looked up at a remembered offset. It is found by asking where a bit field would
have to sit for the objectives and the nine strings to end exactly at the end of
the record. A record that cannot be framed that way, or whose text is not valid
UTF-8, is reported and left out; if many cannot be, the layout has changed and
the run stops instead of writing a half-empty file.

Only what the game published is read. A quest's progress line and hand-in text
are not part of this record (they come with the NPC's dialogue), so they are not
here and are not made up.
"""
import argparse
import json
import pathlib
import re
import struct
import sys

STRING_FIELDS = ("title", "objectives", "description", "area", "giverText", "giverName",
                 "turnInText", "turnInName", "completionLog")
STRING_BITS = (9, 12, 12, 9, 10, 8, 10, 8, 11)
HEADER_SIZE = 24
# Builds the layout above was checked on. Others are read, with a warning.
KNOWN_BUILDS = range(69000, 80000)
# More unreadable records than this share of the file means the layout moved.
MAX_UNREADABLE = 0.05


CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


class CacheError(Exception):
    pass


def read_header(buf):
    if len(buf) < HEADER_SIZE:
        raise CacheError("file is shorter than a cache header")
    magic = buf[0:4][::-1].decode("ascii", "replace")
    if magic != "WQST":
        raise CacheError("not a quest cache (magic %r, expected 'WQST')" % magic)
    build = struct.unpack_from("<I", buf, 4)[0]
    locale = buf[8:12][::-1].decode("ascii", "replace")
    return {"build": build, "locale": locale}


def iter_records(buf):
    """Yield (id, data) for every framed record; raise if the framing breaks."""
    pos, size = HEADER_SIZE, len(buf)
    while pos + 8 <= size:
        rid, length = struct.unpack_from("<II", buf, pos)
        pos += 8
        if rid == 0 and length == 0:
            return
        if pos + length > size:
            raise CacheError("record %d overruns the file" % rid)
        yield rid, buf[pos:pos + length]
        pos += length


def _string_lengths(data, offset):
    bits = int.from_bytes(data[offset:offset + 12], "big")
    out, used = [], 0
    for width in STRING_BITS:
        used += width
        out.append((bits >> (96 - used)) & ((1 << width) - 1))
    return out


def _walk_objectives(data, start, end):
    """Parse the objective entries between start and end.

    Returns the list, or None when they do not end exactly at end -- which is
    how a wrong guess at the bit field's position is told from the right one.
    """
    pos, found = start, []
    while pos < end:
        if pos + 30 > end:
            return None
        kind = data[pos + 4]
        object_id, amount = struct.unpack_from("<ii", data, pos + 6)
        effects = struct.unpack_from("<i", data, pos + 26)[0]
        if effects < 0 or effects > 64:
            return None
        pos += 30 + 4 * effects
        if pos >= end:
            return None
        length = data[pos]
        text_start = pos + 1
        pos = text_start + length
        if pos > end:
            return None
        try:
            text = data[text_start:pos].decode("utf-8")
        except UnicodeDecodeError:
            return None
        found.append({"type": kind, "objectId": object_id, "amount": amount, "text": text})
    return found if pos == end else None


def parse_record(rid, data):
    """Return the quest's strings and objectives, or None if it cannot be framed."""
    size = len(data)
    if size < 40 or struct.unpack_from("<I", data, 0)[0] != rid:
        return None
    candidates = []
    for offset in range(40, size - 11):
        lengths = _string_lengths(data, offset)
        tail = size - sum(lengths)
        if tail < offset + 12:
            continue
        objectives = _walk_objectives(data, offset + 12, tail) if tail > offset + 12 else []
        if objectives is None:
            continue
        try:
            position, strings = tail, {}
            for name, length in zip(STRING_FIELDS, lengths):
                strings[name] = data[position:position + length].decode("utf-8")
                position += length
        except UnicodeDecodeError:
            continue
        # A framing that is off by a few bytes cuts text in the wrong places and
        # leaves control characters inside it. Real quest text has none besides
        # line breaks and tabs.
        if any(CONTROL.search(value) for value in strings.values()):
            continue
        if not (strings["title"] or strings["description"] or strings["objectives"]):
            continue
        candidates.append((strings, objectives))
    if not candidates:
        return None
    if len(candidates) > 1:
        # Two framings both fit. Take one only if they agree on the text.
        first = candidates[0][0]
        if any(other[0] != first for other in candidates[1:]):
            return None
    strings, objectives = candidates[0]
    strings = dict(strings)
    strings["amounts"] = [o["amount"] for o in objectives]
    return strings


def read_cache(path):
    """Return (header, {quest id: record}, [ids that could not be read])."""
    buf = pathlib.Path(path).read_bytes()
    header = read_header(buf)
    records, unreadable = {}, []
    for rid, data in iter_records(buf):
        if rid in records:
            raise CacheError("quest %d appears twice" % rid)
        record = parse_record(rid, data)
        if record is None:
            unreadable.append(rid)
        else:
            records[rid] = record
    total = len(records) + len(unreadable)
    if total and len(unreadable) / total > MAX_UNREADABLE:
        raise CacheError("%d of %d records could not be framed; the cache layout has changed"
                         % (len(unreadable), total))
    return header, records, unreadable


AMOUNT = re.compile(r"\$(\d+)oa")


def resolve_amounts(text, amounts):
    """Replace the game's $1oa, $2oa ... with the amount of that objective.

    The cache keeps the macro. When the record lists its objectives the number
    sits right there; most Forever quests do not list them -- the client takes
    those from its own data tables -- and then the macro is left as it is, for
    whoever merges this with a source that has the number written out.
    """
    def fill(match):
        index = int(match.group(1)) - 1
        if 0 <= index < len(amounts) and amounts[index] > 0:
            return str(amounts[index])
        return match.group(0)
    return AMOUNT.sub(fill, text or "")


def to_entry(quest_id, record, header):
    entry = {
        "id": quest_id,
        "title": record["title"],
        "description": resolve_amounts(record["description"], record["amounts"]),
        "objectives": resolve_amounts(record["objectives"], record["amounts"]),
        "source": "questcache.wdb",
        "build": header["build"],
        "locale": header["locale"],
    }
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("cache", nargs="+", help="questcache.wdb file(s)")
    parser.add_argument("--locale", help="refuse a cache written by a client in another language")
    parser.add_argument("--jsonl", help="write the quests here, one JSON object per line")
    args = parser.parse_args()

    entries = {}
    for path in args.cache:
        try:
            header, records, unreadable = read_cache(path)
        except (CacheError, OSError) as error:
            sys.exit("%s: %s" % (path, error))
        if args.locale and header["locale"] != args.locale:
            sys.exit("%s: written by a %s client, not %s" % (path, header["locale"], args.locale))
        note = "" if header["build"] in KNOWN_BUILDS else "  (build outside the range this was checked on)"
        print("%s: build %d, %s, %d quests, %d unreadable%s"
              % (path, header["build"], header["locale"], len(records), len(unreadable), note))
        if unreadable:
            print("  unreadable ids:", unreadable[:20], "..." if len(unreadable) > 20 else "")
        for quest_id, record in records.items():
            entry = to_entry(quest_id, record, header)
            # Later files win: list the older cache first.
            entries[quest_id] = entry
    if args.jsonl:
        out = pathlib.Path(args.jsonl)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8", newline="\n") as handle:
            for quest_id in sorted(entries):
                handle.write(json.dumps(entries[quest_id], ensure_ascii=False) + "\n")
        print("wrote %d quests to %s" % (len(entries), out))


if __name__ == "__main__":
    main()
