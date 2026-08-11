param(
    [string]$InstallRoot = "$env:LOCALAPPDATA\ai-presence-monitor"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvRoot = Join-Path $InstallRoot "venv"
$Python = Join-Path $VenvRoot "Scripts\python.exe"
$Command = Join-Path $VenvRoot "Scripts\ai-presence.exe"

if (-not (Test-Path $Python)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3 -m venv $VenvRoot
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        python -m venv $VenvRoot
    }
    else {
        throw "Python 3 was not found in PATH."
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Virtual environment creation failed with exit code $LASTEXITCODE."
    }
}

& $Python -m pip install --upgrade $ProjectRoot
if ($LASTEXITCODE -ne 0) {
    throw "Package installation failed with exit code $LASTEXITCODE."
}

Write-Host "Installed command: $Command"
Write-Host "Test with: & `"$Command`" --help"
Write-Host "Rollback: remove only $VenvRoot after uninstalling scheduled tasks."
