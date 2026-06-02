$ErrorActionPreference = "Stop"

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    $defaultOllama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (Test-Path $defaultOllama) {
        $ollama = $defaultOllama
    } else {
        Write-Host "Ollama was not found. Please install Ollama first:" -ForegroundColor Yellow
        Write-Host "https://ollama.com/download/windows"
        exit 1
    }
} else {
    $ollama = $ollama.Source
}

$modelRoot = Join-Path $PSScriptRoot "ollama_models"
New-Item -ItemType Directory -Force -Path $modelRoot | Out-Null
$env:OLLAMA_MODELS = $modelRoot

$model = "qwen2.5vl:3b"
Write-Host "Model directory: $env:OLLAMA_MODELS"
Write-Host "Ollama executable: $ollama"

try {
    $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3
    Write-Host "Ollama is already running at http://127.0.0.1:11434."
    if (-not ($tags.models | Where-Object { $_.name -eq $model })) {
        Write-Host "Model $model is not listed. Check whether OLLAMA_MODELS points to: $env:OLLAMA_MODELS" -ForegroundColor Yellow
    }
    exit 0
} catch {
    Write-Host "Ollama is not running. Starting service."
}

Write-Host "Starting Ollama service..."
Write-Host "If the model is missing, run these commands in another PowerShell:"
Write-Host "First:"
Write-Host "`$env:OLLAMA_MODELS = $env:OLLAMA_MODELS"
Write-Host "Then:"
Write-Host "$ollama pull $model"
& $ollama serve
