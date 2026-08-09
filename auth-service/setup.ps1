# WordPress Auth Service Setup Script
# Run this script to install dependencies and start the service

Write-Host "WordPress Auth Service Setup" -ForegroundColor Cyan
Write-Host "=============================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
Write-Host "Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "Error: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.9 or higher from https://www.python.org/" -ForegroundColor Yellow
    exit 1
}

# Create and activate virtual environment
Write-Host ""
Write-Host "Setting up Python virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) {
    python -m venv venv
    Write-Host "Created virtual environment in .\venv" -ForegroundColor Green
} else {
    Write-Host "Virtual environment already exists." -ForegroundColor Green
}

# Activate virtual environment
$venvActivate = ".\venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    . $venvActivate
} else {
    Write-Host "Warning: Could not find $venvActivate. Proceeding with default Python." -ForegroundColor Yellow
}

# Install dependencies
Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to install dependencies" -ForegroundColor Red
    exit 1
}
Write-Host "Dependencies installed successfully" -ForegroundColor Green

# Create .env file if it doesn't exist
if (-not (Test-Path .env)) {
    Write-Host ""
    Write-Host "Creating .env file from template..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host ".env file created. Please edit it with your WordPress site details." -ForegroundColor Green
    Write-Host "You can configure it through the admin interface after starting the service." -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host ".env file already exists" -ForegroundColor Green
}

# Helper function to find next open port
function Get-NextOpenPort {
    param([int]$startPort = 8000)
    $p = $startPort
    while ($true) {
        $occupied = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' }
        if (-not $occupied) {
            return $p
        }
        $p++
    }
}

# Port check & conflict resolution
$targetPort = 8000
$tcpConn = Get-NetTCPConnection -LocalPort $targetPort -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' }

if ($tcpConn) {
    $owningPid = $tcpConn.OwningProcess | Select-Object -First 1
    $procName = "Unknown"
    if ($owningPid) {
        $proc = Get-Process -Id $owningPid -ErrorAction SilentlyContinue
        if ($proc) { $procName = $proc.ProcessName }
    }

    Write-Host ""
    Write-Host "==========================================================" -ForegroundColor Red
    Write-Host "WARNING: Port $targetPort is already in use by another process!" -ForegroundColor Red
    Write-Host "  Process Name : $procName" -ForegroundColor Yellow
    Write-Host "  Process PID  : $owningPid" -ForegroundColor Yellow
    Write-Host "==========================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Select an option:" -ForegroundColor Cyan
    Write-Host "  [T] Terminate process (PID $owningPid) and use port $targetPort" -ForegroundColor Yellow
    Write-Host "  [A] Try an alternative available port" -ForegroundColor Yellow
    Write-Host "  [Q] Quit setup" -ForegroundColor Yellow
    Write-Host ""

    $choice = Read-Host "Choice (T / A / Q)"
    $choice = $choice.Trim().ToUpper()

    if ($choice -eq 'T') {
        Write-Host "Terminating process (PID $owningPid)..." -ForegroundColor Yellow
        try {
            Stop-Process -Id $owningPid -Force -ErrorAction Stop
            Start-Sleep -Seconds 1
            Write-Host "Process terminated successfully." -ForegroundColor Green
        } catch {
            Write-Host "Failed to terminate process: $_" -ForegroundColor Red
            $alt = Get-NextOpenPort -startPort ($targetPort + 1)
            Write-Host "Switching to alternative available port: $alt" -ForegroundColor Yellow
            $targetPort = $alt
        }
    } elseif ($choice -eq 'A') {
        $alt = Get-NextOpenPort -startPort ($targetPort + 1)
        $userPort = Read-Host "Enter alternative port (Press Enter for auto-detected $alt)"
        if ([string]::IsNullOrWhiteSpace($userPort) -or -not ($userPort -match '^\d+$')) {
            $targetPort = $alt
        } else {
            $targetPort = [int]$userPort
        }
        Write-Host "Using port: $targetPort" -ForegroundColor Green
    } else {
        Write-Host "Setup aborted by user." -ForegroundColor Red
        exit 0
    }
}

# Start the service
Write-Host ""
Write-Host "Starting WordPress Auth Service..." -ForegroundColor Yellow
Write-Host "The service will be available at http://localhost:$targetPort" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the service" -ForegroundColor Yellow
Write-Host ""

python -m wp_auth_service.main $targetPort
