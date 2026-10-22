param([string]$Url = "http://127.0.0.1:8010/mcp")

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $root ".venv-mcp\Scripts\python.exe"
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }
$env:PYTHONPATH = $root

& $python -m unittest discover -s (Join-Path $root "mcp_server\tests") -p "test*.py" -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python (Join-Path $root "mcp_server\smoke_client.py") --url $Url
exit $LASTEXITCODE

