<#
.SYNOPSIS
    Development environment setup script
.DESCRIPTION
    Sets up the development environment for power-outage-monitor package.
.EXAMPLE
    .\scripts\dev-setup.ps1
.EXAMPLE
    .\scripts\dev-setup.ps1 -CreateVenv -VenvName "power-monitor-dev"
#>

[CmdletBinding()]
param(
    [switch]$CreateVenv = $false,
    [string]$VenvName = "venv",
    [switch]$InstallPreCommit = $true,
    [switch]$Force = $false
)

$ErrorActionPreference = "Stop"

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Setting up development environment..." -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan

try {
    # Create virtual environment if requested
    if ($CreateVenv) {
        if (Test-Path $VenvName) {
            if ($Force) {
                Write-Host "Removing existing virtual environment..." -ForegroundColor Yellow
                Remove-Item $VenvName -Recurse -Force
            } else {
                throw "Virtual environment '$VenvName' already exists. Use -Force to recreate."
            }
        }
        
        Write-Host "Creating virtual environment: $VenvName" -ForegroundColor Yellow
        python -m venv $VenvName
        
        Write-Host "Activating virtual environment..." -ForegroundColor Yellow
        & ".\$VenvName\Scripts\Activate.ps1"
    }

    # Upgrade pip
    Write-Host "Upgrading pip..." -ForegroundColor Yellow
    python -m pip install --upgrade pip

    # Install package in development mode
    Write-Host "Installing package in development mode..." -ForegroundColor Yellow
    python -m pip install -e ".[dev]"

    # Install pre-commit hooks if requested
    if ($InstallPreCommit) {
        Write-Host "Installing pre-commit hooks..." -ForegroundColor Yellow
        pre-commit install
    }

    Write-Host "=" * 60 -ForegroundColor Green
    Write-Host "Development environment setup completed!" -ForegroundColor Green
    Write-Host "=" * 60 -ForegroundColor Green
    
    if ($CreateVenv) {
        Write-Host "To activate the virtual environment,
 run:" -ForegroundColor Cyan
        Write-Host "  .\$VenvName\Scripts\Activate.ps1" -ForegroundColor White
    }

} catch {
    Write-Host "=" * 60 -ForegroundColor Red
    Write-Host "Setup failed!" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "=" * 60 -ForegroundColor Red
    exit 1
}