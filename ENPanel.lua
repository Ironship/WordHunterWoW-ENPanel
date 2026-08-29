local addonName = ...

local frame
local questInfoHooked
local questMapHooked
local hideWatched = {}
local db
-- Which passage the NPC is showing. The base addon works this out too, and its
-- answer is preferred when it is installed, but this addon has to stand on its
-- own: without it there is nothing to ask.
local lastPassage = "offer"

local function layoutContent()
  if not frame then return end
  local w = frame:GetWidth()
  frame.content:SetWidth(math.max(200, w - 52))
  if frame:IsShown() then
    frame.content:SetHeight(math.max(1, frame.text:GetStringHeight() + 12))
    frame.scroll:UpdateScrollChildRect()
  end
end

local function applyTheme(target)
  local Addon = WordHunterWoW_Addon
  if Addon and Addon.ApplyBackground then
    Addon.ApplyBackground(target)
  else
    target:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8", edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 1, insets = { left = 1, right = 1, top = 1, bottom = 1 } })
    target:SetBackdropColor(0.08, 0.09, 0.13, 0.97)
    target:SetBackdropBorderColor(0.22, 0.24, 0.34, 0.95)
  end
end

local function questText(questId)
  local entry = WordHunterWoW_QuestEN and WordHunterWoW_QuestEN[tonumber(questId)]
  if not entry then return nil end
  local title = entry.title or ""
  local description = entry.description or ""
  local objectives = entry.objectives or ""
  local body = description
  if objectives ~= "" then body = body .. (body ~= "" and "\n\n" or "") .. objectives end
  return title, body
end

local function questFrameOpen()
  return QuestFrame and QuestFrame:IsShown()
end

local function questLogOpen()
  local details = QuestMapFrame and QuestMapFrame.DetailsFrame
  if details and details:IsShown() then return true end
  return WorldMapFrame and WorldMapFrame:IsShown() and QuestMapFrame and QuestMapFrame:IsShown()
end

local function currentQuestId()
  if questFrameOpen() then
    local id = GetQuestID and GetQuestID()
    if id and id > 0 then return id end
  end
  local id = QuestMapFrame_GetDetailQuestID and QuestMapFrame_GetDetailQuestID()
  if id and id > 0 then return id end
  id = C_QuestLog and C_QuestLog.GetSelectedQuest and C_QuestLog.GetSelectedQuest()
  if id and id > 0 then return id end
  id = GetQuestID and GetQuestID()
  if id and id > 0 then return id end
  return nil
end

local function hideIfOrphaned()
  if not frame or not frame:IsShown() then return end
  if not questFrameOpen() and not questLogOpen() then
    frame:Hide()
  end
end

local function watchHide(target)
  if not target or hideWatched[target] then return end
  hideWatched[target] = true
  target:HookScript("OnHide", function()
    C_Timer.After(0, hideIfOrphaned)
  end)
end

local function ensureFrame()
  if frame then return frame end
  frame = CreateFrame("Frame", "WordHunterWoWENPanelFrame", UIParent, "BackdropTemplate")
  frame:SetSize(420, 480)
  frame:SetFrameStrata("FULLSCREEN_DIALOG")
  frame:SetClampedToScreen(true)
  frame:SetMovable(true)
  frame:EnableMouse(true)
  frame:RegisterForDrag("LeftButton")
  frame:SetScript("OnDragStart", frame.StartMoving)
  frame:SetScript("OnDragStop", frame.StopMovingOrSizing)
  applyTheme(frame)
  if WordHunterWoW_Addon then WordHunterWoW_Addon.enPanel = frame end
  if WordHunterWoW_Addon and WordHunterWoW_Addon.MakeResizable then
    WordHunterWoW_Addon.MakeResizable(frame, "enPanel", 280, 220, 700, 800)
  else
    frame:SetResizable(true)
    if frame.SetResizeBounds then frame:SetResizeBounds(280, 220, 700, 800) end
    local handle = CreateFrame("Button", nil, frame)
    handle:SetSize(16, 16)
    handle:SetPoint("BOTTOMRIGHT", -4, 4)
    handle:SetNormalTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Up")
    handle:SetHighlightTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Highlight")
    handle:SetPushedTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Down")
    handle:SetScript("OnMouseDown", function() frame:StartSizing("BOTTOMRIGHT") end)
    handle:SetScript("OnMouseUp", function() frame:StopMovingOrSizing() end)
    frame.resizeHandle = handle
  end
  if db and db.w and db.h then frame:SetSize(db.w, db.h) end
  frame:HookScript("OnSizeChanged", function(self)
    if db then
      db.w, db.h = self:GetWidth(), self:GetHeight()
    end
    layoutContent()
  end)
  frame.title = frame:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
  frame.title:SetPoint("TOPLEFT", 16, -14)
  frame.title:SetPoint("TOPRIGHT", -40, -14)
  frame.title:SetJustifyH("LEFT")
  frame.title:SetMaxLines(1)
  local close = CreateFrame("Button", nil, frame, "UIPanelCloseButton")
  close:SetPoint("TOPRIGHT", -2, -2)
  frame.scroll = CreateFrame("ScrollFrame", nil, frame, "UIPanelScrollFrameTemplate")
  frame.scroll:SetPoint("TOPLEFT", 16, -44)
  frame.scroll:SetPoint("BOTTOMRIGHT", -34, 16)
  frame.content = CreateFrame("Frame", nil, frame.scroll)
  frame.content:SetSize(368, 1)
  frame.scroll:SetScrollChild(frame.content)
  frame.text = frame.content:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
  frame.text:SetPoint("TOPLEFT", 0, 0)
  frame.text:SetPoint("TOPRIGHT", 0, 0)
  frame.text:SetJustifyH("LEFT")
  frame.text:SetJustifyV("TOP")
  frame.text:SetWordWrap(true)
  frame:Hide()
  return frame
