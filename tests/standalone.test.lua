-- Run from the addon root:  lua tests/standalone.test.lua
--
-- The panel has to work with no base addon present at all. Loading it that way
-- was already covered; showing a quest was not, and the hand-in path reached
-- straight into the base addon for its label and its colour. With the base
-- switched off that is a nil index, and the panel dies at the exact moment a
-- player turns a quest in.

local texts, shows = {}, 0

-- Every frame is the same thing: a table that is also callable, so both
-- f:Method(...) and f.child:Method(...) work without knowing the shape in
-- advance. SetText and Show are recorded; everything else is a no-op.
local function node()
  local t = {}
  return setmetatable(t, {
    __index = function(_, key)
      if key == "SetText" then
        return function(_, value) texts[#texts + 1] = tostring(value or "") end
      end
      if key == "Show" then return function() shows = shows + 1 end end
      if key == "IsShown" then return function() return true end end
      if key == "GetWidth" then return function() return 400 end end
      if key == "GetStringHeight" then return function() return 10 end end
      return node()
    end,
    __call = function(self) return self end,
  })
end

local events
CreateFrame = function()
  local f = node()
  if not events then
    events = { RegisterEvent = function() end }
    rawset(events, "SetScript", function(_, _, fn) rawset(events, "fn", fn) end)
    return setmetatable(events, getmetatable(f))
  end
  return f
end

C_Timer = { After = function(_, fn) if fn then fn() end end }
C_QuestLog = { GetSelectedQuest = function() return 0 end }
UIParent = node()
GetQuestID = function() return 184 end
hooksecurefunc = function() end
QuestFrame, WorldMapFrame, QuestMapFrame = node(), node(), node()
QuestInfo_ShowDescriptionText = function() end
QuestMapFrame_ShowQuestDetails = function() end
QuestMapFrame_GetDetailQuestID = function() return 0 end
strtrim = function(s) return (tostring(s or ""):gsub("^%s+", ""):gsub("%s+$", "")) end

dofile("Data/QuestEN_000.lua")
assert(WordHunterWoW_QuestEN[184], "expected quest 184 in the shipped data")
assert(WordHunterWoW_Addon == nil, "this test is only meaningful without the base addon")

assert(loadfile("ENPanel.lua"))("WordHunterWoW-ENPanel")
assert(events and events.fn, "the addon never registered an event handler")
events.fn(nil, "ADDON_LOADED", "WordHunterWoW-ENPanel")
print("loaded with no base addon")

local function lastText()
  return texts[#texts] or ""
end

-- offer: the ordinary path
events.fn(nil, "QUEST_DETAIL")
assert(shows > 0, "the panel never showed for a quest offer")
local offer = table.concat(texts, "\n")
assert(offer:find("deed", 1, true), "offer text missing: " .. offer:sub(1, 120))
print("  quest offer shown")

-- hand-in: this is the call that used to throw
local before = shows
events.fn(nil, "QUEST_COMPLETE")
assert(shows > before, "the panel never showed at hand-in")
local body = table.concat(texts, "\n")
assert(body:find("Blizzard publishes no English text", 1, true),
       "hand-in should carry the caveat")
assert(body:find("|cffff6b6b", 1, true),
       "with no base addon the caveat colour must fall back to a fixed red")
print("  hand-in shown, caveat present, colour fell back")

-- progress goes down the same branch
before = shows
events.fn(nil, "QUEST_PROGRESS")
assert(shows > before, "the panel never showed at progress")
print("  progress shown")

print("standalone: all assertions passed")
