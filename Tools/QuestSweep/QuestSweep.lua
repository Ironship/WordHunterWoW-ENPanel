-- QuestSweep: a maintainer's tool. It is not part of the English Quest Panel
-- and is not packaged with it.
--
-- The client keeps every quest the server has told it about in
-- Cache/WDB/<locale>/questcache.wdb, complete with its text, and that holds for
-- quests the player never took. This asks the server about one quest id after
-- another, slowly, so that the cache fills with the whole game instead of only
-- the quests this character happened to meet. Tools/wdb_quests.py reads the
-- result.
--
--   /qsweep start        begin (or carry on from where the last run stopped)
--   /qsweep stop         pause
--   /qsweep status       how far it has got
--   /qsweep rate <n>     requests per second, 1 to 30 (default 10)
--   /qsweep add <a> <b>  also ask about ids a to b
--   /qsweep reset        forget the progress and start over
--
-- Run it in an English client (Battle.net: text language English) -- the cache
-- holds the text in the language the client runs in. It writes the cache when
-- the game closes, so log out to the character screen or quit when it says it
-- is done, and then run Tools/build_forever_quests.py.
--
-- What it keeps in QuestSweepDB: every id the server answered for, with its
-- title, so the list of quests that exist survives even if the cache does not.

local DEFAULT_RANGES = { { 1, 9999 }, { 65000, 100500 } }
local DEFAULT_RATE = 10
local MAX_RATE = 30
local MAX_IN_FLIGHT = 40   -- asked and not yet answered
local ANSWER_WITHIN = 20   -- seconds; a request unanswered for this long is written off
local REPORT_EVERY = 500   -- requests between progress lines

local db
local running = false
local paused = false       -- stopped by combat or a loading screen, not by the user
local pending, inFlight = {}, 0
local owed = 0             -- requests earned by elapsed time and not yet sent
local sinceReport = 0
local retried = false

local function say(text)
  local message = "|cff7fd0ffQuestSweep|r " .. text
  if DEFAULT_CHAT_FRAME and DEFAULT_CHAT_FRAME.AddMessage then
    DEFAULT_CHAT_FRAME:AddMessage(message)
  else
    print(message)
  end
end

local function freshDb()
  local ranges = {}
  for index, range in ipairs(DEFAULT_RANGES) do
    ranges[index] = { range[1], range[2], range[1] } -- from, to, next id to ask about
  end
  return { ranges = ranges, found = {}, unanswered = {}, asked = 0, answered = 0,
           rate = DEFAULT_RATE, locale = GetLocale and GetLocale() or "?" }
end

local function count(set)
  local n = 0
  for _ in pairs(set) do n = n + 1 end
  return n
end

local function remaining()
  local left = 0
  for _, range in ipairs(db.ranges) do
    if range[3] <= range[2] then left = left + (range[2] - range[3] + 1) end
  end
  return left
end

local function nextId()
  for _, range in ipairs(db.ranges) do
    if range[3] <= range[2] then
      local id = range[3]
      range[3] = id + 1
      return id
    end
  end
  return nil
end

local function status()
  local left = remaining()
  local rate = db.rate
  say(string.format("asked %d, answered %d, %d quests exist so far, %d unanswered; %d ids left (about %d min at %d/s)%s",
    db.asked, db.answered, count(db.found), count(db.unanswered), left,
    math.ceil(left / rate / 60), rate, running and "" or "  [stopped]"))
end

local function request(id)
  pending[id] = GetTime()
  inFlight = inFlight + 1
  db.asked = db.asked + 1
  sinceReport = sinceReport + 1
  local ok = pcall(C_QuestLog.RequestLoadQuestByID, id)
  if not ok then
    pending[id] = nil
    inFlight = inFlight - 1
    db.unanswered[id] = true
  end
end

local function finish()
  running = false
  say("done. " .. count(db.found) .. " quests exist; the server did not answer for " .. count(db.unanswered) .. " ids.")
  say("Now log out to the character screen (or quit) so the client writes Cache\\WDB\\" .. db.locale
    .. "\\questcache.wdb, then run Tools/build_forever_quests.py.")
end

local function expire(now)
  for id, since in pairs(pending) do
    if now - since > ANSWER_WITHIN then
      pending[id] = nil
      inFlight = inFlight - 1
      db.unanswered[id] = true
    end
  end
end

