#!/usr/bin/env python3
"""Assemble the English quest text for World of Warcraft: Forever.

Forever (the Camelot client) is Classic with new content on top: about 4,400
quests that Classic had and about 1,800 that only it has, with ids from 65000 up.
None of the new ones is in the Retail data (what the Game Data API returned), and
the API has no quest endpoint for Classic at all, so the Retail pipeline cannot
reach them. This script puts together what can be had, field by field, from five
places:

  native        what the Forever client itself received from the server, read out
                of Cache/WDB/enUS/questcache.wdb (Tools/wdb_quests.py), or taken
                from an older capture of one. This is the game's own text. The
                client cache is not cumulative -- quests drop out of it -- so
                every run adds what it read to Data/cache/forever/native_enUS.jsonl
                and reads from there, and nothing once seen is lost.
  efficient     Efficient Games' EG Link output (CC BY 4.0, see NOTICE): what the
                server said of every quest that players' clients asked about, read
                from their caches like the line above but from many players and
                every build, the objectives' amounts included; and the lines the
                NPC says while a quest is in progress and at hand-in, as players'
                games showed them. It is the game's own text too, so it is merged
                with the native text: the newer build wins.
  classic       Data/Classic: titles and objective lines from the Classic quest
                database, plus the opening text that was copied over from the
                Retail quest of the same id. A Retail copy can be a newer telling
                than Forever's, so it is used last and marked descriptionSource =
                "retail", which the base addon already knows to leave out on a
                client that is not Retail.
  multilanguage the MultiLanguage addon's Forever data (Ruben Zantingh, used with
                his permission, see NOTICE): title, objective, opening text and,
                for most quests, the line the NPC says while the quest is in
                progress and the one at hand-in. Neither of those two can be read
                from the client cache, so this is where they come from.
  spoken        the quest data of the Spoken addon (rusty-key/spoken-wow, MIT, see
                NOTICE): the opening text and hand-in text of its voiced quests and
                the English title of every quest Forever serves. Used last of the
                text sources: it is the least close to what the live game says.

Which source wins, per field:

  title        native (client cache or Efficient Games, newer build first), classic,
               multilanguage, spoken
  description  native, multilanguage, spoken, classic (Retail copy)
  objectives   native, classic, multilanguage
  progress     efficient games, multilanguage
  completion   efficient games, multilanguage, spoken

Nothing is rewritten. The only change made to a text is the one that makes the
sources agree on how a name is written: the game's $n, $c and $r (and the
<name> of the scrape) become {name}, {class} and {race}, and $b becomes a line
break. A macro the game would fill with a number ($1oa: the amount of the first
objective) is replaced by the amount Efficient Games lists for that objective, or
when another source has the same sentence with the number written out; otherwise
it is shown as X.

    python Tools/build_forever_quests.py --fetch --wdb "<game>/Cache/WDB/enUS/questcache.wdb"
    python Tools/build_quest_lua.py --cache Data/cache/forever/quests_enUS.jsonl --out Data/Forever --chunk 1000 --toc WordHunterWoW-ENPanel_Camelot.toc --flavor forever

The first command writes the cache file the second turns into Data/Forever.
"""
import argparse
import html
import json
import os
import pathlib
import re
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wdb_quests  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "Data" / "cache" / "forever"

# The MultiLanguage revision the Forever data was taken from. The data lives
# under Database/Quests/enUS.lua; nothing newer has changed it.
MULTILANGUAGE_REV = "87d8e5f4c904291c24296205df97c9bc96aa6943"
MULTILANGUAGE_URL = ("https://raw.githubusercontent.com/rubenzantingh/MultiLanguage/"
                     "%s/Database/Quests/enUS.lua" % MULTILANGUAGE_REV)

# Spoken's quest data (MIT, (c) 2026 Rusty Key), at the revision it was read from.
# The same two files ship in the Spoken_Quests addon under Data/.
SPOKEN_REV = "9b2e01c92f99c8d2457fa676a1b9f91ba602338a"
SPOKEN_FILES = ("QuestText.lua", "Compendium.lua")
SPOKEN_URL = ("https://raw.githubusercontent.com/rusty-key/spoken-wow/"
              "%s/addons/Spoken_Quests/Data/%%s" % SPOKEN_REV)

# Efficient Games' EG Link output (CC BY 4.0), at the revision it was read from. One
# folder per client build under two products: the beta and the live game.
EG_REPO = "JIVESCORP/eg-link-output-wowf"
EG_REV = "164bd1e2d89579ada4ee5e2de7e5fd4db684a9f1"
EG_RAW = "https://raw.githubusercontent.com/%s/%s/" % (EG_REPO, EG_REV)

