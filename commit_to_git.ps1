# commit_to_git.ps1
# Kjor fra rot-mappen i prosjektet: .\commit_to_git.ps1

Set-StrictMode -Off
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  XLENT Compliance - git commit og push" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

$statusLines = git status --short 2>&1
if (-not $statusLines) {
    Write-Host ""
    Write-Host "Ingenting a committe - alt er allerede lagret pa GitHub." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "Endringer siden siste commit:" -ForegroundColor White
$statusLines | ForEach-Object { Write-Host "  $_" }

git add -A

$staged = git diff --cached --name-only 2>&1
if (-not $staged) {
    Write-Host ""
    Write-Host "Ingen endringer a committe etter staging." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "Filer som committes:" -ForegroundColor Green
$staged | ForEach-Object { Write-Host "  + $_" -ForegroundColor Green }

Write-Host ""
$msg = Read-Host "Beskriv endringene"

if ([string]::IsNullOrWhiteSpace($msg)) {
    Write-Host "Tom melding - avbryter." -ForegroundColor Red
    git restore --staged . 2>&1 | Out-Null
    exit 1
}

git commit -m $msg
if ($LASTEXITCODE -ne 0) {
    Write-Host "Commit feilet." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Laster opp til GitHub..." -ForegroundColor Cyan

$upstream = git rev-parse --abbrev-ref --symbolic-full-name "@{upstream}" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Setter opp tracking mot origin/main..." -ForegroundColor Yellow
    git push --set-upstream origin main
} else {
    git push
}

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Ferdig! Endringene er pa GitHub." -ForegroundColor Green
    Write-Host "https://github.com/telboth/compliance-system" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "Push feilet. Sjekk nettverkstilgang og at remote er satt opp." -ForegroundColor Red
    exit 1
}