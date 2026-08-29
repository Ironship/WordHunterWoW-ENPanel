# QuestWordHunter — English Quest Panel

You are playing WoW in German (or French, Spanish, …) on purpose. That is the point. But every so often a sentence is just *too* thick and you want the English version without leaving the game.

It shows the official English title and description for the quest you have open, in its own window, while the game itself stays in the language you are playing.

**It works on its own.** Install it, play in German, French, Spanish, Italian or Portuguese, and read the English when a sentence defeats you. Nothing else is required.

If you also install [QuestWordHunter](https://github.com/Ironship/WordHunterWoW), the two combine: the quest text becomes clickable for saving vocabulary, and this panel can dock beside it instead of floating.

<img width="1044" height="909" alt="{27A402AE-8B2E-4C42-90B0-DF0C4C845C2E}" src="https://github.com/user-attachments/assets/c41b2c8e-3f8f-4d33-a475-0c7fc2e8ddfe" />

About 30,000 quests from Blizzard's Game Data API.

## English names in tooltips

Hover a spell or an NPC and the English name appears on the tooltip the game already draws, under the German or French one. No second window, no hotkey.

Spell and creature names ship with the panel — 8,941 and 13,500 of them, small enough to be free. **Item names are a separate download**, [English Item Names](https://github.com/Ironship/WordHunterWoW-ENPanel-Items): 168,833 entries and around ten megabytes, which is most of what this data weighs, so you decide whether you want them.

Spells also carry their English description, so you learn what the ability does and not just what to search for. 8,319 of the 8,941 have one.

**About the numbers in a spell description.** Blizzard's API publishes a spell's text with base, unscaled values; the game computes what it shows from your character's level and stats. So `Tiger Palm` reads *"dealing 32 Physical damage"* here while your tooltip above says 146. The mechanic is right and anything that does not scale — percentages, durations, target counts — is exact. Only absolute damage and healing figures are indicative.

Substituting the live numbers into the English sentence is not safe: the two languages order them differently in about a fifth of spells, so the damage figure and the duration would swap places. Showing a stale number beats confidently showing the wrong one.

On an English client the whole feature stays quiet — there would be nothing to add.

## What it cannot show you

Blizzard's quest API publishes a quest's title and its opening text and nothing else — no progress line, no hand-in line. So when an NPC is showing you one of those, there is no English to pair with it. Rather than passing the opening text off as a translation of what you are reading, the panel says so in red above it.

## What you need

- Retail 12.1 (`Interface 120100`)
- Nothing else. [QuestWordHunter](https://github.com/Ironship/WordHunterWoW) is optional and adds clickable words on top.

## Rebuild (maintainers)

1. Blizzard keys in `Tools/keys.env` (`BLIZZARD_CLIENT_ID`, `BLIZZARD_CLIENT_SECRET`). Never commit this file.
2. Nothing. `fetch_quests.py` asks the API which quests exist. An optional
   `Data/quest_ids.csv` with an `ID` column is merged in when present.
3. `python Tools/fetch_quests.py`
4. `python Tools/build_quest_lua.py`

Do not commit `Data/cache/`. Commit generated `Data/QuestEN_*.lua`.

All rights reserved.