end

local function showQuest(questId)
  local Addon = WordHunterWoW_Addon
  if Addon and Addon.GetIntegratedLayout and Addon.GetIntegratedLayout() then
    if frame then frame:Hide() end
    return
  end
  questId = questId or currentQuestId()
  if not questId or questId == 0 then return end
  local title, body = questText(questId)
  -- The shipped data holds only the quest's opening text and objectives, because
  -- that is all Blizzard's quest API publishes. When the NPC is showing the
  -- progress or hand-in lines instead, say so rather than passing off the opening
  -- text as a translation of what the player is reading.
  local lastQuest = Addon and Addon.lastQuest
  local passage = (lastQuest and lastQuest.passage) or lastPassage
  if body and passage and passage ~= "offer" then
    -- Addon is nil whenever the base addon is absent or switched off, which is
    -- the normal case now that this works on its own. Until lastPassage existed
    -- this branch could only be reached when the base had supplied the passage,
    -- so it was safe by accident; it is not any more.
    local caveat = (Addon and Addon.LABELS and Addon.LABELS.enOfferOnly)
      or "[Blizzard publishes no English text for this part of a quest. Showing the quest's opening text instead.]"
    -- Red, and on its own line: it is a warning about the text underneath, not a
    -- part of it. Fall back to a fixed red if the base addon is absent or is an
    -- older version that has no caveat colour.
    local color = Addon and Addon.COLORS and Addon.COLORS.caveat
    local hex = color
      and string.format("%02x%02x%02x", color[1] * 255, color[2] * 255, color[3] * 255)
      or "ff6b6b"
    body = "|cff" .. hex .. caveat .. "|r" .. (body ~= "" and "\n\n" or "") .. body
  end
  local f = ensureFrame()
  applyTheme(f)
  f.title:SetText(title or ("English quest #" .. questId))
  f.text:SetText(body or "English text is not available for this quest.")
  layoutContent()
  f:Show()
  f:Raise()
end

local function hookQuestUi()
  if not questInfoHooked and type(QuestInfo_ShowDescriptionText) == "function" then
    questInfoHooked = true
    hooksecurefunc("QuestInfo_ShowDescriptionText", function()
      C_Timer.After(0, function() showQuest() end)
    end)
  end
  if not questMapHooked and type(QuestMapFrame_ShowQuestDetails) == "function" then
    questMapHooked = true
    hooksecurefunc("QuestMapFrame_ShowQuestDetails", function()
      C_Timer.After(0, function()
        local questId = QuestMapFrame_GetDetailQuestID and QuestMapFrame_GetDetailQuestID()
        if not questId or questId == 0 then questId = C_QuestLog.GetSelectedQuest() end
        -- Reading a quest in the log always shows its offer text, whatever the
        -- last NPC conversation happened to be.
        lastPassage = "offer"
        showQuest(questId)
      end)
    end)
  end
  watchHide(QuestFrame)
  watchHide(WorldMapFrame)
  watchHide(QuestMapFrame)
  if QuestMapFrame and QuestMapFrame.DetailsFrame then watchHide(QuestMapFrame.DetailsFrame) end
end

local events = CreateFrame("Frame")
events:RegisterEvent("ADDON_LOADED")
events:RegisterEvent("QUEST_DETAIL")
events:RegisterEvent("QUEST_PROGRESS")
events:RegisterEvent("QUEST_COMPLETE")
events:RegisterEvent("QUEST_FINISHED")
events:SetScript("OnEvent", function(_, event, loaded)
  if event == "ADDON_LOADED" then
    if loaded == addonName then
      WordHunterWoWENPanelDB = WordHunterWoWENPanelDB or {}
      db = WordHunterWoWENPanelDB
      hookQuestUi()
      local Addon = WordHunterWoW_Addon
      if Addon then
        Addon.OnIntegratedLayoutChanged = function(integrated)
          if integrated then
            if frame then frame:Hide() end
          else
            showQuest()
          end
        end
        if Addon.ApplyIntegratedLayout then Addon.ApplyIntegratedLayout() end
      end
    elseif loaded == "Blizzard_WorldMap" or loaded == "Blizzard_UIPanels_Game" then
      hookQuestUi()
    end
  elseif event == "QUEST_FINISHED" then
    lastPassage = "offer"
    if frame then frame:Hide() end
  else
    -- QUEST_DETAIL is the offer, QUEST_PROGRESS the "are you done yet" line,
    -- QUEST_COMPLETE the hand-in. Only the first has English text behind it.
    if event == "QUEST_PROGRESS" then
      lastPassage = "progress"
    elseif event == "QUEST_COMPLETE" then
      lastPassage = "reward"
    else
      lastPassage = "offer"
    end
    hookQuestUi()
    C_Timer.After(0, function() showQuest() end)
  end
end)
