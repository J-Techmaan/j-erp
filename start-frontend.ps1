$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$portableNode = Get-ChildItem -LiteralPath (Join-Path $projectRoot '.tools') -Directory -Filter 'node-*-win-x64' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($portableNode) { $env:PATH = $portableNode.FullName + ';' + $env:PATH }
Set-Location -LiteralPath (Join-Path $projectRoot 'frontend')
& npm.cmd run dev -- --host 0.0.0.0
