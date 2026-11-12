# QuestWordHunter — English Quest Panel

Controllers can scroll the panel with D-pad up/down or LB/RB and close it with B / Circle. The footer shows the client's button labels. With ConsolePort active, its interface cursor handles the panel instead.

Play WoW in German, French, Spanish, Italian or Portuguese, and read the English whenever a sentence defeats you.

The quest you have open appears in English in its own window, next to the original. Hover a spell or an NPC and its English name and description appear on the tooltip you are already looking at.

<img width="1044" height="909" alt="English quest panel" src="https://github.com/user-attachments/assets/c41b2c8e-3f8f-4d33-a475-0c7fc2e8ddfe" />

## What you get

- **English quest text** — 49,141 Retail quests, 4,244 Classic and 5,285 for WoW: Forever, title and description
- **English spell names** on tooltips — 11,038 spells, with 10,220 descriptions *(Retail only)*
- **English NPC names** on tooltips — 13,500 creatures *(Retail only)*
- **English item names** — a separate download, [English Item Names](https://github.com/Ironship/WordHunterWoW-ENPanel-Items), 168,833 items

Playing in English already? The addon stays quiet — there is nothing for it to add.

## On Classic Era

The quest text is there — 4,244 Classic quests, harvested from a Classic client
and shipped in the Classic Era build.

The spell and NPC tooltips are not. That data is keyed by id and was read from
Retail, and the two games do not always mean the same thing by the same id:
Blizzard rewrote abilities across expansions and Classic Era still runs the
originals. Shipping it anyway would put an English name on a Classic tooltip
that is sometimes the wrong ability's name, and a wrong name nobody can see is
wrong about is worse than no name at all. So the Classic Era build loads none
of it, and these tooltips stay as the game draws them until the data has been
read from a Classic client too.

## On WoW: Forever

5,285 quests, put together from what the Forever client itself received from the server, the Classic data,
the Forever data of the MultiLanguage addon by Ruben Zantingh (used with his permission) and the quest data of
the Spoken addon by Rusty Key (MIT). Most of them also carry the line the NPC says while the quest is in
progress and the one at hand-in, so the panel shows the passage you are actually reading. The new quests that
only Forever has are in as far as any source has their text; for the rest there is no English text yet, and
the panel says so. A number the game works out from its own data tables is shown as **X**. `NOTICE` has the
details and the licences.

## Install

Unzip into `_retail_\Interface\AddOns\`, `_classic_era_\Interface\AddOns\` or
`_forever_\Interface\AddOns\` and restart the game.

Nothing else is required. If you also install [QuestWordHunter](https://github.com/Ironship/WordHunterWoW), the quest text becomes clickable so you can save words you want to learn, this panel docks beside it, and pointing at a word lights up the English sentence that says the same thing.

## Good to know

Blizzard's description API works its numbers out for a default character, not for yours, so on Retail the amounts that scale with level, gear and talents — damage, healing, absorbs and flat stat bonuses — are shown as **X** ("causing X Frost damage") instead of a figure that would be wrong for most players. Read the real amount off the tooltip above the English block. Percentages, durations, ranges and counts are the spell's base values and are kept; talents can still change them.

Spell data was refreshed from Blizzard's Retail 12.1.5 API on 14 October 2026.
Coverage was checked for all 13 classes, 40 specializations, 41 hero trees and
407 PvP talents, in addition to the full spell search. Some API records have no
description, including six class talents; those tooltips receive a name only.

Some quests have no English text for their progress or hand-in lines, because Blizzard does not publish it. The panel tells you when that happens instead of showing you the wrong passage.

Retail 12.1 (interface 120100), Classic Era 1.15.9 (11509) and WoW: Forever
(16001) — one manifest each. What the Classic build does and does not carry is
set out above.

## Rebuild (maintainers)

Blizzard API keys in `Tools/keys.env`, then:

```
python Tools/fetch_quests.py
python Tools/build_quest_lua.py
python Tools/fetch_names.py --kind spell
python Tools/fetch_names.py --kind creature
python Tools/fetch_descriptions.py --kind spell --retry-empty
python Tools/build_names_lua.py --kind spell --out Data
python Tools/build_names_lua.py --kind creature --out Data
python Tools/build_names_lua.py --kind spell --desc --out Data   # also masks scaled amounts as X (Tools/scaling.py)
```

Commit the generated `Data/*.lua`. Do not commit `Data/cache/`.

Both fetch commands accept `--keys-file <path>` when the credentials are kept
outside this checkout. `--retry-empty` asks again for descriptions that were
previously unavailable. Failed requests and truncated searches return a failure
status, leaving the cache available for another run.

The Retail spell search includes IDs below 2,000,000. Use `--max-id` to extend
that range when new spells exceed it; older imports stopped at 500,000 and
missed the newer Rogue abilities entirely.

## WoW: Forever

The client keeps the text of every quest the server has told it about, the ones the player never took
included, in `Cache\WDB\<locale>\questcache.wdb`. In an English client that is the game's own English.
Blizzard's API has none of the new Forever quests, so this is where they come from.

`Tools/QuestSweep` is a small addon for the maintainer: copy it into the AddOns folder, run an English
client, `/qsweep start`, and it asks the server about every quest id, slowly, so the cache fills with all of
them. Log out when it says it is done, then:

```
python Tools/build_forever_quests.py --fetch --wdb "<game>\_forever_\Cache\WDB\enUS\questcache.wdb"
python Tools/build_quest_lua.py --cache Data/cache/forever/quests_enUS.jsonl --out Data/Forever --chunk 1000 --toc WordHunterWoW-ENPanel_Camelot.toc --flavor forever
```

The client's cache does not keep everything it has ever held, so every run adds what it reads to
`Data/cache/forever/native_enUS.jsonl`, and the build reads from there. `--native-lua` takes an older capture
kept as Lua (the German Dictionary's `QuestData/Data/forever/enUS_000.lua` is one). The MultiLanguage file is
fetched at the revision named in `Tools/build_forever_quests.py`. The script's header says which source wins
for which field.

## Classic Era and Season of Discovery

Blizzard's Game Data API has no quest endpoint for Classic at all, so the
Classic quest data is not fetched the way the Retail data is. It is extracted
from a local quest database:

```
lua Tools/extract_classic_quests.lua <db.lua> Data/cache/classic/quests_en.jsonl <locale.lua> deDE
python Tools/build_quest_lua.py --cache Data/cache/classic/quests_en.jsonl --out Data/Classic --chunk 1000
```

Classic quests carry a title and an objective line but no offer text, because
the source has none. Where the Retail data holds the same quest id, its
description is copied over by `Tools/backfill_classic.py`, so most Classic
quests read in full rather than falling back to the objective. It is
Blizzard's own text, not an invented one -- but Blizzard rewrote many quests
over the expansions, and where they did the English on screen may be a newer
telling than the Classic one beside it. Ids with no Retail twin keep the empty
description, and the panel keeps saying so instead of showing something
that is not theirs. The panel shows what exists and does not invent the rest.

## Licence

GPL v3 — see `LICENSE`, and `NOTICE` for the attribution the licence requires.
