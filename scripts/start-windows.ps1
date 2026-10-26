param([switch]$AI)
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Write-Host "Traffic Enhancer - Windows quick start" -ForegroundColor Cyan

# Only fast-forward clean Git checkouts. Do not overwrite developer edits.
if ((Test-Path ".git") -and (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Checking the latest GitHub main branch..."
    & git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Could not fast-forward automatically; keeping current local version."
    }
}
if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
    throw "Port 8000 is already in use. Stop your old Traffic Enhancer console with Ctrl+C, then double-click again."
}
$python = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw "Install Python 3.12 from python.org, then run this launcher again."
    }
    Write-Host "Creating local Python environment..."
    & py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Python 3.12 environment creation failed." }
}
Write-Host "Installing essential project dependencies..."
& $python -m pip install --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed." }
if ($AI) {
    Write-Host "Checking the real YOLO and Whisper AI packages..." -ForegroundColor Cyan
    & $python -c "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('ultralytics') and importlib.util.find_spec('faster_whisper') else 1)"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing Ultralytics, PyTorch dependencies and faster-whisper. First setup downloads may be large..." -ForegroundColor Yellow
        & $python -m pip install --disable-pip-version-check --prefer-binary -r requirements-ai.txt
        if ($LASTEXITCODE -ne 0) { throw "AI install failed. Re-run this launcher after checking your internet connection and disk space." }
    }
    & $python -c "from ultralytics import YOLO;from faster_whisper import WhisperModel;print('YOLO and Whisper modules ready')"
    if ($LASTEXITCODE -ne 0) { throw "AI imports failed in the project's Python environment." }

    # Configure real local models only if the operator did not choose others.
    # 'base' is lighter for CPU-only Windows than the prior 'small' default.
    if (-not $env:TE_YOLO_MODEL) { $env:TE_YOLO_MODEL = "yolo11n.pt" }
    if (-not $env:TE_GROQ_ASR_MODEL -and -not $env:TE_ASR_MODEL) { $env:TE_ASR_MODEL = "base" }
    $env:TE_ASR_DEVICE = "cpu"
    if (-not $env:TE_ASR_COMPUTE_TYPE) { $env:TE_ASR_COMPUTE_TYPE = "int8" }
    $env:TE_ASR_ALLOW_DOWNLOAD = "1"

    # Model downloads occur on first inference, never report success before that.
    if ($env:TE_QWEN_API_KEY) {
        if (-not $env:TE_QWEN_API_BASE) { $env:TE_QWEN_API_BASE = "https://openrouter.ai/api/v1" }
        if (-not $env:TE_QWEN_MODEL) { $env:TE_QWEN_MODEL = "qwen/qwen-2.5-vl-7b-instruct:free" }
        $env:TE_ENABLE_QWEN = "1"
        Write-Host "Qwen remote analysis configured via your existing environment key." -ForegroundColor Green
    } else {
        Write-Host "Qwen is OFF locally: Codespaces secrets do not transfer to Windows." -ForegroundColor Yellow
        Write-Host "To enable Qwen, set TE_QWEN_API_KEY in your local Windows environment before launching."
    }
    Write-Host "YOLO weights: $env:TE_YOLO_MODEL. Speech: $(if ($env:TE_GROQ_ASR_MODEL) { $env:TE_GROQ_ASR_MODEL + ' (Groq)' } else { $env:TE_ASR_MODEL + ' (local Whisper)' })."
}
$secretPath = ".traffic-local-key"
if (-not (Test-Path $secretPath)) {
    $bytes = New-Object byte[] 24
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    [Convert]::ToBase64String($bytes) | Set-Content $secretPath -NoNewline
}
$env:TE_API_KEY = (Get-Content $secretPath -Raw).Trim()
$env:TE_ENV = "development"
Write-Host "Local login opens automatically without an operator-key prompt." -ForegroundColor Green
Write-Host "Your local URL: http://127.0.0.1:8000"

# Show actionable dependency errors instead of opening a broken page.
& $python -c "from services.api.main import app; print('Python imports OK')"
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Import failed (possibly damaged Pillow or Pydantic files). Automatically repairing core packages..."
    & $python -m pip install --disable-pip-version-check --no-cache-dir --force-reinstall -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Automatic dependency repair failed." }
    & $python -c "from services.api.main import app; print('Python imports OK after repair')"
    if ($LASTEXITCODE -ne 0) {
        throw "The Python environment is still broken. Inspect the error above or recreate only .venv."
    }
}
Write-Host "Launching backend and checking readiness..."
$proc = Start-Process -FilePath $python -ArgumentList @("-m","uvicorn","services.api.main:app","--host","127.0.0.1","--port","8000") -NoNewWindow -PassThru
$ready = $false
for($i=0;$i -lt 40;$i++) {
    if ($proc.HasExited) { throw "Backend exited unexpectedly. Inspect traceback in this window." }
    try {
        $res = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/health" -UseBasicParsing -TimeoutSec 2
        if ($res.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
    Start-Sleep -Milliseconds 500
}
if (-not $ready) { throw "Backend was not ready. Check the server output above." }
Start-Process "http://127.0.0.1:8000"
Write-Host "Running! Keep this window open. Press Ctrl+C to stop." -ForegroundColor Green
$proc.WaitForExit()
