<#
.SYNOPSIS
    Test script for power-outage-monitor package
.DESCRIPTION
    This script runs tests for the power-outage-monitor package with coverage reporting.
.EXAMPLE
    .\scripts\test.ps1
.EXAMPLE
    .\scripts\test.ps1 -Coverage -Verbose
.EXAMPLE
    .\scripts\test.ps1 -TestFile "tests/test_config.py"
#>

[CmdletBinding()]
param(
    [switch]$Coverage = $true,
    [switch]$Verbose = $false,
    [string]$TestFile = "",
    [string]$TestPattern = "test_*.py",
    [switch]$FailFast = $false,
    [int]$CoverageThreshold = 80
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Enable verbose output if requested
if ($Verbose) {
    $VerbosePreference = "Continue"
}

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Running tests for power-outage-monitor..." -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan

try {
    # Check if we're
 in the right directory
    if (-not (Test-Path "pyproject.toml")) {
        throw "pyproject.toml not found. Please run this script from the project root directory."
    }

    # Install test dependencies
    Write-Host "Installing test dependencies..." -ForegroundColor Yellow
    python -m pip install -e ".[test]"

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install test dependencies"
    }

    # Prepare pytest arguments
    $pytestArgs = @()

    # Add test file or default test directory
    if ($TestFile) {
        if (-not (Test-Path $TestFile)) {
            throw "Test file not found: $TestFile"
        }
        $pytestArgs += $TestFile
    } else {
        $pytestArgs += "tests/"
    }

    # Add coverage options
    if ($Coverage) {
        $pytestArgs += "--cov=power_outage_monitor"
        $pytestArgs += "--cov-report=html"
        $pytestArgs += "--cov-report=term-missing"
        $pytestArgs += "--cov-fail-under=$CoverageThreshold"
    }

    # Add verbose option
    if ($Verbose) {
        $pytestArgs += "-v"
    }

    # Add fail fast option
    if ($FailFast) {
        $pytestArgs += "-x"
    }

    # Run tests
    Write-Host "Running tests with arguments: $($pytestArgs -join ' ')" -ForegroundColor Yellow
    python -m pytest @pytestArgs

    if ($LASTEXITCODE -ne 0) {
        throw "Tests failed"
    }

    # Display results
    Write-Host "=" * 60 -ForegroundColor Green
    Write-Host "Tests completed successfully!" -ForegroundColor Green
    Write-Host "=" * 60 -ForegroundColor Green

    if ($Coverage -and (Test-Path "htmlcov")) {
        Write-Host "Coverage report generated in htmlcov/" -ForegroundColor Cyan
        Write-Host "Open htmlcov/index.html in your browser to view detailed coverage" -ForegroundColor Cyan
    }

} catch {
    Write-Host "=" * 60 -ForegroundColor Red
    Write-Host "Tests failed!" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "=" * 60 -ForegroundColor Red
    exit 1
}