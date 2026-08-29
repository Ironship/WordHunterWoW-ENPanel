-- Run from the addon root:  lua tests/names.test.lua
-- Drive Names.lua against a stubbed retail tooltip API.
local postCalls = {}
TooltipDataProcessor = {
  AllTypes = "all",
  AddTooltipPostCall = function(_, fn) postCalls[#postCalls + 1] = fn end,
}
Enum = { TooltipDataType = { Item = 1, Spell = 2, Unit = 3, Macro = 4 } }

local locale = "deDE"
GetLocale = function() return locale end
strsplit = function(sep, s)
  local out = {}
  for piece in (s .. sep):gmatch("([^" .. sep .. "]*)" .. sep) do out[#out + 1] = piece end
  return table.unpack(out)
end

local guids = { player = "Creature-0-4379-0-27-30-000082EF89", pet = "Pet-0-1-2-3-4-5-6" }
UnitGUID = function(unit) return guids[unit] end

local function makeTooltip(name, firstLine)
  local tt = { lines = {}, shown = 0 }
  function tt:GetName() return name end
  function tt:AddDoubleLine(l, r) self.lines[#self.lines + 1] = l .. " = " .. r end
  function tt:AddLine(text) self.lines[#self.lines + 1] = text end
  function tt:Show() self.shown = self.shown + 1 end
  _G[name .. "TextLeft1"] = { GetText = function() return firstLine end }
  return tt
end

GameTooltip = makeTooltip("GameTooltip", "Feuerball")
ItemRefTooltip = makeTooltip("ItemRefTooltip", "x")
local Other = makeTooltip("OtherTooltip", "x")

local events
CreateFrame = function()
  events = { RegisterEvent = function() end }
  function events:SetScript(_, fn) self.fn = fn end
  return events
end

dofile("Data/NamesSpell.lua")
dofile("Data/NamesNPC.lua")
local chunk = assert(loadfile("Names.lua"))
chunk("WordHunterWoW-ENPanel")
events.fn(nil, "ADDON_LOADED", "WordHunterWoW-ENPanel")
assert(#postCalls == 1, "tooltip hook not registered")
local hook = postCalls[1]
local N = WordHunterWoW_ENPanelNames

local function reset(tt) tt.lines, tt.shown = {}, 0 end

-- spell: German client should get the English name appended
reset(GameTooltip)
hook(GameTooltip, { type = 2, id = 133 })
assert(GameTooltip.lines[1] == " ", "a blank line must come first")
assert(GameTooltip.lines[2] == "English = Fireball", "spell: " .. tostring(GameTooltip.lines[2]))

-- npc: the creature id has to come out of the guid, not data.id
reset(GameTooltip)
hook(GameTooltip, { type = 3, id = "player" })
assert(GameTooltip.lines[2] == "English = Forest Spider", "npc: " .. tostring(GameTooltip.lines[2]))

-- a pet guid is not a creature and must not be looked up
reset(GameTooltip)
hook(GameTooltip, { type = 3, id = "pet" })
assert(#GameTooltip.lines == 0, "pet guid should be ignored")

-- item with no pack installed: nothing to add, and no error
reset(GameTooltip)
hook(GameTooltip, { type = 1, id = 19019 })
assert(#GameTooltip.lines == 0, "item without the pack should add nothing")

-- now the optional pack registers itself
assert(N.Register("item", { [19019] = "Thunderfury, Blessed Blade of the Windseeker" }))
reset(GameTooltip)
hook(GameTooltip, { type = 1, id = 19019 })
assert(GameTooltip.lines[2]:find("Thunderfury", 1, true), "item after register: " .. tostring(GameTooltip.lines[2]))

-- an unknown id adds nothing rather than an empty line
reset(GameTooltip)
hook(GameTooltip, { type = 2, id = 999999 })
assert(#GameTooltip.lines == 0, "unknown id must add nothing")

-- tooltips that are not the game or link tooltip are left alone
reset(Other)
hook(Other, { type = 2, id = 133 })
assert(#Other.lines == 0, "unrelated tooltip must be untouched")

-- an English client needs none of this
locale = "enUS"
reset(GameTooltip)
hook(GameTooltip, { type = 2, id = 133 })
assert(#GameTooltip.lines == 0, "English client should get nothing")
locale = "deDE"

-- turning it off works
N.SetEnabled(false)
reset(GameTooltip)
hook(GameTooltip, { type = 2, id = 133 })
assert(#GameTooltip.lines == 0, "disabled should add nothing")
N.SetEnabled(true)

-- a tooltip already titled with the English name should not repeat it
_G["GameTooltipTextLeft1"] = { GetText = function() return "Fireball" end }
reset(GameTooltip)
hook(GameTooltip, { type = 2, id = 133 })
assert(#GameTooltip.lines == 0, "must not repeat the title back")

-- descriptions
_G["GameTooltipTextLeft1"] = { GetText = function() return "Feuerball" end }
WordHunterWoW_ENDesc_Spell[133] = "Hurls a fiery ball that causes damage."
reset(GameTooltip)
hook(GameTooltip, { type = 2, id = 133 })
assert(GameTooltip.lines[1] == " ", "separator")
assert(GameTooltip.lines[2] == "English = Fireball", "name line: " .. tostring(GameTooltip.lines[2]))
assert(GameTooltip.lines[3] == "Hurls a fiery ball that causes damage.", "desc line: " .. tostring(GameTooltip.lines[3]))

-- a spell with a name but no description still gets its name
reset(GameTooltip)
hook(GameTooltip, { type = 2, id = 585 })
assert(#GameTooltip.lines == 2, "separator + name when there is no description")

-- when the tooltip already says the English name, the description is still
-- worth adding on its own -- but the repeated name is not
_G["GameTooltipTextLeft1"] = { GetText = function() return "Fireball" end }
reset(GameTooltip)
hook(GameTooltip, { type = 2, id = 133 })
assert(#GameTooltip.lines == 2 and GameTooltip.lines[2]:find("Hurls", 1, true),
       "English client name repeat: " .. tostring(GameTooltip.lines[2]))
_G["GameTooltipTextLeft1"] = { GetText = function() return "Feuerball" end }

-- an empty description string must not produce a blank line
WordHunterWoW_ENDesc_Spell[2050] = ""
reset(GameTooltip)
hook(GameTooltip, { type = 2, id = 2050 })
assert(#GameTooltip.lines == 2, "empty description must not add a line")

local c = N.Counts()
print(string.format("all assertions passed  (spell=%d npc=%d item=%d)", c.spell, c.npc, c.item or 0))
