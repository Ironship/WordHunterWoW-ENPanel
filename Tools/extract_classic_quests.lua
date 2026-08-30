-- Read a local Classic quest database and write it out as JSONL.
--
--   lua Tools/extract_classic_quests.lua <english-db.lua> <out.jsonl> [locale-lookup.lua] [locale]
--
-- The database is Lua source, so it is loaded rather than parsed: the tables it
-- builds are the answer. Nothing about the file's origin is assumed beyond the
-- two shapes below, and the path is an argument so no location is baked in.
--
-- Records carry the quest title and its objective line. The offer text -- the
-- paragraph an NPC speaks when handing the quest over -- is not in this source
-- and cannot be invented, so it is simply absent.

local englishPath, outPath, localePath, localeName = ...
if not englishPath or not outPath then
  io.stderr:write("usage: extract_classic_quests.lua <english-db.lua> <out.jsonl> [locale-lookup.lua] [locale]\n")
  os.exit(2)
end

-- Enough of the host addon's shape for the data files to load.
local modules = {}
QuestieLoader = {
  ImportModule = function(_, name)
    -- The locale files assign into a sub-table they expect the host addon to
    -- have made already, so it has to exist before they run.
    modules[name] = modules[name] or { questLookup = {}, itemLookup = {},
                                       npcLookup = {}, objectLookup = {} }
    return modules[name]
  end,
}
QuestieDB = modules.QuestieDB or {}
modules.QuestieDB = QuestieDB
GetLocale = function() return localeName or "enUS" end
if not loadstring then loadstring = load end

local function collectTables(root, depth)
  -- The data lands somewhere under the module table, sometimes behind a
  -- loadstring thunk. Walk what was produced and take the biggest integer-keyed
  -- table, which is the quest set.
  local best, bestCount = nil, 0
  local seen = {}
  local function walk(value, level)
    if level > (depth or 4) or type(value) ~= "table" or seen[value] then return end
    seen[value] = true
    local count = 0
    for k in pairs(value) do
      if type(k) == "number" then count = count + 1 end
    end
    if count > bestCount then best, bestCount = value, count end
    for _, v in pairs(value) do
      if type(v) == "function" then
        -- Some of it is handed over behind a thunk.
        local ok, produced = pcall(v)
        if ok then walk(produced, level + 1) end
      elseif type(v) == "string" and v:match("^%s*return%s*{") then
        -- and some of it is kept as Lua source in a string, to be compiled on
        -- demand. Compile it here rather than parsing the text by hand.
        local chunk = loadstring(v)
        if chunk then
          local ok, produced = pcall(chunk)
          if ok then walk(produced, level + 1) end
        end
      else
        walk(v, level + 1)
      end
    end
  end
  walk(root, 0)
  return best, bestCount
end

local function load_file(path)
  local chunk = assert(loadfile(path), "cannot load " .. path)
  chunk()
end

load_file(englishPath)
local english, englishCount = collectTables(modules, 5)
assert(english and englishCount > 0, "found no quest table in " .. englishPath)

local localized
if localePath then
  load_file(localePath)
  local candidate, count = collectTables(modules, 6)
  -- The localised table is a different, usually smaller one; take it only if it
  -- is not the English table we already have.
  if candidate ~= english and count > 0 then localized = candidate end
  if not localized then
    for _, mod in pairs(modules) do
      if type(mod.questLookup) == "table" and type(mod.questLookup[localeName]) ~= nil then
        local t = mod.questLookup[localeName]
        if type(t) == "function" then t = t() end
        if type(t) == "table" then localized = t end
      end
    end
  end
end

local function jsonEscape(s)
  s = tostring(s or "")
  s = s:gsub("\\", "\\\\"):gsub('"', '\\"')
  s = s:gsub("\n", "\\n"):gsub("\r", "\\r"):gsub("\t", "\\t")
  s = s:gsub("%c", function(c) return string.format("\\u%04x", c:byte()) end)
  return s
end

-- The objective is a list of lines in both shapes; join them the way the game
-- shows them, one per line.
local function objectiveText(entry, index)
  local value = entry and entry[index]
  if type(value) == "string" then return value end
  if type(value) ~= "table" then return "" end
  local parts = {}
  for _, line in ipairs(value) do
    if type(line) == "string" and line ~= "" then parts[#parts + 1] = line end
  end
  return table.concat(parts, "\n")
end

local ids = {}
for id in pairs(english) do
  if type(id) == "number" then ids[#ids + 1] = id end
end
table.sort(ids)

local out = assert(io.open(outPath, "wb"))
local written, withLocale = 0, 0
for _, id in ipairs(ids) do
  local entry = english[id]
  if type(entry) == "table" then
    local title = type(entry[1]) == "string" and entry[1] or ""
    local objectives = objectiveText(entry, 8)
    local localTitle, localObjectives = nil, nil
    if localized and type(localized[id]) == "table" then
      local le = localized[id]
      localTitle = type(le[1]) == "string" and le[1] or nil
      localObjectives = objectiveText(le, 2)
      if localTitle then withLocale = withLocale + 1 end
    end
    if title ~= "" then
      local row = string.format('{"id":%d,"title":"%s","objectives":"%s"', id,
        jsonEscape(title), jsonEscape(objectives))
      if localTitle then
        row = row .. string.format(',"localeTitle":"%s","localeObjectives":"%s"',
          jsonEscape(localTitle), jsonEscape(localObjectives))
      end
      out:write(row, "}\n")
      written = written + 1
    end
  end
end
out:close()

print(string.format("quests=%d localized=%d -> %s", written, withLocale, outPath))
