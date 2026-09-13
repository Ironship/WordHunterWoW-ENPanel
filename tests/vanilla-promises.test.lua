-- Run from the addon root:  lua tests/vanilla-promises.test.lua
--
-- The README ships to both builds and the two builds do not hold the same
-- thing. Retail loads NamesSpell, NamesNPC and DescSpell; Classic Era loads
-- none of them, and Names.lua initialises the tables to empty and returns nil
-- for every lookup. No error, no warning, no English on a single Classic spell
-- or NPC tooltip -- while the README told the reader to expect 8,941 spells
-- and 13,500 creatures.
--
-- An audit raised it as a packaging contract: either the Vanilla manifest is
-- missing data files or the README overpromises, and one of the two has to
-- move. The README moved, because the data is keyed by id and was read from
-- Retail -- Blizzard rewrote abilities across expansions and Classic Era still
-- runs the originals, so shipping it would put an English name on a Classic
-- tooltip that is sometimes the wrong ability's. A wrong name nobody can see
-- is wrong beats no name only until somebody believes it.
--
-- What this holds is that the two cannot drift apart again silently. If the
-- data is ever added to the Vanilla manifest, this fails and asks for the
-- qualification to come out of the README with it.

local function read(path)
  local handle = assert(io.open(path, "r"), "cannot read " .. path)
  local text = handle:read("*a")
  handle:close()
  return text
end

local vanilla = read("WordHunterWoW-ENPanel_Vanilla.toc")
local mainline = read("WordHunterWoW-ENPanel_Mainline.toc")
local readme = read("README.md")

-- The three files the tooltips need, named as the manifests name them.
local NAME_DATA = { "Data/NamesSpell.lua", "Data/NamesNPC.lua", "Data/DescSpell.lua" }

local inVanilla, inMainline = {}, {}
for _, file in ipairs(NAME_DATA) do
  inVanilla[file] = vanilla:find(file, 1, true) ~= nil
  inMainline[file] = mainline:find(file, 1, true) ~= nil
  assert(inMainline[file], "Retail is supposed to load " .. file .. " and does not")
end

local vanillaHasData = false
for _, file in ipairs(NAME_DATA) do
  if inVanilla[file] then vanillaHasData = true end
end

-- Every line of the README that makes the promise, found by what it promises
-- rather than by its wording, so rephrasing the sentence does not slip past.
local promises = {}
for line in readme:gmatch("[^\n]+") do
  if line:find("8,941", 1, true) or line:find("13,500", 1, true) then
    promises[#promises + 1] = line
  end
end
assert(#promises >= 2,
  "the README no longer states the spell and creature counts; this test is pinned to them")

if vanillaHasData then
  -- Somebody added the data to Classic. Good -- but then the qualification is
  -- a lie in the other direction, and the paragraph explaining its absence is
  -- describing a thing that is no longer absent.
  for _, line in ipairs(promises) do
    assert(not line:find("Retail only", 1, true),
      "Classic now loads the name data, so the README must stop saying Retail only:\n  " .. line)
  end
  assert(not readme:find("The spell and NPC tooltips are not", 1, true),
    "Classic now loads the name data, so the section explaining its absence has to go")
else
  for _, line in ipairs(promises) do
    assert(line:find("Retail only", 1, true),
      "Classic loads no name data, so this promise has to say so:\n  " .. line)
  end
  assert(readme:find("On Classic Era", 1, true),
    "and the README has to say what a Classic Era player does and does not get")
end

-- The Vanilla manifest's own Notes never made the promise. Kept under test so
-- it does not acquire one later from a copy of the Mainline line.
local notes = vanilla:match("## Notes:([^\n]*)") or ""
assert(not notes:lower():find("spell") and not notes:lower():find("npc"),
  "the Classic Era manifest must not promise tooltips it has no data for:\n  " .. notes)

print("vanilla-promises: ok  (Classic name data: " ..
  (vanillaHasData and "shipped" or "absent, and the README says so") .. ")")