FIELD = re.compile(r'(\w+) = (nil|-?\d+(?:\.\d+)?|true|false|"(?:\\.|[^"\\])*")')
ROW = re.compile(r"^\s*(?:[A-Za-z_]\w*)?\[(\d+)\] = \{(.*)\},?\s*$")
ESCAPE = re.compile(r'\\(?:(\d{1,3})|(.))', re.S)
SIMPLE = {"n": "\n", "r": "\r", "t": "\t", "a": "\a", "b": "\b", "f": "\f", "v": "\v"}

# Quest 1 is a developer's test record in the MultiLanguage data.
SKIP_IDS = {1}


def lua_unquote(raw):
    """The text of a Lua string literal, without its quotes."""
    def replace(match):
        if match.group(1) is not None:
            return chr(int(match.group(1)))
        char = match.group(2)
        return SIMPLE.get(char, char)
    return ESCAPE.sub(replace, raw)


def parse_rows(text, wanted=None):
    """{id: {field: value}} from lines like  [12] = {title = "...", ...},"""
    rows = {}
    for line in text.splitlines():
        match = ROW.match(line)
        if not match:
            continue
        quest_id = int(match.group(1))
        record = {}
        for key, raw in FIELD.findall(match.group(2)):
            if raw == "nil":
                continue
            if raw.startswith('"'):
                record[key] = lua_unquote(raw[1:-1])
            elif raw in ("true", "false"):
                record[key] = raw == "true"
            else:
                record[key] = float(raw) if "." in raw else int(raw)
        if record:
            rows[quest_id] = record
    return rows


def read_lua_dir(directory, pattern):
    rows = {}
    for path in sorted(pathlib.Path(directory).glob(pattern)):
        rows.update(parse_rows(path.read_bytes().decode("utf-8")))
    return rows


# --- text -----------------------------------------------------------------

NAME_FORMS = (("name", "nN"), ("class", "cC"), ("race", "rR"))


def normalize(text, scraped=False):
    """Make the sources agree on how a placeholder and a line break are written."""
    if not text:
        return ""
    if scraped:
        # The MultiLanguage scrape kept HTML escapes -- <name> arrives as
        # &lt;name&gt; -- and a non-breaking space where the game has an ordinary one.
        text = html.unescape(text.replace("&nbsp;", " ")).replace("\xa0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\$[bB]", "\n", text)
    for word, letters in NAME_FORMS:
        # One letter is the whole macro; what follows it is ordinary text, so
        # "$rs" is the race and an s, "$nath" the name and "ath".
        text = re.sub(r"\$[%s]" % letters, "{%s}" % word, text)
        text = text.replace("<%s>" % word, "{%s}" % word)
    # "$g lad : lass;" is the game's he/she switch. The data already writes those
    # as <lad/lass> (the Blizzard API does), so this is the same thing.
    text = GENDER.sub(lambda match: "<%s/%s>" % (match.group(1), match.group(2)), text)
    return text.strip()


GENDER = re.compile(r"\$[gG]\s*([^:;$]+?)\s*:\s*([^;$]+?)\s*;")
DEVELOPER_TEXT = re.compile(r"temp text \d+|NEW TEST|\$Tpunk;|\(123\)aa")

# The scrape glued the reward headings of the quest page onto the end of its text.
REWARD_HEADING = re.compile(
    r"\s*(?:(?:You will (?:also )?receive|Upon completion of this quest you will gain"
    r"|You will be able to choose one of these rewards)\s*:\s*)+$")


def clean_scraped(record):
    """One MultiLanguage record as title / description / objectives / progress / completion."""
    fields = {
        "title": normalize(record.get("title"), scraped=True),
        "description": normalize(record.get("description"), scraped=True),
        "objectives": normalize(record.get("objective"), scraped=True),
        "progress": normalize(record.get("progress"), scraped=True),
        "completion": normalize(record.get("completion"), scraped=True),
    }
    for name in ("description", "objectives", "progress", "completion"):
        fields[name] = REWARD_HEADING.sub("", fields[name]).strip()
        # A few records are a developer's test text, not something to learn from.
        if DEVELOPER_TEXT.search(fields[name]):
            fields[name] = ""
    # On some pages the objective line and the opening text come out as one run in
    # the objective field: "Speak with X." followed by the whole opening text.
    objective, description = fields["objectives"], fields["description"]
    if objective and description:
        if objective == description:
            fields["objectives"] = ""
        elif objective.endswith(description):
            fields["objectives"] = objective[:-len(description)].strip()
    return fields


