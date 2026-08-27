$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
python Tools/fetch_quests.py --locale en_US --workers 6 --interval 0.25
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python Tools/build_quest_lua.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "ENPanel data complete"
