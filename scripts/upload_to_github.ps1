#requires -Version 5.1
<#
.SYNOPSIS
    Upload the MOCHI repository to GitHub in one step.

.DESCRIPTION
    Checks that git is available, initialises the repository on branch main if needed, commits
    everything, points origin at your GitHub URL and pushes. Authentication is handled by git
    (Git Credential Manager, a personal access token, or GitHub CLI).

.PARAMETER RepoUrl
    HTTPS or SSH URL of the (already created, empty) GitHub repository.

.PARAMETER Message
    Commit message. Defaults to a project description.

.EXAMPLE
    pwsh ./scripts/upload_to_github.ps1 -RepoUrl https://github.com/simmzx/mochi.git

.EXAMPLE
    pwsh ./scripts/upload_to_github.ps1 -RepoUrl git@github.com:simmzx/mochi.git -Message "MOCHI v1.0"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepoUrl,
    [string]$Message = "MOCHI: self-evolving multi-agent system for end-to-end AI drug discovery"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

# ---------------------------------------------------------------- git available?
$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) {
    Write-Host "git was not found on PATH." -ForegroundColor Red
    Write-Host "Install it with:  winget install --id Git.Git -e --source winget" -ForegroundColor Yellow
    Write-Host "then reopen the terminal and run this script again." -ForegroundColor Yellow
    exit 1
}
Write-Host "git: $((& git --version))" -ForegroundColor Cyan

# ---------------------------------------------------------------- identity
$name = (& git config --global user.name) 2>$null
if (-not $name) {
    $name = Read-Host "Your name for git commits (e.g. Zhang Xiang)"
    & git config --global user.name "$name"
}
$email = (& git config --global user.email) 2>$null
if (-not $email) {
    $email = Read-Host "Your e-mail for git commits"
    & git config --global user.email "$email"
}

# ---------------------------------------------------------------- init / commit
if (-not (Test-Path ".git")) {
    Write-Host "`ninitialising repository on branch main" -ForegroundColor Yellow
    & git init -b main | Out-Null
}

Write-Host "`nstaging all files" -ForegroundColor Yellow
& git add -A
$staged = (& git diff --cached --name-only) | Measure-Object | Select-Object -ExpandProperty Count
if ($staged -eq 0) {
    Write-Host "nothing new to commit" -ForegroundColor DarkGray
} else {
    Write-Host "committing $staged file(s)" -ForegroundColor Yellow
    & git commit -m "$Message" | Out-Null
}

# ---------------------------------------------------------------- remote
$existing = (& git remote) 2>$null
if ($existing -contains "origin") {
    & git remote set-url origin "$RepoUrl"
} else {
    & git remote add origin "$RepoUrl"
}
Write-Host "origin -> $RepoUrl" -ForegroundColor Cyan

# ---------------------------------------------------------------- push
Write-Host "`npushing to GitHub (a browser window may ask you to sign in)" -ForegroundColor Yellow
& git push -u origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "`npush failed. Common causes:" -ForegroundColor Red
    Write-Host "  - the GitHub repository does not exist yet: create it empty at https://github.com/new"
    Write-Host "  - the remote has files (e.g. a README created by GitHub): run"
    Write-Host "      git pull --rebase origin main --allow-unrelated-histories"
    Write-Host "      git push -u origin main"
    Write-Host "  - authentication: use a personal access token as the password, or sign in via GitHub Desktop"
    exit 1
}

Write-Host "`nuploaded. Open: $($RepoUrl -replace '\.git$','')" -ForegroundColor Green
