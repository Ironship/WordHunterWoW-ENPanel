# QuestWordHunter — English Quest Panel

Play WoW in German, French, Spanish, Italian or Portuguese, and read the English whenever a sentence defeats you.

The quest you have open appears in English in its own window, next to the original. Hover a spell or an NPC and its English name and description appear on the tooltip you are already looking at.

<img width="1044" height="909" alt="English quest panel" src="https://github.com/user-attachments/assets/c41b2c8e-3f8f-4d33-a475-0c7fc2e8ddfe" />

## What you get

- **English quest text** — 49,041 Retail quests and 4,244 Classic, title and description
- **English spell names and descriptions** on tooltips — 8,941 spells
- **English NPC names** on tooltips — 13,500 creatures
- **English item names** — a separate download, [English Item Names](https://github.com/Ironship/WordHunterWoW-ENPanel-Items), 168,833 items

Playing in English already? The addon stays quiet — there is nothing for it to add.

## Install

Unzip into `_retail_\Interface\AddOns\` and restart the game.

Nothing else is required. If you also install [QuestWordHunter](https://github.com/Ironship/WordHunterWoW), the quest text becomes clickable so you can save words you want to learn, and this panel docks beside it.

## Good to know

A spell's English description shows Blizzard's standard values, so a damage number may not match the one your character rolls. Everything else — what the ability does, percentages, durations — is exact.

Some quests have no English text for their progress or hand-in lines, because Blizzard does not publish it. The panel tells you when that happens instead of showing you the wrong passage.

Retail 12.1. All rights reserved.

## Rebuild (maintainers)

Blizzard API keys in `Tools/keys.env`, then:

```
python Tools/fetch_quests.py
python Tools/build_quest_lua.py
python Tools/fetch_names.py --kind spell
python Tools/fetch_names.py --kind creature
python Tools/fetch_descriptions.py --kind spell
python Tools/build_names_lua.py --kind spell --out Data
python Tools/build_names_lua.py --kind creature --out Data
python Tools/build_names_lua.py --kind spell --desc --out Data
```

Commit the generated `Data/*.lua`. Do not commit `Data/cache/`.

## Classic Era and Season of Discovery

Blizzard's Game Data API has no quest endpoint for Classic at all, so the
Classic quest data is not fetched the way the Retail data is. It is extracted
from a local quest database:

```
lua Tools/extract_classic_quests.lua <db.lua> Data/cache/classic/quests_en.jsonl <locale.lua> deDE
python Tools/build_quest_lua.py --cache Data/cache/classic/quests_en.jsonl --out Data/Classic --chunk 1000
```

Classic quests carry a title and an objective line but no offer text, because
the source has none. The panel shows what exists and does not invent the rest.

## Licence

GPL v3 — see `LICENSE`, and `NOTICE` for the attribution the licence requires.
