#!/usr/bin/env python3
"""Replace the numbers in a spell description that the game scales for the player.

The Game Data API answers a spell's description with its numbers already worked
out -- for some default character, not for the one reading the tooltip. On
Retail the damage, healing and absorb amounts, and flat stat bonuses, depend on
level, gear and talents, so "causing 38 Physical damage" is simply wrong for
nearly everybody, and where the API could not work a value out at all it says
"deals 0 Physical damage". The tooltip would be better off admitting that:
"causing X Physical damage".

Only those amounts are masked. Percentages, durations, ranges, counts of targets,
stacks and charges, and resource generation ("Generates 20 Rage") are design
values the player can rely on, so they stay.

    python Tools/scaling.py Data/DescSpell.lua            # rewrite in place
    python Tools/scaling.py Data/DescSpell.lua --dry-run  # only say what changes
    python Tools/scaling.py ../WordHunterWoW-ENPanel-Items/Data/DescItem_000.lua --zeros-only

build_names_lua.py applies the same function to a Retail description table, so a
rebuilt table comes out masked and masking an already masked one changes nothing.
Item effects are different: an item's figures are fixed by the item, so only the
amounts the API could not work out (it answers 0) are replaced, with --zeros-only.
"""
import argparse, pathlib, re, sys

# "1,721", "1147.7", "38" -- a comma only inside a number, never the one after it
NUM = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
# What may stand between an amount and the word "damage": a damage school or a
# word that qualifies it. Kept to a list on purpose -- "2 times the normal damage"
# and "10 sec and its damage" are not amounts of damage.
QUALIFIER = (r"additional|bonus|extra|total|magic|physical|shadow|fire|nature|holy|arcane|frost|chaos|bleed|"
             r"cosmic|shadowflame|astral|radiant|shadowfrost|volcanic|spellfrost|stormstrike|plague|"
             r"elemental|flamestrike|shadowstrike|holystrike|frostfire")
# Right after an amount, so that "for 10 sec", "by 5%" or "heals 5 injured allies" is
# never taken for one: those are a time, a percentage and a number of targets.
NOT_A_UNIT = (r"(?![\d,]|\.\d|%|\s*(?:(?:additional|injured|nearby|other|friendly|wounded)\s+)*"
              r"(?:sec|seconds?|min|minutes?|hours?|yd|yds|yards?|times|stacks?|charges?|points?|"
              r"targets?|enem(?:y|ies)|all(?:y|ies)|members?|players?)\b)")
STATS = (r"strength|agility|intellect|stamina|armor|haste|critical strike|mastery|versatility|"
         r"attack power|spell power|avoidance|leech|maximum health|max health|stats?")
SCHOOL = (r"physical|shadow|fire|nature|holy|arcane|frost|chaos|bleed|cosmic|shadowflame|astral|radiant|"
          r"shadowfrost|volcanic|magic|spellfrost|plague|elemental|frostfire")
# What "restores 100 ..." can restore that is a fixed design value, not a scaled amount.
RESOURCE = (r"energy|rage|fury|focus|runic power|astral power|insanity|maelstrom|chi|holy power|soul|"
            r"combo|essence|lunar|fel|arcane charges?|mana|health")

