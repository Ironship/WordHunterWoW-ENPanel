-- Run from the addon root:  lua tests/dialogueui.test.lua
--
-- DialogueUI replaces the quest window and offers a translator hook. What it
-- asks for and what the records hold are nearly the same shape, and the one
-- place they differ is the trap: it wants `objective`, the records spell it
-- `objectives`. Getting that wrong loses the objectives silently -- every
-- other field would still show, so it would look like it worked.
--
-- It also decides whether its button appears by asking for a title and
-- checking it is a non-empty string, so a record without one must come back
-- in a way that leaves the button hidden rather than showing an empty pane.

local captured
DialogueUIAPI = {
  SetTranslator = function(t) captured = t end,
}

local frames = {}
function CreateFrame()
  local f = {events = {}}
  function f:RegisterEvent(e) self.events[e] = true end
  function f:UnregisterAllEvents() self.events = {} end
  function f:SetScript(_, fn) self.handler = fn end
  frames[#frames + 1] = f
  return f
end
function GetQuestID() return 0 end
SLASH_WORDHUNTERENPANELDUI1 = nil
SlashCmdList = {}

WordHunterWoW_QuestEN = {
  [1234] = {
    title = "The Missing Scholar",
    description = "The pursuit of knowledge...",
    objectives = "Find Fillion Flamebreeze.",
    progress = "Have you found him?",
    completion = "Thank the Light.",
  },
  [5678] = { title = "Bare Title Only" },
}

loadedAddOns = {DialogueUI = true}
C_AddOns = {IsAddOnLoaded = function(name) return loadedAddOns[name] and true or false end}

-- Loaded the way the client loads it: every file of an addon is called with
-- its name and the addon's own shared table, and the panel reads the flag off
-- that table. dofile passes neither, so the flag would be invisible.
local ns = {}
assert(loadfile("DialogueUI.lua"))("WordHunterWoW-ENPanel", ns)

local frame = frames[1]
assert(frame, "no event frame was created")
assert(frame.events.ADDON_LOADED, "ADDON_LOADED was not registered")
assert(frame.events.PLAYER_LOGIN, "PLAYER_LOGIN was not registered")
assert(captured == nil, "it registered before DialogueUI said it had loaded")

-- Somebody else's addon loading must not trigger it.
frame.handler(frame, "ADDON_LOADED", "Baganator")
assert(captured == nil, "an unrelated addon triggered the handshake")

frame.handler(frame, "ADDON_LOADED", "DialogueUI")
assert(captured, "DialogueUI loading did not register a translator")
assert(captured.name and captured.name ~= "", "the translator has no name")
assert(type(captured.questDataGetter) == "function", "no questDataGetter was handed over")
assert(next(frame.events) == nil, "it kept listening after registering")
print("dialogueui: registers once, and only once DialogueUI is there")

local get = captured.questDataGetter

-- The field that does not line up.
local full = get(1234)
assert(full, "a quest with a record came back empty")
assert(full.title == "The Missing Scholar", "wrong title")
assert(full.description == "The pursuit of knowledge...", "wrong description")
assert(full.objective == "Find Fillion Flamebreeze.",
  "objectives must arrive as `objective` -- DialogueUI does not read `objectives`")
assert(full.objectives == nil, "the record's own spelling leaked through")
assert(full.progress == "Have you found him?", "wrong progress")
assert(full.completion == "Thank the Light.", "wrong completion")
print("dialogueui: objectives arrives as objective, and the rest are carried over")

-- A questID it has never heard of, and the states that happen at load.
assert(get(999999) == nil, "an unknown quest returned something")
assert(get(nil) == nil, "a nil questID returned something")
assert(get("1234") ~= nil, "a questID given as a string was not looked up")
local records = WordHunterWoW_QuestEN
WordHunterWoW_QuestEN = nil
assert(get(1234) == nil, "it read the records before they had loaded")
WordHunterWoW_QuestEN = records

-- A bare title still counts: DialogueUI shows its button on a non-empty title,
-- and a title alone is worth reading.
local bare = get(5678)
assert(bare and bare.title == "Bare Title Only", "a title-only record was dropped")
assert(bare.description == nil and bare.objective == nil, "a title-only record invented text")
print("dialogueui: unknown, nil and title-only quests all behave")

-- Registering twice would have DialogueUI turn the second one away in chat.
captured = nil
frame.handler(frame, "PLAYER_LOGIN")
assert(captured == nil, "it registered a second translator")
print("dialogueui: ok")


-- The panel stands down once DialogueUI is drawing the English. The base
-- addon's own column already had this rule; this is the same rule for a second
-- window showing the same paragraph. It must be false when DialogueUI is not
-- there, or a player without it would lose the panel altogether.
assert(type(ns.EnglishShownInDialogue) == "function",
  "the adapter did not publish the flag the panel reads")
loadedAddOns.DialogueUI = true
assert(ns.EnglishShownInDialogue() == true,
  "with DialogueUI loaded and the translator taken, the English is shown there")
loadedAddOns.DialogueUI = false
assert(ns.EnglishShownInDialogue() == false,
  "with DialogueUI gone the panel must come back")
loadedAddOns.DialogueUI = true
print("dialogueui: the panel stands down only while DialogueUI shows the English")
