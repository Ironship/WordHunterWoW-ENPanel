# The 1.12 build

This branch is the copy of this addon that runs on World of Warcraft **1.12.1**
(`## Interface: 11200`), taken off the Project Legacy client it was living on.

An orphan branch, with no ancestor on `main`, because it is a different build
of the same idea rather than a divergence from a commit. Merging it into `main`
is not the intention.

## Why it is here

Until 2026-09-14 it was in exactly one place. An audit found no repository, no
branch and no tag for it anywhere, and `Tools/build_release.ps1` accepts only
`retail` and `classic`, so nothing built it. Deleting that game folder would
have deleted the work.

The companion branch in `WordHunterWoW` carries the part that mattered beyond
the port: its `Compat.lua` answered CLASSIC where `main` answered RETAIL on a
client that defines neither project global. That fix is in `WordHunterWoW`
1.19.3 now, with a test behind it.

Unmodified: this is the snapshot as it ran.
