$ErrorActionPreference = "Stop"

$env:OLLAMA_MODELS = Join-Path $PSScriptRoot "ollama_models"
New-Item -ItemType Directory -Force -Path $env:OLLAMA_MODELS | Out-Null

$ollama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
if (-not (Test-Path $ollama)) {
    Write-Host "未找到 Ollama 程序：$ollama" -ForegroundColor Yellow
    Write-Host "请先安装 Windows 版 Ollama：https://ollama.com/download/windows"
    exit 1
}

try {
    Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | Out-Null
    Write-Host "Ollama 服务已在 http://127.0.0.1:11434 运行。"
    exit 0
} catch {
    Write-Host "启动 Ollama 服务，模型目录：$env:OLLAMA_MODELS"
}

& $ollama serve
