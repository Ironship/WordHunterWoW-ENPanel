# QuestWordHunter — English Quest Panel

You are playing WoW in German (or French, Spanish, …) on purpose. That is the point. But every so often a sentence is just *too* thick and you want the English version without leaving the game.

This optional addon sits next to [QuestWordHunter](https://github.com/Ironship/WordHunterWoW) and shows the official English title and description for the quest you have open. The base addon still reads the original language so you can click and save those words.

<img width="1044" height="909" alt="{27A402AE-8B2E-4C42-90B0-DF0C4C845C2E}" src="https://github.com/user-attachments/assets/c41b2c8e-3f8f-4d33-a475-0c7fc2e8ddfe" />

About 30,000 quests from Blizzard's Game Data API.

## What it cannot show you

Blizzard's quest API publishes a quest's title and its opening text and nothing else — no progress line, no hand-in line. So when an NPC is showing you one of those, there is no English to pair with it. Rather than passing the opening text off as a translation of what you are reading, the panel says so in red above it.

## What you need

- Retail 12.1 (`Interface 120100`)
- [QuestWordHunter](https://github.com/Ironship/WordHunterWoW) — this pack does nothing without it

## Rebuild (maintainers)

1. Blizzard keys in `Tools/keys.env` (`BLIZZARD_CLIENT_ID`, `BLIZZARD_CLIENT_SECRET`). Never commit this file.
2. Wago QuestV2 CSV → `Data/QuestV2.csv` (gitignored).
3. `python Tools/fetch_quests.py`
4. `python Tools/build_quest_lua.py`

Do not commit `Data/cache/` or `QuestV2.csv`. Commit generated `Data/QuestEN_*.lua`.

All rights reserved.
