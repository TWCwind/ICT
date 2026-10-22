$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $root ".venv-mcp"
$python = Join-Path $venv "Scripts\python.exe"

if (!(Test-Path -LiteralPath $python)) {
    python -m venv $venv
}

& $python -m pip install -r (Join-Path $root "mcp_server\requirements.txt")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "MCP dependencies installed: $python"