MACRO = re.compile(r"\$(\d+)oa")
# A number the game fills in from its own data tables: the amount of an objective
# ($1oa), or a world-state count ($2063w). Nothing in the quest text says what it is.
UNKNOWN_NUMBER = re.compile(r"\$\d+(?:oa|w)")


def resolve_macros(native, reference):
    """Fill $1oa-style macros in the game's text from the same sentence elsewhere.

    Only when the reference is the native text with numbers where the macros are
    -- anything else could be a different version of the quest, and a number
    taken from it would be a guess.
    """
    if not native or not MACRO.search(native) or not reference:
        return native
    pattern, last, keys = "", 0, []
    for match in MACRO.finditer(native):
        pattern += re.escape(native[last:match.start()]) + r"(\d+)"
        keys.append(match.group(1))
        last = match.end()
    pattern += re.escape(native[last:])
    found = re.fullmatch(pattern, reference)
    if not found:
        return native
    values = {}
    for key, value in zip(keys, found.groups()):
        if values.setdefault(key, value) != value:
            return native
    return MACRO.sub(lambda match: values[match.group(1)], native)


def fill_amounts(text, amounts):
    """Write out $1oa, $2oa ... from the amounts of the quest's objectives, in order."""
    if not text or not amounts:
        return text

    def number(match):
        index = int(match.group(1)) - 1
        if 0 <= index < len(amounts) and amounts[index] > 0:
            return str(amounts[index])
        return match.group(0)
    return MACRO.sub(number, text)


# A title that says the record is not a quest a player can have.
JUNK_TITLE = re.compile(r"^<(?:UNUSED|TEST)[^>]*>", re.I)


# --- sources ----------------------------------------------------------------

def load_classic(directory):
    rows = read_lua_dir(directory, "QuestEN_*.lua")
    return {quest_id: {k: v for k, v in record.items() if k in ("title", "description", "objectives")}
            for quest_id, record in rows.items()}


def load_multilanguage(path):
    text = pathlib.Path(path).read_bytes().decode("utf-8")
    rows = parse_rows(text)
    out = {}
    for quest_id, record in rows.items():
        if quest_id in SKIP_IDS:
            continue
        entry = clean_scraped(record)
        if any(entry.values()):
            out[quest_id] = entry
    return out


SPOKEN_RECORD = re.compile(r"^\t\[(\d+)\] = \{$")
SPOKEN_FIELD = re.compile(r'^\t\t(accept|complete) = "((?:\\.|[^"\\])*)",?$')
SPOKEN_TITLE = re.compile(r'^\t\t\[(\d+)\] = \{ "((?:\\.|[^"\\])*)"(.*)\},?\s*$')


def load_spoken(directory):
    """Spoken's English quest data: opening text, hand-in text and title per id.

    QuestText.lua keeps what the NPC says when a quest is offered (accept) and
    handed in (complete); Compendium.lua has the English title of every quest
    Forever serves, flagged notext where Spoken has no words for it yet.
    """
    directory = pathlib.Path(directory)
    out = {}
    current = None
    for line in (directory / "QuestText.lua").read_bytes().decode("utf-8").splitlines():
        match = SPOKEN_RECORD.match(line)
        if match:
            current = out.setdefault(int(match.group(1)), {})
            continue
        match = SPOKEN_FIELD.match(line)
        if match and current is not None:
            value = normalize(lua_unquote(match.group(2)))
            if value:
                current["description" if match.group(1) == "accept" else "completion"] = value
    inside = False
    for line in (directory / "Compendium.lua").read_bytes().decode("utf-8").splitlines():
        if line == "\tquests = {":
            inside = True
        elif inside and line == "\t},":
            break
        elif inside:
            match = SPOKEN_TITLE.match(line)
            if match:
                title = normalize(lua_unquote(match.group(2)))
                record = out.setdefault(int(match.group(1)), {})
                if title:
                    record["title"] = title
    return {quest_id: record for quest_id, record in out.items() if record}


def build_number(build):
    return int(str(build).split(".")[-1])


def eg_files(directory, dataset):
    """Efficient Games' files of one dataset, oldest build first, the live game after the beta."""
    found = []
    for path in pathlib.Path(directory).glob("*/*/%s.enUS.json" % dataset):
        found.append((build_number(path.parent.name), path.parent.parent.name == "wowf", path))
    return [path for _, _, path in sorted(found)]


