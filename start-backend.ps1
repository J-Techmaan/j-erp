$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
Set-Location -LiteralPath (Join-Path $projectRoot 'backend')
& (Join-Path $projectRoot '.venv\Scripts\python.exe') -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