RULES = [
    # "dealing 444 Nature damage", "absorbing 2,280 damage", "139 Physical damage",
    # "798 Arcane damage", also a range: "100 to 150 Fire damage".
    (re.compile(rf"(?<![\w.,])({NUM})(?:\s+to\s+{NUM})?(?!%)(?=(?:\s+(?:{QUALIFIER}))*\s+damage\b)", re.I), "X"),
    # "2,802 healing", "restoring 837 health", "a Psyfiend with 1,222 health", "granting 450 mana"
    (re.compile(rf"(?<![\w.,])({NUM})(?!%)(?=\s+(?:healing|health|mana)\b)", re.I), "X"),
    # "healing them for 5,730 over 2.7 sec", "heals you for 2,000"; not "heals you for 20%"
    (re.compile(rf"(\b(?:heal\w*|restor\w+|replenish\w*)\s+(?:[A-Za-z']+\s+){{0,3}}for\s+)({NUM}){NOT_A_UNIT}", re.I), r"\1X"),
    # "increasing Armor by 110", "Increases your critical strike by 6", "maximum health by 95"
    (re.compile(rf"(\b(?:{STATS})(?:\s+rating)?\s+by\s+)({NUM}){NOT_A_UNIT}", re.I), r"\1X"),
    # "gain 8 Intellect for 20 sec", "+12 Armor", "gain 0 Intellect"
    (re.compile(rf"(?<![\w.,])({NUM})(?!%)(?=\s+(?:{STATS})\b)", re.I), "X"),
    # "absorbing 30% of incoming damage, up to 2,381 total"
    (re.compile(rf"(\bup to\s+)({NUM})(?=\s+total\b)", re.I), r"\1X"),
    # An amount spread over time: "healed for an additional 281 over 4 sec", "8 over 1 sec"
    (re.compile(rf"(?<![\w.,])({NUM})(?!%)(?=\s+over\s+\d)", re.I), "X"),
    # "dealing 6,739 Shadowflame over 3 sec": a school with no "damage" after it
    (re.compile(rf"(?<![\w.,])({NUM})(?!%)(?=\s+(?:{SCHOOL})\s+over\b)", re.I), "X"),
    # "up to a maximum of 3,055"; only the thousands, because "a maximum of 10 Runic Power" is a count
    (re.compile(rf"(\bmaximum of\s+)(\d{{1,3}}(?:,\d{{3}})+){NOT_A_UNIT}", re.I), r"\1X"),
    # Heals "all allies within 40 yards for 19,392" and "within 10 yds for 150"
    (re.compile(rf"(\b(?:yd|yds|yards?)\s+for\s+)({NUM}){NOT_A_UNIT}", re.I), r"\1X"),
    # "Heals 757 instantly", "restores 4,245 of a friendly target's health" -- not "Restore 100 Energy"
    (re.compile(rf"(\b(?:heals?|healing|restor(?:e|es|ing))\s+)({NUM}){NOT_A_UNIT}(?!\s+(?:of\s+your\s+)?(?:{RESOURCE})\b)", re.I), r"\1X"),
    # "absorbing X damage plus 611 for each Soul Fragment consumed"
    (re.compile(rf"(\bplus\s+)({NUM})(?=\s+for each\b)", re.I), r"\1X"),
    # What is left with a thousands separator is an amount nearly everywhere: "absorb shield for 25,000"
    (re.compile(rf"(?<![\w.,])(\d{{1,3}}(?:,\d{{3}})+){NOT_A_UNIT}", re.I), "X"),
]


def _only_zero(rule, replacement):
    """The rule's replacement, applied only where the amount it found is 0."""
    # A rule has either just the number in group 1 or a prefix in group 1 and the
    # number in group 2.
    group = 1 if rule.groups == 1 else 2

    def replace(found):
        if float(found.group(group).replace(",", "")) != 0:
            return found.group(0)
        return found.expand(replacement)
    return replace


def mask(text, zeros_only=False):
    """The description with its scaled amounts replaced by X.

    `zeros_only` replaces only the amounts the API could not work out and so
    answered as 0 ("Restores 0 health over 18 sec"). That is for item effects: an
    item's own figures are fixed by the item, so "Restores 1,250 health" is right
    and stays, while a 0 is plainly a failure to work the figure out.
    """
    for pattern, replacement in RULES:
        text = pattern.sub(_only_zero(pattern, replacement) if zeros_only else replacement, text)
    return text


# --- the Lua table, for rewriting an existing Data/DescSpell.lua or DescItem_*.lua --

LINE = re.compile(r'^(WordHunterWoW_ENDesc_(?:Spell|Item)\[\d+\] = )"(.*)"$')


def unquote(body):
    out, i = [], 0
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            out.append({"n": "\n", "\\": "\\", '"': '"'}.get(body[i + 1], body[i + 1]))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def quote(value):
    return '"' + (value.replace("\\", "\\\\").replace('"', '\\"')
                       .replace("\r", "").replace("\n", "\\n")) + '"'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=pathlib.Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--zeros-only", action="store_true",
                    help="item effects: replace only the amounts the API answered as 0")
    args = ap.parse_args()

    lines = args.path.read_text(encoding="utf-8").split("\n")
    changed = 0
    for index, line in enumerate(lines):
        found = LINE.match(line)
        if not found:
            continue
        before = unquote(found.group(2))
        after = mask(before, args.zeros_only)
        if after != before:
            changed += 1
            lines[index] = found.group(1) + quote(after)
    print(f"{args.path.name}: {changed:,} descriptions {'would change' if args.dry_run else 'rewritten'}")
    if not args.dry_run and changed:
        args.path.write_text("\n".join(lines), encoding="utf-8", newline="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