def load_eg(directory):
    """What Efficient Games' players' clients recorded of Forever's quests.

    Returns (quests, texts). quests[id] is the server's description of the quest in
    the newest build that has one, as an entry like a client cache's (title,
    description, objectives, build) plus the amount of each objective, in order.
    texts[id] has the line the NPC says while the quest is in progress and the one
    at hand-in, from the newest build that recorded them, the variant most players
    saw first.
    """
    quests, texts = {}, {}
    for path in eg_files(directory, "quests"):
        build = build_number(path.parent.name)
        for key, record in json.loads(path.read_text(encoding="utf-8"))["quests"].items():
            entry = {
                "id": int(key),
                "title": record.get("title", ""),
                "description": record.get("description", ""),
                "objectives": record.get("objectivesText", ""),
                "amounts": [objective.get("amount", 0) for objective in sorted(
                    record.get("objectives", []), key=lambda o: o.get("storageIndex", 0))],
                "source": "efficient.games",
                "build": build,
                "locale": "enUS",
            }
            if not (entry["title"] or entry["description"] or entry["objectives"]):
                continue
            quests[entry["id"]] = entry  # a later file is a newer build
    for path in eg_files(directory, "texts"):
        for key, record in json.loads(path.read_text(encoding="utf-8"))["quests"].items():
            found = texts.setdefault(int(key), {})
            for said, field in (("progress", "progress"), ("complete", "completion")):
                variants = record.get(said) or []
                if variants and variants[0].get("text"):
                    found[field] = variants[0]["text"]
    return quests, {quest_id: found for quest_id, found in texts.items() if found}


