<#
.SYNOPSIS
    Deployment script for power-outage-monitor package
.DESCRIPTION
    This script deploys the power-outage-monitor package to PyPI after running tests and building.
.EXAMPLE
    .\scripts\deploy.ps1
.EXAMPLE
    .\scripts\deploy.ps1 -TestPyPI
.EXAMPLE
    .\scripts\deploy.ps1 -SkipTests -Force
#>

[CmdletBinding()]
param(
    [switch]$TestPyPI = $false,
    [switch]$SkipTests = $false,
    [switch]$SkipBuild = $false,
    [switch]$Force = $false,
    [switch]$DryRun = $false,
    [string]$Repository = ""
)

# Set error action preference
$ErrorActionPreference = "Stop"

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Deploying power-outage-monitor package..." -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan

try {
    # Check if we're in the right directory
    if (-not (Test-Path "pyproject.toml")) {
        throw "pyproject.toml not found. Please run this script from the project root directory."
    }

    # Check git status unless forced
    if (-not $Force) {
        Write-Host "Checking git status..." -ForegroundColor Yellow

        $gitStatus = git status --porcelain 2>$null
        if ($LASTEXITCODE -eq 0 -and $gitStatus) {
            Write-Host "Git status output:" -ForegroundColor Yellow
            $gitStatus | ForEach-Object { Write-Host "  $_" -ForegroundColor White }

            if (-not $Force) {
                throw "Working directory is not clean. Please commit your changes first or use -Force to override."
            }
        }
    }

    # Run tests unless skipped
    if (-not $SkipTests) {
        Write-Host "Running tests..." -ForegroundColor Yellow
        & ".\scripts\test.ps1"

        if ($LASTEXITCODE -ne 0) {
            throw "Tests failed. Deployment aborted."
        }
    } else {
        Write-Host "Skipping tests as requested..." -ForegroundColor Yellow
    }

    # Build the package unless skipped
    if (-not $SkipBuild) {
        Write-Host "Building package..." -ForegroundColor Yellow
        & ".\scripts\build.ps1" -Clean

        if ($LASTEXITCODE -ne 0) {
            throw "Build failed. Deployment aborted."
        }
    } else {
        Write-Host "Skipping build as requested..." -ForegroundColor Yellow
    }

    # Check if dist directory exists and has files
    if (-not (Test-Path "dist") -or -not (Get-ChildItem "dist" -Filter "*.whl")) {
        throw "No distribution files found in dist/. Please run build first."
    }

    # Install/upgrade tw
ine
    Write-Host "Installing/upgrading twine..." -ForegroundColor Yellow
    python -m pip install --upgrade twine

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install twine"
    }

    # Check distribution files
    Write-Host "Checking distribution files..." -ForegroundColor Yellow
    python -m twine check dist/*

    if ($LASTEXITCODE -ne 0) {
        throw "Distribution files check failed"
    }

    # Determine repository
    $repoArgs = @()
    if ($TestPyPI) {
        $repoArgs += "--repository", "testpypi"
        Write-Host "Uploading to Test PyPI..." -ForegroundColor Yellow
    } elseif ($Repository) {
        $repoArgs += "--repository", $Repository
        Write-Host "Uploading to repository: $Repository..." -ForegroundColor Yellow
    } else {
        Write-Host "Uploading to PyPI..." -ForegroundColor Yellow
    }

    # Show what will be uploaded
    Write-Host "Files to be uploaded:" -ForegroundColor Cyan
    Get-ChildItem -Path "dist" | ForEach-Object {
        $size = [math]::Round($_.Length / 1KB, 2)
        Write-Host "  $($_.Name) ($size KB)" -ForegroundColor White
    }

    # Dry run check
    if ($DryRun) {
        Write-Host "DRY RUN: Would upload the above files" -ForegroundColor Yellow
        Write-Host "Use without -DryRun to actually upload" -ForegroundColor Yellow
        return
    }

    # Confirm upload unless forced
    if (-not $Force) {
        $confirmation = Read-Host "Do you want to proceed with upload? (y/N)"
        if ($confirmation -notmatch "^[Yy]") {
            Write-Host "Upload cancelled by user." -ForegroundColor Yellow
            return
        }
    }

    # Upload to PyPI
    python -m twine upload @repoArgs dist/*

    if ($LASTEXITCODE -ne 0) {
        throw "Upload failed"
    }

    # Success message
    Write-Host "=" * 60 -ForegroundColor Green
    Write-Host "Deployment completed successfully!" -ForegroundColor Green
    Write-Host "=" * 60 -ForegroundColor Green

    if ($TestPyPI) {
        Write-Host "Package uploaded to Test PyPI: https://test.pypi.org/project/power-outage-monitor/" -ForegroundColor Cyan
        Write-Host "Install with: pip install -i https://test.pypi.org/simple/ power-outage-monitor" -ForegroundColor Cyan
    } else {
        Write-Host "Package uploaded to PyPI: https://pypi.org/project/power-outage-monitor/" -ForegroundColor Cyan
        Write-Host "Install with: pip install power-outage-monitor" -ForegroundColor Cyan
    }

} catch {
    Write-Host "=" * 60 -ForegroundColor Red
    Write-Host "Deployment failed!" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "=" * 60 -ForegroundColor Red
    exit 1
}