# Run frontend and backend together for local testing (Windows).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python is required. Install Python 3.12+ and ensure it is on PATH."
}

$backendDeps = python -c "import fastapi" 2>$null
if (-not $backendDeps) {
    Write-Host "Installing backend dependencies..."
    python -m pip install -r backend/requirements.txt
}

if (-not (Test-Path "frontend/node_modules")) {
    Write-Host "Installing frontend dependencies..."
    Set-Location frontend
    npm install
    Set-Location $Root
}

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing root dev dependencies..."
    npm install
}

Write-Host "Starting backend (http://127.0.0.1:8000) and frontend (http://localhost:5173)..."
npm run dev
