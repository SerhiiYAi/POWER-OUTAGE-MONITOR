<#
.SYNOPSIS
    Build script for power-outage-monitor package
.DESCRIPTION
    This script builds the power-outage-monitor Python package, creating wheel and source distributions.
.EXAMPLE
    .\scripts\build.ps1
.EXAMPLE
    .\scripts\build.ps1 -Clean
#>

[CmdletBinding()]
param(
    [switch]$Clean = $false,
    [switch]$Verbose = $false
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Enable verbose output if requested
if ($Verbose) {
    $VerbosePreference = "Continue"
}

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Building power-outage-monitor package..." -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan

try {
    # Clean previous builds if requested
    if ($Clean) {
        Write-Host "Cleaning previous builds..." -ForegroundColor Yellow

        $dirsToRemove = @("build", "dist", "*.egg-info")
        foreach ($dir in $dirsToRemove) {
            if (Test-Path $dir) {
                Remove-Item $dir -Recurse -Force
                Write-Verbose "Removed: $dir"
            }
        }

        # Also clean __pycache__ directories
        Get-ChildItem -Path . -Name "__pycache__" -Recurse -Directory | Remove-Item -Recurse -Force
        Write-Verbose "Cleaned __pycache__ directories"
    }

    # Check if we're in the right directory
    if (-not (Test-Path "pyproject.toml")) {
        throw "pyproject.toml not found. Please run this script from the project root directory."
    }

    # Install/upgrade build dependencies
    Write-Host "Installing build dependencies..." -ForegroundColor Yellow
    python -m pip install --upgrade pip setuptools wheel build

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install build dependencies"
    }

    # Build the package
    Write-Host "Building the package..." -ForegroundColor Yellow
    python -m build

    if ($LASTEXITCODE -ne 0) {
        throw "Package build failed"
    }

    # Display results
    Write-Host "=" * 60 -ForegroundColor Green
    Write-Host "Build completed successfully!" -ForegroundColor Green
    Write-Host "=" * 60 -ForegroundColor Green

    if (Test-Path "dist") {
        Write-Host "Distribution files created in dist/:" -ForegroundColor Cyan
        Get-ChildItem -Path "dist" | ForEach-Object {
            $size = [math]::Round($_.Length / 1KB, 2)
            Write-Host "  $($_.Name) ($size KB)" -ForegroundColor White
        }
    }

} catch {
    Write-Host "=" * 60 -ForegroundColor Red
    Write-Host "Build failed!" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "=" * 60 -ForegroundColor Red
    exit 1
}