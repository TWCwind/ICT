$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $root ".venv-mcp\Scripts\python.exe"
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }

$env:PYTHONPATH = $root
if (!$env:MCP_HOST) { $env:MCP_HOST = "127.0.0.1" }
if (!$env:MCP_PORT) { $env:MCP_PORT = "8010" }
if (!$env:MCP_RATE_LIMIT_PER_MIN) { $env:MCP_RATE_LIMIT_PER_MIN = "240" }

# 允许显式指定解释器（CI、共享 venv 或临时排障时用）
if ($env:MCP_PYTHON) { $python = $env:MCP_PYTHON }

# 依赖预检：缺 mcp / uvicorn 时给出可执行的提示，而不是抛 ModuleNotFoundError。
# 用 find_spec 只查不导入，避免在预检阶段抛出堆栈。
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $python -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('mcp') and importlib.util.find_spec('uvicorn') else 1)" *> $null
$probeCode = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($probeCode -ne 0) {
    Write-Host "当前解释器缺少依赖：$python" -ForegroundColor Red
    Write-Host "请先运行 .\install_mcp.ps1 创建 .venv-mcp，或用 MCP_PYTHON 指定已装好依赖的解释器。" -ForegroundColor Yellow
    exit 1
}

# 对外暴露（0.0.0.0 或公网隧道）必须带 API Key。这里没传就从本地文件读，
# 文件不存在就现生成一个；key 只留在本机 .mcp_api_key（已 gitignore）。
$keyFile = Join-Path $root ".mcp_api_key"
if (!$env:MCP_API_KEY) {
    if (Test-Path -LiteralPath $keyFile) {
        $env:MCP_API_KEY = (Get-Content -LiteralPath $keyFile -Raw).Trim()
    } else {
        $bytes = New-Object "byte[]" 32
        [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        $env:MCP_API_KEY = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
        Set-Content -LiteralPath $keyFile -Value $env:MCP_API_KEY -NoNewline -Encoding ascii
        Write-Host "已生成新的 MCP_API_KEY 并保存到 $keyFile（不要提交该文件）"
    }
}

Write-Host "MCP 服务: http://$($env:MCP_HOST):$($env:MCP_PORT)/mcp"
Write-Host "健康检查: http://$($env:MCP_HOST):$($env:MCP_PORT)/healthz"
Write-Host "限流: $($env:MCP_RATE_LIMIT_PER_MIN) 次/分钟（0 表示关闭）"
Write-Host "鉴权: 请求头 X-API-Key 或 Authorization: Bearer <key>"
if ($env:MCP_HOST -eq "0.0.0.0") {
    Write-Host "注意：正在监听所有网卡，公网可达前请确认已完成网关注册与 TLS 终结。" -ForegroundColor Yellow
}

& $python -m mcp_server.server
exit $LASTEXITCODE