def fetch_eg(directory):
    """Download the quest and text files of every build, as many as are not there yet.

    The repository's own index (data/index.json) names every product, build and
    dataset it holds.
    """
    index_url = EG_RAW + "data/index.json"
    print("reading", index_url)
    request = urllib.request.Request(index_url, headers={"User-Agent": "WordHunterWoW-ENPanel/1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        products = json.load(response)["products"]
    for product in ("wow_classic_beta", "wowf"):
        for build, datasets in products.get(product, {}).items():
            for dataset in ("quests", "texts"):
                if "%s.enUS" % dataset not in datasets:
                    continue
                destination = pathlib.Path(directory) / product / build / ("%s.enUS.json" % dataset)
                if not destination.exists():
                    download(EG_RAW + "data/%s/%s/%s.enUS.json" % (product, build, dataset), destination)


def load_native_jsonl(path):
    out = {}
    path = pathlib.Path(path)
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            out[int(record["id"])] = record
    return out


def load_native_lua(path):
    """An older capture kept as Lua: quests[id] = { title =, description =, objectives =, sourceBuild = }."""
    out = {}
    for quest_id, record in parse_rows(pathlib.Path(path).read_bytes().decode("utf-8")).items():
        if "title" not in record and "description" not in record:
            continue
        out[quest_id] = {
            "id": quest_id,
            "title": record.get("title", ""),
            "description": record.get("description", ""),
            "objectives": record.get("objectives", ""),
            "source": "native capture",
            "build": int(record.get("sourceBuild", 0) or 0),
            "locale": record.get("locale", "enUS"),
        }
    return out


def merge_native(archive, incoming):
    """Newer build wins; the same build, the later file."""
    for quest_id, record in incoming.items():
        old = archive.get(quest_id)
        if old is None or int(record.get("build", 0)) >= int(old.get("build", 0)):
            archive[quest_id] = record
    return archive


def download(url, destination):
    destination = pathlib.Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    print("downloading", url)
    request = urllib.request.Request(url, headers={"User-Agent": "WordHunterWoW-ENPanel/1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        destination.write_bytes(response.read())


def fetch_multilanguage(destination):
    download(MULTILANGUAGE_URL, destination)


def fetch_spoken(directory):
    for name in SPOKEN_FILES:
        download(SPOKEN_URL % name, pathlib.Path(directory) / name)


# --- merge ------------------------------------------------------------------

def assemble(classic, multilanguage, spoken, native, eg_texts, eg_amounts):
    records, report = {}, {"title": {}, "description": {}, "objectives": {}, "progress": {}, "completion": {}}
    resolved = unresolved = 0
    masked = []
    filled = []

    def count(field, source):
        report[field][source] = report[field].get(source, 0) + 1

    picked = []

    for quest_id in sorted(set(classic) | set(multilanguage) | set(spoken) | set(native) | set(eg_texts)):
        cl = classic.get(quest_id, {})
        ml = multilanguage.get(quest_id, {})
        sp = spoken.get(quest_id, {})
        eg = eg_texts.get(quest_id, {})
        na = native.get(quest_id)
        amounts = eg_amounts.get(quest_id) or (na or {}).get("amounts")
        label = "eg" if (na or {}).get("source") == "efficient.games" else "native"
        nat = {}
        if na is not None:
            for field in ("title", "description", "objectives"):
                nat[field] = normalize(na.get(field))
            for field in ("description", "objectives"):
                before = nat[field]
                nat[field] = fill_amounts(nat[field], amounts)
                if MACRO.search(before) and not MACRO.search(nat[field]):
                    filled.append(quest_id)
                    continue
                nat[field] = resolve_macros(nat[field], ml.get(field))
                if MACRO.search(before):
                    if MACRO.search(nat[field]):
                        unresolved += 1
                    else:
                        resolved += 1
        # A few of the Retail copies in Data/Classic carry the same glued-on heading.
        cl = {k: REWARD_HEADING.sub("", normalize(v)).strip() for k, v in cl.items()}

        record = {"id": quest_id}
        sources = {}
        del picked[:]

        def pick(field, candidates):
            for source, value in candidates:
                if value:
                    if amounts and MACRO.search(value):
                        # The amounts Efficient Games lists for the quest's objectives.
                        value = fill_amounts(value, amounts)
                        filled.append(quest_id)
                    if UNKNOWN_NUMBER.search(value):
                        # Shown as X, the way the spell descriptions show an
                        # amount the API could not work out.
                        value = UNKNOWN_NUMBER.sub("X", value)
                        masked.append(quest_id)
                    record[field] = value
                    sources[field] = source
                    picked.append((field, source))
                    return
            record[field] = ""

        pick("title", ((label, nat.get("title")), ("classic", cl.get("title")), ("multilanguage", ml.get("title")),
                       ("spoken", sp.get("title"))))
        # A quest the client has no opening text for falls through to the older
        # sources; they have none either unless the game dropped it since.
        pick("description", ((label, nat.get("description")), ("multilanguage", ml.get("description")),
                             ("spoken", sp.get("description")), ("classic", cl.get("description"))))
        pick("objectives", ((label, nat.get("objectives")), ("classic", cl.get("objectives")),
                            ("multilanguage", ml.get("objectives"))))
        pick("progress", (("eg", normalize(eg.get("progress"))), ("multilanguage", ml.get("progress"))))
        pick("completion", (("eg", normalize(eg.get("completion"))), ("multilanguage", ml.get("completion")),
                            ("spoken", sp.get("completion"))))
        if sources.get("description") == "classic":
            # Every opening text in Data/Classic is a copy of the Retail quest's.
            record["descriptionSource"] = "retail"
        if not any(record.get(f) for f in ("title", "description", "objectives", "progress", "completion")):
            continue
        if JUNK_TITLE.match(record["title"]) and not any(
                record.get(f) for f in ("description", "objectives", "progress", "completion")):
            continue
        if DEVELOPER_TEXT.search(record["title"]):
            continue
        for field, source in picked:
            count(field, source)
        record["from"] = sources
        records[quest_id] = record
    return records, report, resolved, unresolved, len(masked), len(set(filled))


def default_wdb():
    base = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    path = pathlib.Path(base) / "World of Warcraft" / "_forever_" / "Cache" / "WDB" / "enUS" / "questcache.wdb"
    return [str(path)] if path.exists() else []


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--wdb", action="append", default=None,
                        help="a questcache.wdb written by an enUS client (repeatable; default: the Forever install's)")
    parser.add_argument("--native-lua", action="append", default=[],
                        help="an older native capture kept as Lua, e.g. the German Dictionary's Data/forever/enUS_000.lua")
    parser.add_argument("--classic", default=str(ROOT / "Data" / "Classic"))
    parser.add_argument("--multilanguage", default=str(CACHE / "multilanguage_enUS.lua"),
                        help="MultiLanguage's Database/Quests/enUS.lua")
    parser.add_argument("--spoken", default=str(CACHE / "spoken"),
                        help="a folder holding Spoken's QuestText.lua and Compendium.lua (the Spoken_Quests addon's Data folder)")
    parser.add_argument("--eg", default=str(CACHE / "eg"),
                        help="a folder holding Efficient Games' <product>/<build>/quests.enUS.json and texts.enUS.json")
    parser.add_argument("--fetch", action="store_true",
                        help="download the MultiLanguage, Spoken and Efficient Games files that are not there")
    parser.add_argument("--archive", default=str(CACHE / "native_enUS.jsonl"))
    parser.add_argument("--out", default=str(CACHE / "quests_enUS.jsonl"))
    args = parser.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    ml_path = pathlib.Path(args.multilanguage)
    if not ml_path.exists():
        if not args.fetch:
            sys.exit("%s is missing; download it with --fetch or point --multilanguage at the file" % ml_path)
        fetch_multilanguage(ml_path)
    spoken_dir = pathlib.Path(args.spoken)
    if not all((spoken_dir / name).exists() for name in SPOKEN_FILES):
        if not args.fetch:
            sys.exit("%s lacks %s; download them with --fetch or point --spoken at the Spoken_Quests Data folder"
                     % (spoken_dir, " and ".join(SPOKEN_FILES)))
        fetch_spoken(spoken_dir)
    eg_dir = pathlib.Path(args.eg)
    if args.fetch:
        fetch_eg(eg_dir)
    elif not eg_files(eg_dir, "quests"):
        sys.exit("%s holds no Efficient Games quest files; download them with --fetch" % eg_dir)

    archive = load_native_jsonl(args.archive)
    print("native archive: %d quests" % len(archive))
    if not archive and not args.native_lua and not (args.wdb or default_wdb()):
        print("note: no native text at all (no questcache.wdb found); only Classic and MultiLanguage are used")
    for path in args.native_lua:
        added = load_native_lua(path)
        merge_native(archive, added)
        print("  + %s: %d quests" % (path, len(added)))
    wdb_paths = args.wdb if args.wdb is not None else default_wdb()
    for path in wdb_paths:
        try:
            header, records, unreadable = wdb_quests.read_cache(path)
        except (wdb_quests.CacheError, OSError) as error:
            sys.exit("%s: %s" % (path, error))
        if header["locale"] != "enUS":
            sys.exit("%s was written by a %s client; English text needs an enUS one" % (path, header["locale"]))
        entries = {quest_id: wdb_quests.to_entry(quest_id, record, header) for quest_id, record in records.items()}
        before = len(archive)
        merge_native(archive, entries)
        print("  + %s: build %d, %d quests (%d unreadable), %d new" % (
            path, header["build"], len(entries), len(unreadable), len(archive) - before))
    with open(args.archive, "w", encoding="utf-8", newline="\n") as handle:
        for quest_id in sorted(archive):
            handle.write(json.dumps(archive[quest_id], ensure_ascii=False) + "\n")

    classic = load_classic(args.classic)
    multilanguage = load_multilanguage(ml_path)
    spoken = load_spoken(spoken_dir)
    eg_quests, eg_texts = load_eg(eg_dir)
    # Both are the server's own answers. The client cache stays in the archive on
    # its own; here the two are laid over each other, the newer build on top.
    native = merge_native(dict(archive), eg_quests)
    eg_amounts = {quest_id: entry["amounts"] for quest_id, entry in eg_quests.items() if any(entry["amounts"])}
    print("classic: %d, multilanguage: %d, spoken: %d, efficient games: %d (+ %d with dialogue lines), client cache: %d"
          % (len(classic), len(multilanguage), len(spoken), len(eg_quests), len(eg_texts), len(archive)))

    records, report, resolved, unresolved, masked, filled = assemble(
        classic, multilanguage, spoken, native, eg_texts, eg_amounts)
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        for quest_id in sorted(records):
            handle.write(json.dumps(records[quest_id], ensure_ascii=False) + "\n")

    print("\n%d quests -> %s" % (len(records), args.out))
    for field, sources in report.items():
        total = sum(sources.values())
        print("  %-12s %5d   %s" % (field, total, ", ".join("%s %d" % kv for kv in sorted(sources.items()))))
    titled = sum(1 for r in records.values() if r["title"])
    with_text = sum(1 for r in records.values() if r["description"])
    flagged = sum(1 for r in records.values() if r.get("descriptionSource"))
    print("  with a title: %d, with an opening text: %d (%d of them a Retail copy)" % (titled, with_text, flagged))
    print("  objective amounts the game would fill in: %d quests written out from the quest's own objectives, "
          "%d from another source's sentence, %d unknown" % (filled, resolved, unresolved))
    print("  texts with a number nobody has (shown as X): %d" % masked)


if __name__ == "__main__":
    main()
