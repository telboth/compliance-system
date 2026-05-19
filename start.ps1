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

function Test-PathCaseExact([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $full = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetPathRoot($full)
    $relative = $full.Substring($root.Length).TrimStart("\")
    if ([string]::IsNullOrWhiteSpace($relative)) {
        return $true
    }

    $current = $root
    foreach ($segment in ($relative -split "[\\/]" | Where-Object { $_ -ne "" })) {
        $children = Get-ChildItem -LiteralPath $current -Force -ErrorAction SilentlyContinue
        if (-not $children) { return $false }
        $match = $children | Where-Object { $_.Name -ceq $segment } | Select-Object -First 1
        if (-not $match) { return $false }
        $current = Join-Path $current $match.Name
    }
    return $true
}

function Resolve-AliasImportCandidates(
    [string]$FrontendSrcRoot,
    [string]$AliasPath
) {
    $normalized = $AliasPath -replace "/", "\"
    $base = Join-Path $FrontendSrcRoot $normalized

    if ($normalized -match "\.(ts|tsx|js|jsx|json|css|svg)$") {
        return @($base)
    }

    return @(
        "$base.ts",
        "$base.tsx",
        "$base.js",
        "$base.jsx",
        "$base.json",
        "$base.css",
        "$base.svg",
        (Join-Path $base "index.ts"),
        (Join-Path $base "index.tsx"),
        (Join-Path $base "index.js"),
        (Join-Path $base "index.jsx")
    )
}

function Validate-FrontendAliasImports([string]$ProjectRootPath) {
    $frontendRoot = Join-Path $ProjectRootPath "frontend"
    $frontendSrc = Join-Path $frontendRoot "src"
    if (-not (Test-Path $frontendSrc)) {
        Write-Warn "Frontend-kildekode ble ikke funnet ($frontendSrc). Hopper over import-sjekk."
        return
    }

    Write-Header "Frontend import-sjekk"
    Write-Info "Sjekker @/ imports for manglende filer og case-mismatch ..."

    $files = Get-ChildItem -LiteralPath $frontendSrc -Recurse -File -Include *.ts,*.tsx,*.js,*.jsx
    $issues = New-Object System.Collections.Generic.List[string]
    $pattern = '(?:from\s+["'']@/([^"'']+)["''])|(?:import\(\s*["'']@/([^"'']+)["'']\s*\))'

    foreach ($file in $files) {
        $content = Get-Content -LiteralPath $file.FullName -Raw
        $matches = [regex]::Matches($content, $pattern)
        foreach ($m in $matches) {
            $spec = if (-not [string]::IsNullOrWhiteSpace($m.Groups[1].Value)) {
                $m.Groups[1].Value
            } else {
                $m.Groups[2].Value
            }
            if ([string]::IsNullOrWhiteSpace($spec)) { continue }

            $candidates = Resolve-AliasImportCandidates -FrontendSrcRoot $frontendSrc -AliasPath $spec
            $existing = @($candidates | Where-Object { Test-Path -LiteralPath $_ })
            if ($existing.Count -eq 0) {
                $issues.Add("$($file.FullName): mangler target for @/$spec")
                continue
            }

            $hasExact = $false
            foreach ($candidate in $existing) {
                if (Test-PathCaseExact -Path $candidate) {
                    $hasExact = $true
                    break
                }
            }
            if (-not $hasExact) {
                $issues.Add("$($file.FullName): case-mismatch i import @/$spec")
            }
        }
    }

    if ($issues.Count -gt 0) {
        Write-Fail "Frontend import-sjekk feilet."
        $issues | Select-Object -Unique | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
        Write-Host ""
        Write-Host "  Korriger imports/filnavn og kjor start.ps1 pa nytt." -ForegroundColor Yellow
        exit 1
    }

    Write-OK "Frontend import-sjekk OK"
}

function Get-ComposeExit137Services {
    try {
        $raw = docker compose ps --all --format json 2>$null
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($raw)) {
            return @()
        }
        $parsed = $raw | ConvertFrom-Json
        if ($parsed -isnot [System.Array]) {
            $parsed = @($parsed)
        }
        return @(
            $parsed |
            Where-Object { $_.State -eq "exited" -and [int]$_.ExitCode -eq 137 } |
            ForEach-Object { $_.Service } |
            Select-Object -Unique
        )
    } catch {
        return @()
    }
}

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

# -- Frontend import-sjekk ----------------------------------------------------

Validate-FrontendAliasImports -ProjectRootPath $Root

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
    $composeExitCode = $LASTEXITCODE
    Write-Warn "docker compose returnerte exit $composeExitCode"
    $exit137Services = @(
        Get-ComposeExit137Services |
        Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) }
    )
    $exit137Count = @($exit137Services).Length
    if ($composeExitCode -eq 137 -or $exit137Count -gt 0) {
        Write-Fail "En eller flere containere ble drept med exit 137 (SIGKILL)."
        if ($exit137Count -gt 0) {
            Write-Warn "Berorte tjenester: $($exit137Services -join ', ')"
        }
        Write-Warn "Vanligste arsaker: for lite minne i Docker Desktop, eller WSL2 etter install/restart."
        Write-Warn "Tiltak:"
        Write-Warn "  1) Restart maskinen (spesielt etter ny Docker/WSL-installasjon)."
        Write-Warn "  2) Sett Docker Desktop Memory til minst 6 GB (helst 8 GB)."
        Write-Warn "  3) Senk ES-heap i .env ved lav-RAM maskin:"
        Write-Warn "     ELASTICSEARCH_JAVA_OPTS=-Xms256m -Xmx256m"
        Write-Warn "  4) Kjor pa nytt:"
        Write-Warn "     docker compose down --remove-orphans"
        Write-Warn "     .\\start.ps1"
        Write-Warn "Detaljlogger:"
        Write-Warn "  docker compose logs --tail=200 elasticsearch yente api"
        exit 137
    } else {
        Write-Warn "Yente kan fortsatt holde paa med datasett-nedlasting - dette er normalt ved forste oppstart."
        Write-Warn "Sjekk status med: docker compose logs yente"
    }
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
