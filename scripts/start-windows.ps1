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
    Write-Host "Installing optional YOLO / Whisper dependencies..."
    & $python -m pip install --disable-pip-version-check -r requirements-ai.txt
    if ($LASTEXITCODE -ne 0) { throw "AI dependency installation failed." }
    $env:TE_YOLO_MODEL = "yolo11n.pt"
    $env:TE_ASR_MODEL = "small"
    $env:TE_ASR_ALLOW_DOWNLOAD = "1"
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
Write-Host "API operator key (private; stored locally):" -ForegroundColor Yellow
Write-Host $env:TE_API_KEY
Write-Host "Your local URL: http://127.0.0.1:8000"

# Show actionable dependency errors instead of opening a broken page.
& $python -c "from services.api.main import app; print('Python imports OK')"
if ($LASTEXITCODE -ne 0) {
    throw "Import check failed. Run: .\.venv\Scripts\python.exe -m pip install --no-cache-dir --force-reinstall -r requirements.txt"
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
