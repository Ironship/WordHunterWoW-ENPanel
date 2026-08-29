# QuestWordHunter — English Quest Panel

You are playing WoW in German (or French, Spanish, …) on purpose. That is the point. But every so often a sentence is just *too* thick and you want the English version without leaving the game.

It shows the official English title and description for the quest you have open, in its own window, while the game itself stays in the language you are playing.

**It works on its own.** Install it, play in German, French, Spanish, Italian or Portuguese, and read the English when a sentence defeats you. Nothing else is required.

If you also install [QuestWordHunter](https://github.com/Ironship/WordHunterWoW), the two combine: the quest text becomes clickable for saving vocabulary, and this panel can dock beside it instead of floating.

<img width="1044" height="909" alt="{27A402AE-8B2E-4C42-90B0-DF0C4C845C2E}" src="https://github.com/user-attachments/assets/c41b2c8e-3f8f-4d33-a475-0c7fc2e8ddfe" />

About 30,000 quests from Blizzard's Game Data API.

## What it cannot show you

Blizzard's quest API publishes a quest's title and its opening text and nothing else — no progress line, no hand-in line. So when an NPC is showing you one of those, there is no English to pair with it. Rather than passing the opening text off as a translation of what you are reading, the panel says so in red above it.

## What you need

- Retail 12.1 (`Interface 120100`)
- Nothing else. [QuestWordHunter](https://github.com/Ironship/WordHunterWoW) is optional and adds clickable words on top.

## Rebuild (maintainers)

1. Blizzard keys in `Tools/keys.env` (`BLIZZARD_CLIENT_ID`, `BLIZZARD_CLIENT_SECRET`). Never commit this file.
2. A quest id list at `Data/quest_ids.csv` — one `ID` column. Gitignored.
3. `python Tools/fetch_quests.py`
4. `python Tools/build_quest_lua.py`

Do not commit `Data/cache/` or `quest_ids.csv`. Commit generated `Data/QuestEN_*.lua`.

All rights reserved.