local function tick(elapsed)
  if not running or paused then return end
  local now = GetTime()
  expire(now)
  owed = owed + elapsed * db.rate
  if owed > db.rate then owed = db.rate end -- never a burst of more than a second's worth
  while owed >= 1 do
    if inFlight >= MAX_IN_FLIGHT then return end
    local id = nextId()
    if not id then
      -- Everything has been asked once. Ask the unanswered ids a second time,
      -- then stop when nothing is left outstanding.
      if inFlight > 0 then return end
      if not retried and next(db.unanswered) then
        retried = true
        local again = {}
        for unanswered in pairs(db.unanswered) do again[#again + 1] = unanswered end
        table.sort(again)
        db.unanswered = {}
        db.ranges = {}
        for index, value in ipairs(again) do db.ranges[index] = { value, value, value } end
        return
      end
      finish()
      return
    end
    owed = owed - 1
    request(id)
  end
  if sinceReport >= REPORT_EVERY then
    sinceReport = 0
    status()
  end
end

local function start(force)
  if not (C_QuestLog and C_QuestLog.RequestLoadQuestByID) then
    say("this client has no C_QuestLog.RequestLoadQuestByID; nothing to do.")
    return
  end
  if db.locale ~= "enUS" and not force then
    say("this client runs in " .. db.locale .. ", so the cache would hold " .. db.locale
      .. " text. Switch the text language to English, or use /qsweep start force.")
    return
  end
  running, paused, retried = true, false, false
  say("started. Leave the game open; /qsweep stop to pause.")
  status()
end

local function stop()
  running = false
  say("stopped.")
  status()
end

local commands = {
  start = function(rest) start(rest == "force") end,
  stop = stop,
  status = status,
  rate = function(rest)
    local n = tonumber(rest)
    if not n or n < 1 or n > MAX_RATE then
      say("rate is a number from 1 to " .. MAX_RATE)
      return
    end
    db.rate = n
    status()
  end,
  add = function(rest)
    local from, to = rest:match("^(%d+)%s+(%d+)$")
    from, to = tonumber(from), tonumber(to)
    if not from or not to or from > to then
      say("usage: /qsweep add <first id> <last id>")
      return
    end
    db.ranges[#db.ranges + 1] = { from, to, from }
    status()
  end,
  reset = function()
    local rate, locale = db.rate, db.locale
    QuestSweepDB = freshDb()
    db = QuestSweepDB
    db.rate, db.locale = rate, locale
    pending, inFlight, owed, retried = {}, 0, 0, false
    running = false
    say("progress forgotten.")
    status()
  end,
}

SLASH_QUESTSWEEP1 = "/qsweep"
SlashCmdList["QUESTSWEEP"] = function(input)
  local word, rest = (input or ""):match("^%s*(%S*)%s*(.-)%s*$")
  local run = commands[word or ""]
  if run then
    run(rest or "")
  else
    say("/qsweep start | stop | status | rate <n> | add <a> <b> | reset")
  end
end

local frame = CreateFrame("Frame")
frame:RegisterEvent("PLAYER_LOGIN")
frame:RegisterEvent("QUEST_DATA_LOAD_RESULT")
frame:RegisterEvent("PLAYER_REGEN_DISABLED")
frame:RegisterEvent("PLAYER_REGEN_ENABLED")
frame:RegisterEvent("PLAYER_LEAVING_WORLD")
frame:RegisterEvent("PLAYER_ENTERING_WORLD")
frame:SetScript("OnEvent", function(_, event, questId, success)
  if event == "PLAYER_LOGIN" then
    QuestSweepDB = QuestSweepDB or freshDb()
    db = QuestSweepDB
    db.locale = GetLocale and GetLocale() or db.locale
    db.found, db.unanswered = db.found or {}, db.unanswered or {}
    say("loaded. /qsweep start to begin; " .. count(db.found) .. " quests recorded so far.")
  elseif not db then
    return
  elseif event == "QUEST_DATA_LOAD_RESULT" then
    if pending[questId] then
      pending[questId] = nil
      inFlight = inFlight - 1
      db.unanswered[questId] = nil
      db.answered = db.answered + 1
    end
    if success then
      local title = C_QuestLog.GetTitleForQuestID and C_QuestLog.GetTitleForQuestID(questId)
      db.found[questId] = title or ""
    end
  elseif event == "PLAYER_REGEN_DISABLED" or event == "PLAYER_LEAVING_WORLD" then
    paused = true
  elseif event == "PLAYER_REGEN_ENABLED" or event == "PLAYER_ENTERING_WORLD" then
    paused = false
  end
end)
frame:SetScript("OnUpdate", function(_, elapsed) tick(elapsed) end)
