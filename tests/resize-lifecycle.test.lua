-- Lua 5.1: actual standalone grip callbacks, including Hide during sizing.
local made, events, panel = {}, nil, nil
local function frame(parent)
  local f = { scripts = {}, hooks = {}, shown = false, w = 420, h = 480 }
  function f:SetScript(event, fn) self.scripts[event] = fn end
  function f:GetScript(event) return self.scripts[event] end
  function f:HookScript(event, fn) self.hooks[event] = self.hooks[event] or {}; table.insert(self.hooks[event], fn) end
  local function emit(event, ...)
    local fn = f.scripts[event]; if fn then fn(f, ...) end
    for _, fn in ipairs(f.hooks[event] or {}) do fn(f, ...) end
  end
  function f:Show() local changed = not self.shown; self.shown = true; if changed then emit('OnShow') end end
  function f:Hide() local changed = self.shown; self.shown = false; if changed then emit('OnHide') end end
  function f:IsShown() return self.shown end
  function f:SetSize(w, h) self.w, self.h = w, h; emit('OnSizeChanged', w, h) end
  function f:GetWidth() return self.w end
  function f:GetHeight() return self.h end
  function f:GetLeft() return 700 end
  function f:GetTop() return 600 end
  function f:GetPoint() return 'TOPLEFT', UIParent, 'BOTTOMLEFT', 700, 600 end
  function f:StartSizing() self.sizing = true end
  function f:StopMovingOrSizing() self.sizing = false; self.stops = (self.stops or 0) + 1 end
  function f:RegisterForDrag(button) self.dragButton = button end
  function f:CreateFontString() return frame(self) end
  function f:SetText(value) self.textValue = value end
  function f:GetStringHeight() return 12 end
  function f:SetScale(value) self.scaleValue = value end
  -- Only methods are mocked; missing child/data fields remain absent.
  return setmetatable(f, { __index = function(_, key)
    if key:sub(1, 1):match('%u') then return function() end end
  end })
end
CreateFrame = function(kind, name, parent)
  local f = frame(parent)
  made[#made + 1] = f
  if not events then events = f end
  if name == 'WordHunterWoWENPanelFrame' then panel = f end
  return f
end
UIParent, QuestFrame = frame(), frame()
QuestFrame:Show()
GetQuestID = function() return 7 end
C_Timer = { After = function(_, fn) fn() end }
hooksecurefunc = function() end
WordHunterWoWENPanelDB = { w = 500, h = 350, scale = 1.4,
  pos = { quest = { point = 'TOPLEFT', relativePoint = 'BOTTOMLEFT', x = 700, y = 600 } } }
WordHunterWoW_QuestEN = { [7] = { title = 'A quest', description = 'The wolf waits.' } }
assert(WordHunterWoW_Addon == nil, 'this must exercise the standalone branch')
assert(loadfile(arg[1] or 'ENPanel.lua'))('WordHunterWoW-ENPanel')
events:GetScript('OnEvent')(nil, 'ADDON_LOADED', 'WordHunterWoW-ENPanel')
events:GetScript('OnEvent')(nil, 'QUEST_DETAIL')
assert(panel and panel:IsShown(), 'actual events must show the panel')
local grip = assert(panel.resizeHandle, 'actual standalone grip missing')
assert(grip.dragButton == 'LeftButton', 'standalone grip must register actual left-button dragging')
local start, stop = grip:GetScript('OnDragStart'), grip:GetScript('OnDragStop')
assert(type(start) == 'function' and type(stop) == 'function', 'standalone grip needs both native drag callbacks')
start(grip); assert(panel.sizing)
stop(grip); assert(not panel.sizing, 'real drag stop must end sizing')
start(grip); assert(panel.sizing)
panel:Hide(); assert(not panel.sizing, 'Hide must clean up active sizing independently of MouseUp dispatch')
panel:Show(); start(grip)
grip:GetScript('OnMouseUp')(grip); assert(not panel.sizing, 'plain mouse-up remains a cleanup backstop')
assert(panel:GetWidth() == 500 and panel:GetHeight() == 350)
assert(WordHunterWoWENPanelDB.w == 500 and WordHunterWoWENPanelDB.h == 350 and WordHunterWoWENPanelDB.scale == 1.4,
  'lifecycle cleanup must preserve the selected size and scale')
local saved = WordHunterWoWENPanelDB.pos.quest
assert(saved.x == 700 and saved.y == 600, 'lifecycle cleanup must preserve the saved position')
print('resize-lifecycle: real standalone drag start/stop, Hide and MouseUp cleanup; saved geometry preserved: ok')
