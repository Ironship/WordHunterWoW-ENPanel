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
local points, handlers = {}, {}
local panel
local questShown, mapShown = true, false

local function node(record)
  local t = {}
  return setmetatable(t, {
    __index = function(_, key)
      if record and key == "SetPoint" then
        return function(_, point, relativeTo)
          local host = "screen"
          if relativeTo == QuestFrame then host = "QuestFrame"
          elseif relativeTo == WorldMapFrame then host = "WorldMapFrame" end
          points[#points + 1] = tostring(point) .. " of " .. host
        end
      end
      if record and key == "ClearAllPoints" then return function() end end
      if record and key == "SetScript" then
        return function(_, script, fn) handlers[script] = fn end
      end
      if record and key == "GetLeft" then return function() return 700 end end
      if record and key == "GetTop" then return function() return 600 end end
      if record and key == "GetPoint" then
        return function() return "CENTER", nil, "CENTER", 0, 0 end
      end
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
CreateFrame = function(_, name)
  -- Only the panel window itself records its anchoring; its children all
  -- anchored correctly even when the window did not.
  local f = node(name == "WordHunterWoWENPanelFrame")
  if name == "WordHunterWoWENPanelFrame" then panel = f end
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
rawset(QuestFrame, "IsShown", function() return questShown end)
rawset(WorldMapFrame, "IsShown", function() return mapShown end)
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

-- Without OptionalDeps the base addon can load after this one. The integration
-- must attach when that happens, not only when this addon loads first.
WordHunterWoW_Addon = { applied = 0 }
WordHunterWoW_Addon.ApplyIntegratedLayout = function() WordHunterWoW_Addon.applied = 1 end
events.fn(nil, "ADDON_LOADED", "WordHunterWoW")
assert(WordHunterWoW_Addon.OnIntegratedLayoutChanged,
       "integration was not attached when the base addon loaded afterwards")
assert(WordHunterWoW_Addon.applied == 1, "the base layout was never applied")
print("  base addon loading later still attaches the integration")

-- A frame with no anchor point has no position and the game draws nothing, so
-- Show() succeeds and the panel is nowhere on screen. Every child was anchored,
-- which is why this went unnoticed: the code looks full of SetPoint calls.
assert(#points > 0, "the panel window was never anchored, so it cannot be visible")
-- and it belongs beside the quest window it is translating, not adrift in the
-- middle of the screen
assert(points[#points] == "TOPLEFT of QuestFrame",
       "with an NPC quest open the panel should sit beside it, got: " .. points[#points])
print("  anchored beside the NPC quest window")

-- The map is nowhere near the dialogue window, so it gets its own position.
-- Dragging the panel while talking to an NPC must not move it on the map.
assert(handlers.OnDragStop, "the panel never registered a drag handler")
handlers.OnDragStop(panel)
questShown, mapShown = false, true
events.fn(nil, "QUEST_DETAIL")
assert(points[#points] == "TOPLEFT of WorldMapFrame",
       "on the map the panel should sit beside the map, not where it was dragged "
       .. "beside the dialogue, got: " .. points[#points])
print("  the map keeps its own position, not the dialogue's")

-- and each remembered position is used again for its own window
handlers.OnDragStop(panel)
questShown, mapShown = true, false
events.fn(nil, "QUEST_DETAIL")
assert(points[#points] == "TOPLEFT of screen",
       "the dialogue should reuse its own remembered position, got: " .. points[#points])
print("  both windows remember where the player put the panel")

print("standalone: all assertions passed")
