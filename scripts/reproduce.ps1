#requires -Version 5.1
<#
.SYNOPSIS
    Reproduce every artefact of the MOCHI project from a fresh checkout.

.DESCRIPTION
    Installs the three runtime dependencies, runs the offline self-checks, executes all four
    scenarios end-to-end with the deterministic engine, and rebuilds the report and slides.

.EXAMPLE
    pwsh ./scripts/reproduce.ps1
    pwsh ./scripts/reproduce.ps1 -SkipDocs
#>
[CmdletBinding()]
param(
    [switch]$SkipDocs,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
Write-Host "== repository: $root" -ForegroundColor Cyan

# ---------------------------------------------------------------- dependencies
Write-Host "`n[1/4] installing runtime dependencies" -ForegroundColor Yellow
& $Python -m pip install --quiet --upgrade pip
& $Python -m pip install --quiet -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "dependency installation failed" }

# ---------------------------------------------------------------- self-checks
Write-Host "`n[2/4] offline self-checks" -ForegroundColor Yellow
& $Python tests/run_checks.py
if ($LASTEXITCODE -ne 0) { throw "self-checks failed" }

# ---------------------------------------------------------------- scenarios
Write-Host "`n[3/4] four scenarios (offline engine)" -ForegroundColor Yellow
& $Python cases/run_all.py --engine offline
if ($LASTEXITCODE -ne 0) { throw "scenario run failed" }

# ---------------------------------------------------------------- documents
if (-not $SkipDocs) {
    Write-Host "`n[4/4] rebuilding report and slides" -ForegroundColor Yellow
    Push-Location paper
    & $Python make_report.py
    & $Python build_deck.py
    Pop-Location
    Write-Host "LaTeX report: cd paper/latex; tectonic -X compile main.tex  (or latexmk -xelatex)" -ForegroundColor DarkGray
} else {
    Write-Host "`n[4/4] skipped document build" -ForegroundColor DarkGray
}

Write-Host "`nDone. Run directories are under outputs/." -ForegroundColor Green
