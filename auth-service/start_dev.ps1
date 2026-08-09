# PowerShell startup script for dev environment

$scriptPath = $PSScriptRoot
Set-Location $scriptPath

Write-Host "Starting WordPress Auth Service Dev Server..." -ForegroundColor Green

if (Test-Path ".\venv\Scripts\python.exe") {
    & ".\venv\Scripts\python.exe" -m wp_auth_service.main
} else {
    python -m wp_auth_service.main
}
