<#
.SYNOPSIS
    Stopper XLENT Compliance-systemet.

.DESCRIPTION
    Stopper alle Docker-tjenester. Data (database og opplastede filer)
    beholdes i Docker-volumes og er tilgjengelig ved neste oppstart.

.PARAMETER Clean
    Fjerner ogsa Docker-volumes (sletter databasen og opplastede filer).
    Bruk med forsiktighet - alle data gar tapt.

.EXAMPLE
    .\stop.ps1
    .\stop.ps1 -Clean
#>
param(
    [switch]$Clean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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

Write-Header "XLENT Compliance - stopp"

Set-Location $Root

if ($Clean) {
    Write-Warn "ADVARSEL: -Clean sletter databasen, opplastede filer OG yente-indeksen."
    Write-Warn "Yente maa laste ned alle sanksjonslister paa nytt ved neste oppstart (5-15 min)."
    $confirm = Read-Host "  Skriv 'ja' for a bekrefte"
    if ($confirm -ne "ja") {
        Write-Info "Avbrutt - ingen endringer gjort."
        exit 0
    }
    Write-Info "Stopper og sletter volumes ..."
    docker compose down --volumes --remove-orphans
} else {
    Write-Info "Stopper tjenester (data beholdes) ..."
    docker compose down --remove-orphans
}

if ($LASTEXITCODE -ne 0) {
    Write-Warn "docker compose down returnerte exit $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-OK "Alle tjenester er stoppet"
if ($Clean) {
    Write-Warn "Volumes slettet - database, filer og yente-indeks er borte"
}
Write-Host ""
Write-Info "Start igjen med: .\start.ps1"
Write-Host ""
