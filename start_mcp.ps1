$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $root ".venv-mcp\Scripts\python.exe"
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }

$env:PYTHONPATH = $root
if (!$env:MCP_HOST) { $env:MCP_HOST = "127.0.0.1" }
if (!$env:MCP_PORT) { $env:MCP_PORT = "8010" }

& $python -m mcp_server.server
exit $LASTEXITCODE

