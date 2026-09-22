-- The English quest text, inside DialogueUI's own window.
--
-- DialogueUI (Peterodox) replaces the quest and gossip dialogue with a window
-- of its own, which leaves a panel anchored beside Blizzard's quest frame
-- pointing at something the player never sees. It documents a way in --
-- Code\SupportedAddOns\TranslatorPublic.lua -- so rather than fight it for
-- screen space, hand it the English and let it draw it: a button appears in
-- its window, and the quest reads in English with one click.
--
-- This addon registers rather than the base one for two reasons. It owns the
-- data: Data\<flavour>\QuestEN_*.lua are what fill WordHunterWoW_QuestEN, and
-- the base addon only reads that table. And DialogueUI keeps exactly one
-- translator -- a second one is turned away with a message in chat -- so only
-- one of the two may ever register, and it should be the one that still works
-- when the other is not installed.
--
-- Nothing here runs when DialogueUI is absent.

local ADDON_NAME, ns = ...
ns = ns or {}

-- DialogueUI asks for `objective`; the records spell it `objectives`. The rest
-- line up, and there is no greeting in the records, so none is offered -- the
-- contract treats every field as optional.
local function questDataGetter(questID)
  local records = WordHunterWoW_QuestEN
  local entry = records and questID and records[tonumber(questID)]
  if not entry then return nil end
  return {
    title = entry.title,
    description = entry.description,
    objective = entry.objectives,
    progress = entry.progress,
    completion = entry.completion,
  }
end

local registered = false

local function installed()
  if type(C_AddOns) == "table" and C_AddOns.IsAddOnLoaded then
    return C_AddOns.IsAddOnLoaded("DialogueUI") and true or false
  end
  if type(IsAddOnLoaded) == "function" then
    return IsAddOnLoaded("DialogueUI") and true or false
  end
  return false
end

local function register()
  if registered then return true end
  if type(DialogueUIAPI) ~= "table" or type(DialogueUIAPI.SetTranslator) ~= "function" then
    return false
  end
  registered = true
  -- No font. The records are English, the Latin glyphs DialogueUI already uses
  -- cover them, and its FontUtil takes nil as "leave the font alone".
  DialogueUIAPI.SetTranslator({
    name = "QuestWordHunter",
    questDataGetter = questDataGetter,
  })
  return true
end

-- DialogueUIAPI.SetTranslator exists only once DialogueUI's own files have run,
-- and the order two addons load in is not ours to decide. So: try when its
-- manifest reports it loaded, and try again at login for the case where it was
-- already loaded before this file ran. OptionalDeps in the manifest asks the
-- client to load it first, which usually settles it at ADDON_LOADED.
local events = CreateFrame("Frame")
events:RegisterEvent("ADDON_LOADED")
events:RegisterEvent("PLAYER_LOGIN")
events:SetScript("OnEvent", function(self, event, which)
  if event == "ADDON_LOADED" and which ~= "DialogueUI" and which ~= ADDON_NAME then
    return
  end
  if register() then
    self:UnregisterAllEvents()
  end
end)

-- The panel asks this before it opens. Once DialogueUI is drawing the English
-- inside its own window, a second window with the same text beside it is the
-- same text twice -- which is exactly what the panel already avoids when the
-- base addon shows the English in its own column.
function ns.EnglishShownInDialogue()
  return registered and installed()
end

-- For the test build: /enpanel dui says whether the handshake happened and what
-- the records hold for the quest in front of you.
SLASH_WORDHUNTERENPANELDUI1 = "/enpaneldui"
SlashCmdList.WORDHUNTERENPANELDUI = function()
  local api = type(DialogueUIAPI) == "table" and type(DialogueUIAPI.SetTranslator) == "function"
  local records = WordHunterWoW_QuestEN
  local count = 0
  if type(records) == "table" then for _ in pairs(records) do count = count + 1 end end
  print("|cff59aefaQuestWordHunter x DialogueUI:|r")
  print(string.format("  DialogueUIAPI=%s  registered=%s  records=%d",
    tostring(api), tostring(registered), count))
  local questID = GetQuestID and GetQuestID()
  if questID and questID ~= 0 then
    local data = questDataGetter(questID)
    print(string.format("  quest %s -> %s", tostring(questID),
      data and ("|cff80ff80" .. tostring(data.title) .. "|r") or "|cffff8080no English record|r"))
  else
    print("  no quest on screen; run this with a quest window open")
  end
end
