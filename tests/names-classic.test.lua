-- Run from the addon root:  lua tests/names-classic.test.lua
--
-- Drive Names.lua against a Classic tooltip API: no TooltipDataProcessor, so
-- the tooltip has to be asked what it is showing through its own scripts. Two
-- things are worth proving here beyond "a line appears".
--
--   * Adding a line calls Show(), and on the script path Show() can put the
--     tooltip back through the hook that added the line. Without a guard the
--     tooltip appends to itself until the client gives up.
--   * The newer API must still win where it exists, so that a Classic client
--     that has both does not take the older path.

local locale = "deDE"
GetLocale = function() return locale end
strsplit = function(sep, s)
  local out = {}
  for piece in (s .. sep):gmatch("([^" .. sep .. "]*)" .. sep) do out[#out + 1] = piece end
  return table.unpack(out)
end
UnitGUID = function(unit)
  return unit == "mouseover" and "Creature-0-4379-0-27-30-000082EF89" or nil
end

-- A tooltip that behaves like Classic's: scripts are hooked onto it, and it
-- reports what it holds rather than being handed a data table.
local function makeTooltip(name)
  local tt = { lines = {}, shown = 0, scripts = {} }
  function tt:GetName() return name end
  function tt:AddDoubleLine(l, r) self.lines[#self.lines + 1] = l .. " = " .. r end
  function tt:AddLine(text) self.lines[#self.lines + 1] = text end
  function tt:HookScript(event, fn)
    self.scripts[event] = self.scripts[event] or {}
    table.insert(self.scripts[event], fn)
  end
  function tt:Fire(event)
    for _, fn in ipairs(self.scripts[event] or {}) do fn(self) end
  end
  -- This is the trap: showing the tooltip re-runs the script that fired.
  function tt:Show()
    self.shown = self.shown + 1
    if self.reentrant then self:Fire(self.reentrant) end
  end
  function tt:GetItem() return self.itemName, self.itemLink end
  function tt:GetSpell() return self.spellName, self.spellId end
  function tt:GetUnit() return self.unitName, self.unitToken end
  _G[name .. "TextLeft1"] = { GetText = function() return "irgendwas" end }
  return tt
end

GameTooltip = makeTooltip("GameTooltip")
ItemRefTooltip = makeTooltip("ItemRefTooltip")

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

local N = WordHunterWoW_ENPanelNames
assert(GameTooltip.scripts["OnTooltipSetItem"], "the Classic path never hooked the tooltip")
assert(ItemRefTooltip.scripts["OnTooltipSetSpell"], "chat links were left unhooked")

local function reset(tt) tt.lines, tt.shown, tt.reentrant = {}, 0, nil end

-- spell -----------------------------------------------------------------------
reset(GameTooltip)
GameTooltip.spellName, GameTooltip.spellId = "Feuerball", 133
GameTooltip:Fire("OnTooltipSetSpell")
assert(GameTooltip.lines[1] == " ", "a blank line must come first")
assert(GameTooltip.lines[2] == "English = Fireball", "spell: " .. tostring(GameTooltip.lines[2]))

-- npc: the creature id comes out of the guid, and a pet is not a creature ------
reset(GameTooltip)
GameTooltip.unitName, GameTooltip.unitToken = "Waldspinne", "mouseover"
GameTooltip:Fire("OnTooltipSetUnit")
assert(GameTooltip.lines[2] == "English = Forest Spider", "npc: " .. tostring(GameTooltip.lines[2]))

-- item: the id has to be parsed out of the link, not guessed -------------------
assert(N.Register("item", { [19019] = "Thunderfury, Blessed Blade of the Windseeker" }))
reset(GameTooltip)
GameTooltip.itemName = "Donnerzorn"
GameTooltip.itemLink = "|cff0070dd|Hitem:19019::::::::60:::::|h[Donnerzorn]|h|r"
GameTooltip:Fire("OnTooltipSetItem")
assert(GameTooltip.lines[2]:find("Thunderfury", 1, true), "item: " .. tostring(GameTooltip.lines[2]))

-- a link with no item id must not be looked up
reset(GameTooltip)
GameTooltip.itemLink = "|cffffffff|Hspell:133|h[Feuerball]|h|r"
GameTooltip:Fire("OnTooltipSetItem")
assert(#GameTooltip.lines == 0, "a link that is not an item must add nothing")

-- the trap: Show() re-firing the hook must not append a second time ------------
reset(GameTooltip)
GameTooltip.reentrant = "OnTooltipSetSpell"
GameTooltip.spellName, GameTooltip.spellId = "Feuerball", 133
GameTooltip:Fire("OnTooltipSetSpell")
assert(#GameTooltip.lines == 2,
  "the tooltip appended to itself: " .. #GameTooltip.lines .. " lines")

-- an English client needs none of this
locale = "enUS"
reset(GameTooltip)
GameTooltip.spellName, GameTooltip.spellId = "Fireball", 133
GameTooltip:Fire("OnTooltipSetSpell")
assert(#GameTooltip.lines == 0, "an English client should get nothing added")
locale = "deDE"

print("names-classic: ok")
