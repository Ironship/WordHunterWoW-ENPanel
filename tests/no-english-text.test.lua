-- Run from the addon root:  lua tests/no-english-text.test.lua
--
-- Blizzard's own data has quests that are a title and nothing else: no opening
-- text, no objective, no progress or hand-in line. The panel showed those the
-- notice meant for a Classic record -- "showing its objective" -- and then an
-- empty window under it, so it named a line the record does not carry and left
-- the reader looking for it. The shipped Retail data is loaded here rather than
-- imagined, because how many records are like that, and whether they read as
-- real quests, is the whole reason this needs its own wording.

local texts = {}
local function node()
  local t = {}
  return setmetatable(t, {
    __index = function(_, key)
      if key == "SetText" then
        return function(_, value) texts[#texts + 1] = tostring(value or "") end
      end
      if key == "IsShown" then return function() return true end end
      if key == "GetWidth" then return function() return 400 end end
      if key == "GetStringHeight" then return function() return 10 end end
      return node()
    end,
    __call = function(self) return self end,
  })
end

-- The addon's own event frame is the first one it makes; everything after it is
-- the window and its children.
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
hooksecurefunc = function() end
QuestFrame, WorldMapFrame, QuestMapFrame = node(), node(), node()
QuestInfo_ShowDescriptionText = function() end
QuestMapFrame_ShowQuestDetails = function() end
QuestMapFrame_GetDetailQuestID = function() return 0 end
strtrim = function(s) return (tostring(s or ""):gsub("^%s+", ""):gsub("%s+$", "")) end

for i = 0, 49 do dofile(string.format("Data/QuestEN_%03d.lua", i)) end

local function filled(value) return type(value) == "string" and value ~= "" end
local records, titleOnly, objectiveOnly, bare = 0, 0, nil, nil
for id, entry in pairs(WordHunterWoW_QuestEN) do
  records = records + 1
  if not filled(entry.description) then
    -- The lowest id of each shape, so the records this runs against are the
    -- same ones every time rather than whichever the hash order offered first.
    if filled(entry.objectives) then
      if not objectiveOnly or id < objectiveOnly then objectiveOnly = id end
    elseif not filled(entry.progress) and not filled(entry.completion) then
      titleOnly = titleOnly + 1
      if not bare or id < bare then bare = id end
    end
  end
end
assert(records > 40000, 'the shipped Retail records did not load: ' .. records .. ' of them')
assert(titleOnly > 1000,
  'only ' .. titleOnly .. ' records carry a title and nothing else, so the wording this checks may no longer be needed')
assert(bare and objectiveOnly, 'the data no longer holds both shapes this test compares')

GetQuestID = function() return 0 end
assert(loadfile('ENPanel.lua'))('WordHunterWoW-ENPanel')
events.fn(nil, 'ADDON_LOADED', 'WordHunterWoW-ENPanel')

local function shownFor(questId, event)
  GetQuestID = function() return questId end
  texts = {}
  events.fn(nil, event or 'QUEST_DETAIL')
  assert(#texts > 0, 'the panel drew nothing at all for quest ' .. questId)
  return texts[#texts]
end

-- A real one out of the shipped data, not a record written to suit the test.
local bareBody = shownFor(bare)
assert(not bareBody:find('objective', 1, true),
  'a quest with no English text at all still promises an objective: ' .. bareBody)
assert(bareBody:find('no English text', 1, true) or bareBody:find('No English text', 1, true),
  'a quest with no English text at all does not say so: ' .. bareBody)

-- The hand-in and progress frames reach the same record by another route, and
-- the notice there used to name the opening text instead.
for _, event in ipairs({ 'QUEST_PROGRESS', 'QUEST_COMPLETE' }) do
  local body = shownFor(bare, event)
  assert(not body:find('objective', 1, true) and not body:find('opening text', 1, true),
    event .. ' on a record with no English text still names a passage it does not have: ' .. body)
end

-- And the case the notice was written for must keep it. A Classic record is a
-- title and an objective, and a lone objective under a paragraph of German
-- reads as a translation cut short unless it is explained.
local objectiveBody = shownFor(objectiveOnly)
assert(objectiveBody:find('Showing its objective', 1, true),
  'a record that really does have only an objective must still say so: ' .. objectiveBody)
assert(objectiveBody:find(WordHunterWoW_QuestEN[objectiveOnly].objectives, 1, true),
  'the objective itself went missing from the panel')

-- A full record says nothing at all, because there is nothing to explain.
local full
for id, entry in pairs(WordHunterWoW_QuestEN) do
  if filled(entry.description) and (not full or id < full) then full = id end
end
local fullBody = shownFor(full)
assert(not fullBody:find('No English', 1, true) and not fullBody:find('no English', 1, true),
  'a complete record was given a notice about missing text: ' .. fullBody)

-- A quest this addon has never heard of is a different thing from a quest whose
-- record is empty, and the two must not borrow each other's words.
local unknownBody = shownFor(9999999)
assert(unknownBody:find('not available', 1, true),
  'an unknown quest should say the panel has no record of it: ' .. unknownBody)
assert(unknownBody ~= bareBody, 'an unknown quest and an empty record are being described the same way')

-- With the base addon installed the wording comes from its one table of
-- strings, so a player running both reads one set of words rather than two.
WordHunterWoW_Addon = { LABELS = { enNoText = '[nothing here but the name]' } }
local sharedBody = shownFor(bare)
WordHunterWoW_Addon = nil
assert(sharedBody:find('[nothing here but the name]', 1, true),
  'the base addon supplied the wording and the panel used its own instead: ' .. sharedBody)

print('no-english-text: ok  (' .. titleOnly .. ' of ' .. records .. ' records are a title and nothing else)')
