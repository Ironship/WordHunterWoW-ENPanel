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
          elseif relativeTo == WorldMapFrame then host = "WorldMapFrame"
          elseif QuestLogFrame and relativeTo == QuestLogFrame then host = "QuestLogFrame" end
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

-- Hand-in. Blizzard's API publishes no English for this passage, so for a long
-- time the panel could only show the opening text and apologise for it. The
-- records now carry the hand-in line where it is known, and quest 184 is one
-- that does: the panel must show that line, and must not apologise.
local before = shows
texts = {}
events.fn(nil, "QUEST_COMPLETE")
assert(shows > before, "the panel never showed at hand-in")
local body = table.concat(texts, "\n")
assert(not body:find("Blizzard publishes no English text", 1, true),
       "a record that has the hand-in line must not carry the caveat")
assert(body:find(WordHunterWoW_QuestEN[184].completion:sub(1, 30), 1, true),
       "hand-in should show the hand-in line, got: " .. body:sub(1, 160))
print("  hand-in shown from its own text, no caveat")

-- Progress goes down the same path.
before = shows
texts = {}
events.fn(nil, "QUEST_PROGRESS")
assert(shows > before, "the panel never showed at progress")
body = table.concat(texts, "\n")
assert(not body:find("Blizzard publishes no English text", 1, true),
       "a record that has the progress line must not carry the caveat")
print("  progress shown from its own text")

-- A record without the hand-in line still has to say so, in red, and fall back
-- to the opening text rather than showing nothing.
GetQuestID = function() return 1 end
texts = {}
before = shows
events.fn(nil, "QUEST_COMPLETE")
assert(shows > before, "the panel never showed for the quest without a hand-in line")
body = table.concat(texts, "\n")
assert(body:find("Blizzard publishes no English text", 1, true),
       "a record with no hand-in line must still carry the caveat")
assert(body:find("|cffc2ccdb", 1, true),
       "standalone caveat must use the readable neutral palette")
print("  quest without a hand-in line still caveated, colour fell back")
GetQuestID = function() return 184 end

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

-- Classic has no world map quest log: the log is a window of its own, and the
-- panel has to sit beside that instead of falling back to the middle of the
-- screen. It shares the log's remembered position, so a player moving between
-- games does not have to place it twice.
local classicShown = false
QuestLogFrame = node()
rawset(QuestLogFrame, "IsShown", function() return classicShown end)
rawset(QuestLogFrame, "GetName", function() return "QuestLogFrame" end)
questShown, mapShown, classicShown = false, false, true
WordHunterWoWENPanelDB.pos = nil   -- a player who has not placed it yet
events.fn(nil, "QUEST_DETAIL")
assert(points[#points] == "TOPLEFT of QuestLogFrame",
       "on Classic the panel should open beside the quest log window, got: " .. points[#points])
print("  Classic's own quest log window is anchored to as well")

print("standalone: all assertions passed")

-- A Classic record carries a title and an objective and no opening text at all,
-- because the source has none. Left unexplained, a single objective line under a
-- paragraph of German reads as though the translation had been cut short.
WordHunterWoW_QuestEN[999001] = {
  title = "Wanted: Hogger",
  description = "",
  objectives = "Bring Hogger's Huge Fang to Marshal Dughan in Goldshire.",
}
GetQuestID = function() return 999001 end
questShown, mapShown, classicShown = true, false, false
texts = {}
events.fn(nil, "QUEST_DETAIL")
local classicBody = table.concat(texts, "\n")
assert(classicBody:find("Huge Fang", 1, true), "the objective should still be shown")
assert(classicBody:find("No English opening text", 1, true),
       "a record with no opening text must say so: " .. classicBody:sub(1, 160))
-- and a Retail record, which does have opening text, must not carry that notice
GetQuestID = function() return 184 end
texts = {}
events.fn(nil, "QUEST_DETAIL")
assert(not table.concat(texts, "\n"):find("No English opening text", 1, true),
       "a full record must not claim its opening text is missing")
print("  a quest with no opening text says so instead of looking truncated")

-- Progress on a Classic record used to claim it was showing the opening text
-- while actually showing the objective.
GetQuestID = function() return 999001 end
texts = {}
events.fn(nil, "QUEST_PROGRESS")
local classicProgress = table.concat(texts, "\n")
assert(classicProgress:find("Huge Fang", 1, true), "progress still shows the objective")
assert(classicProgress:find("Showing its objective", 1, true),
       "Classic progress must not claim it is showing the opening: " .. classicProgress:sub(1, 200))
assert(not classicProgress:find("opening text instead", 1, true),
       "must not use the Retail missing-passage wording on a Classic record")
