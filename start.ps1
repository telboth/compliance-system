<#
.SYNOPSIS
    Starter XLENT Compliance-systemet.

.DESCRIPTION
    Bygger (om nodvendig) og starter alle Docker-tjenester, kjorer database-
    migrasjoner og apner frontend i nettleseren.

.PARAMETER Build
    Tving re-bygging av Docker-images selv om ingenting har endret seg.

.PARAMETER NoBrowser
    Ikke apne nettleseren automatisk.

.EXAMPLE
    .\start.ps1
    .\start.ps1 -Build
    .\start.ps1 -NoBrowser
#>
param(
    [switch]$Build,
    [switch]$NoBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"   # Stop kaster unntak pa native-kommando-stderr

$Root = $PSScriptRoot

function Write-Header([string]$Text) {
    $line = "-" * ($Text.Length + 4)
    Write-Host ""
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host "  $line" -ForegroundColor DarkGray
}

function Write-OK([string]$Text)   { Write-Host "  [OK]  $Text" -ForegroundColor Green }
function Write-Info([string]$Text) { Write-Host "  -->   $Text" -ForegroundColor Gray }
function Write-Warn([string]$Text) { Write-Host "  [!]   $Text" -ForegroundColor Yellow }
function Write-Fail([string]$Text) { Write-Host "  [X]   $Text" -ForegroundColor Red }

# -- Forutsetninger ------------------------------------------------------------

Write-Header "XLENT Compliance - oppstart"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Fail "Docker er ikke installert eller ikke i PATH."
    exit 1
}

$null = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Docker Desktop kjorer ikke."
    Write-Host ""
    Write-Host "  Start Docker Desktop fra Start-menyen og vent til ikonet" -ForegroundColor Yellow
    Write-Host "  i systemstatusfeltet er grott (ikke animert)." -ForegroundColor Yellow
    Write-Host "  Kjor deretter start.ps1 pa nytt." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-OK "Docker er oppe"

# -- .secrets-sjekk -----------------------------------------------------------

$secretsFile = Join-Path $Root ".secrets"
if (-not (Test-Path $secretsFile)) {
    Write-Warn ".secrets mangler - kopierer fra .secrets.example"
    Copy-Item (Join-Path $Root ".secrets.example") $secretsFile
    Write-Warn "Fyll inn API-nokler i .secrets og kjor start.ps1 pa nytt."
}

# Les .secrets og eksporter som miljovariabler slik at docker compose plukker dem opp
Get-Content $secretsFile | Where-Object { $_ -match "^\s*[^#].*=.*" } | ForEach-Object {
    $parts = $_ -split "=", 2
    $key   = $parts[0].Trim()
    $value = $parts[1].Trim()
    [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
}

# -- Docker Compose -----------------------------------------------------------

Set-Location $Root

Write-Header "Starter tjenester"

$composeArgs = @("compose", "up", "--detach", "--wait")
if ($Build) { $composeArgs += "--build" }

Write-Info "docker $($composeArgs -join ' ')"
Write-Info "Merk: ved forste oppstart laster yente ned sanksjonslister (5-15 min)."
Write-Info "API og frontend starter umiddelbart - yente er klar naar statusindikator slutter aa spinne."
& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    Write-Warn "docker compose returnerte exit $LASTEXITCODE"
    Write-Warn "Yente kan fortsatt holde paa med datasett-nedlasting - dette er normalt ved forste oppstart."
    Write-Warn "Sjekk status med: docker compose logs yente"
} else {
    Write-OK "Alle tjenester er oppe"
}

# -- Database-migrasjoner -----------------------------------------------------

Write-Header "Database-migrasjoner"

Write-Info "Kjorer alembic upgrade head inne i api-containeren ..."
docker compose exec api alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Warn "Migrering feilet (exit $LASTEXITCODE) - sjekk loggene med: docker compose logs api"
} else {
    Write-OK "Databasen er oppdatert"
}

# -- Ferdig -------------------------------------------------------------------

Write-Header "Systemet er klart"
Write-OK "Frontend       ->  http://localhost:5173"
Write-OK "API            ->  http://localhost:8000"
Write-OK "API-docs       ->  http://localhost:8000/docs"
Write-OK "Yente (admin)  ->  http://localhost:8001"
Write-OK "Elasticsearch  ->  http://localhost:9200"
Write-Host ""
Write-Info "Sanksjonsliste-status: http://localhost:8001/catalog"
Write-Info "Yente-logg:  docker compose logs -f yente"
Write-Info "ES-logg:     docker compose logs -f elasticsearch"
Write-Info "Alle logger: docker compose logs -f"
Write-Info "Stopp:       .\stop.ps1"
Write-Host ""

if (-not $NoBrowser) {
    Start-Process "http://localhost:5173"
}
