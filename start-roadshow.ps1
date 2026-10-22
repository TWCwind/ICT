param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$project = Get-ChildItem -LiteralPath $PSScriptRoot -Directory |
  Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'start-roadshow.ps1') } |
  Select-Object -First 1
if (!$project) { throw '主工程目录中未找到 start-roadshow.ps1' }
$script = Join-Path $project.FullName 'start-roadshow.ps1'
& $script @args
