<#
.SYNOPSIS
    Enkel installasjon/oppsett av XLENT Compliance pa ny Windows-maskin.

.DESCRIPTION
    Scriptet kan enten:
    1) Kjores inne i et allerede klonet repo (standard), eller
    2) Klone repo fra GitHub til en malmappe og sette opp der.

    Deretter:
    - sjekker Git, WSL og Docker
    - valgfritt apner LAN-port 5173 i Windows-brannmur
    - oppretter .env/.secrets fra eksempel-filer ved behov
    - starter systemet via start.ps1

.PARAMETER SkipClone
    Ikke klon/pull repo. Bruk mappen scriptet ligger i.

.PARAMETER RepoUrl
    GitHub-URL til repoet. Brukes nar -SkipClone IKKE er satt.

.PARAMETER InstallDir
    Mappe der repoet skal ligge lokalt. Brukes nar -SkipClone IKKE er satt.

.PARAMETER Branch
    Branch som skal klones/sjekkes ut.

.PARAMETER Build
    Sendes videre til start.ps1 for tvungen re-build av containere.

.PARAMETER NoBrowser
    Sendes videre til start.ps1 for a unnga automatisk apning av nettleser.

.PARAMETER NoStart
    Gjennomfor oppsett, men ikke start systemet.

.PARAMETER OpenLanFirewall
    Oppretter inbound firewall-regel for TCP 5173 (for LAN-testing).

.PARAMETER NonInteractive
    Kjor uten sporsmal/prompts. Scriptet prover automatisk Docker-install/start
    der det er mulig, og feiler eksplisitt hvis noe blokkerer videre oppsett.

.PARAMETER SeedFilesDir
    Valgfri mappe med seed-filer (f.eks. USB) som kan inneholde:
    .env, .env.example, .secrets, .secrets.example.
    Hvis filer mangler i prosjektmappen, kopieres de herfra hvis de finnes.

.EXAMPLE
    .\install.ps1 -SkipClone

.EXAMPLE
    .\install.ps1 -RepoUrl https://github.com/<org>/<repo>.git -InstallDir C:\apps\compliance-system
#>
param(
    [switch]$Help,
    [switch]$Update,
    [switch]$Stop,
    [switch]$SkipClone,
    [string]$RepoUrl = "https://github.com/telboth/compliance-system.git",
    [string]$InstallDir = "$env:USERPROFILE\compliance-system",
    [string]$Branch = "main",
    [switch]$Build,
    [switch]$NoBrowser,
    [switch]$NoStart,
    [switch]$OpenLanFirewall,
    [switch]$NonInteractive,
    [string]$SeedFilesDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$script:IsNonInteractive = $false

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

function Refresh-ProcessPathFromRegistry {
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $combined = @($machinePath, $userPath) -join ";"
    $combined = ($combined -split ";" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique) -join ";"
    $env:Path = $combined
}

function Show-RebootGuidance {
    Write-Warn "Maskinen ma sannsynligvis restartes for a fullfore Docker/WSL-oppsett."
    Write-Host "  Anbefalt neste steg:" -ForegroundColor Yellow
    Write-Host "    1) Restart Windows" -ForegroundColor Yellow
    Write-Host "    2) Start Docker Desktop manuelt (vent pa 'Engine running')" -ForegroundColor Yellow
    Write-Host "    3) Kjor install.ps1 pa nytt" -ForegroundColor Yellow
    Write-Host "  Valgfri WSL-sjekk:" -ForegroundColor Yellow
    Write-Host "    wsl --status" -ForegroundColor Yellow
    Write-Host "    wsl --update" -ForegroundColor Yellow
}

function Test-HttpAvailable(
    [string]$Url,
    [int]$TimeoutSeconds = 4
) {
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Uri $Url -Method Get -TimeoutSec $TimeoutSeconds
        return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500)
    } catch {
        return $false
    }
}

function Ask-YesNo([string]$Question, [bool]$DefaultNo = $true) {
    if ($script:IsNonInteractive) {
        return (-not $DefaultNo)
    }
    $suffix = if ($DefaultNo) { " [y/N]" } else { " [Y/n]" }
    $answer = Read-Host ("  " + $Question + $suffix)
    if ([string]::IsNullOrWhiteSpace($answer)) {
        return (-not $DefaultNo)
    }
    $trim = $answer.Trim().ToLowerInvariant()
    return $trim -in @("y", "yes", "j", "ja")
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Ensure-Command([string]$CommandName, [string]$InstallHint) {
    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        Write-Fail "'$CommandName' ble ikke funnet."
        Write-Host "  Installer: $InstallHint" -ForegroundColor Yellow
        exit 1
    }
}

function Ensure-GitReady {
    if (Get-Command git -ErrorAction SilentlyContinue) {
        Write-OK "Git er installert"
        return
    }

    Write-Warn "Git ble ikke funnet."
    Write-Host "  Git kreves for kloning/oppdatering av kode fra GitHub." -ForegroundColor Yellow

    $canInstallWithWinget = [bool](Get-Command winget -ErrorAction SilentlyContinue)
    if ($canInstallWithWinget) {
        $installNow = Ask-YesNo "Vil du installere Git na med winget?" -DefaultNo:$false
        if ($installNow) {
            Write-Info "Installerer Git via winget ..."
            $wingetOutput = & winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements 2>&1
            $wingetExit = $LASTEXITCODE
            $wingetText = ($wingetOutput | Out-String)

            if ($wingetExit -ne 0) {
                Write-Fail "Git installasjon feilet (winget exit $wingetExit)."
                Write-Host "  Proev manuell installasjon: https://git-scm.com/download/win" -ForegroundColor Yellow
                Write-Host "  Winget-output:" -ForegroundColor DarkYellow
                Write-Host "  $wingetText" -ForegroundColor DarkYellow
                exit 1
            }

            Refresh-ProcessPathFromRegistry
            if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
                Write-Fail "Git ble installert, men er ikke tilgjengelig i PATH ennå."
                Write-Host "  Lukk og apne PowerShell pa nytt, eller restart maskinen, og kjor scriptet igjen." -ForegroundColor Yellow
                exit 1
            }

            $gitVersion = (& git --version 2>$null)
            Write-OK "Git er installert: $gitVersion"
            return
        }
    } else {
        Write-Warn "winget er ikke tilgjengelig pa maskinen."
    }

    Write-Fail "Git er ikke installert."
    Write-Host "  Installer med en av disse:" -ForegroundColor Yellow
    Write-Host "    1) winget install -e --id Git.Git" -ForegroundColor Yellow
    Write-Host "    2) https://git-scm.com/download/win" -ForegroundColor Yellow
    Write-Host "  Kjor deretter install.ps1 pa nytt." -ForegroundColor Yellow
    exit 1
}

function Get-WslStatusOutput {
    if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
        return @{
            Installed = $false
            Output = "wsl command not found"
            ExitCode = 127
        }
    }
    $out = (& wsl --status 2>&1 | Out-String)
    $exitCode = $LASTEXITCODE
    $installed = ($exitCode -eq 0)
    return @{
        Installed = $installed
        Output = $out
        ExitCode = $exitCode
    }
}

function Install-Wsl {
    if (-not (Test-IsAdministrator)) {
        Write-Fail "WSL mangler, og scriptet kjores ikke som administrator."
        Write-Host "  Kjor PowerShell som Administrator og kjor install.ps1 pa nytt." -ForegroundColor Yellow
        Write-Host "  Alternativt installer manuelt med: wsl --install --no-distribution" -ForegroundColor Yellow
        exit 1
    }

    if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
        Write-Fail "Fant ikke wsl.exe pa systemet."
        Write-Host "  Oppdater Windows og prover igjen. Eventuelt installer WSL manuelt via Microsoft Docs." -ForegroundColor Yellow
        exit 1
    }

    Write-Info "Installerer/aktiverer Windows Subsystem for Linux ..."
    $installOutput = (& wsl --install --no-distribution 2>&1 | Out-String)
    $installExit = $LASTEXITCODE
    if ($installExit -ne 0) {
        Write-Fail "WSL installasjon feilet (exit $installExit)."
        Write-Host "  Output:" -ForegroundColor DarkYellow
        Write-Host "  $installOutput" -ForegroundColor DarkYellow
        exit 1
    }

    Write-Warn "WSL installert/oppdatert. Windows ma restartes for a fullfore."
    Show-RebootGuidance
    exit 1
}

function Ensure-WSLReady {
    $status = Get-WslStatusOutput
    if ($status.Installed) {
        Write-OK "WSL er installert"
        return
    }

    Write-Warn "WSL er ikke installert eller ikke klart."
    Write-Host "  Docker Desktop krever normalt WSL2 pa Windows." -ForegroundColor Yellow

    $installNow = Ask-YesNo "Vil du installere/aktivere WSL na?" -DefaultNo:$false
    if ($installNow) {
        Install-Wsl
    }

    Write-Fail "WSL er ikke klart."
    Write-Host "  Installer med: wsl --install --no-distribution" -ForegroundColor Yellow
    Write-Host "  Restart Windows, og kjor install.ps1 pa nytt." -ForegroundColor Yellow
    exit 1
}

function Start-DockerDesktopApp {
    $candidatePaths = @(
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
        "$env:ProgramFiles\Docker\Docker\Docker Desktop"
    )
    foreach ($path in $candidatePaths) {
        if (Test-Path $path) {
            Start-Process -FilePath $path | Out-Null
            return $true
        }
    }
    try {
        Start-Process "Docker Desktop" | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Wait-DockerEngine([int]$TimeoutSeconds = 240) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
            Start-Sleep -Seconds 4
            continue
        }
        try {
            $null = & docker info 2>&1
            if ($LASTEXITCODE -eq 0) {
                return $true
            }
        } catch {
            # Docker command can briefly fail while engine is booting.
        }
        Start-Sleep -Seconds 4
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Ensure-DockerDesktopReady {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Warn "Docker CLI ble ikke funnet."
        Write-Host "  Dette systemet krever Docker Desktop." -ForegroundColor Yellow
        $canInstallWithWinget = [bool](Get-Command winget -ErrorAction SilentlyContinue)
        if ($canInstallWithWinget) {
            $installNow = Ask-YesNo "Vil du installere Docker Desktop na med winget?" -DefaultNo:$false
            if ($installNow) {
                Write-Info "Installerer Docker Desktop via winget ..."
                $wingetOutput = & winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements 2>&1
                $wingetExit = $LASTEXITCODE
                $wingetText = ($wingetOutput | Out-String)

                if ($wingetExit -ne 0) {
                    $restartHint = $wingetText -match "(?i)restart|reboot|log off|sign out|wsl"
                    if ($restartHint) {
                        Write-Warn "Winget indikerer at restart/logoff trengs for a fullfore installasjonen."
                        Show-RebootGuidance
                        exit 1
                    }
                    Write-Fail "Docker Desktop installasjon feilet (winget exit $wingetExit)."
                    Write-Host "  Proev manuell installasjon: https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
                    Write-Host "  Winget-output:" -ForegroundColor DarkYellow
                    Write-Host "  $wingetText" -ForegroundColor DarkYellow
                    exit 1
                }

                Refresh-ProcessPathFromRegistry
                Write-OK "Docker Desktop installert."
                Write-Info "Starter Docker Desktop ..."
                if (-not (Start-DockerDesktopApp)) {
                    Write-Warn "Klarte ikke starte Docker Desktop automatisk."
                    Write-Host "  Start Docker Desktop manuelt fra Start-menyen." -ForegroundColor Yellow
                }
                Write-Info "Venter pa at Docker Engine blir klar (inntil 4 min) ..."
                if (-not (Wait-DockerEngine -TimeoutSeconds 240)) {
                    Write-Fail "Docker Engine ble ikke klar innen tidsfristen."
                    Write-Host "  Start Docker Desktop manuelt og verifiser med: docker info" -ForegroundColor Yellow
                    Show-RebootGuidance
                    exit 1
                }
                Write-OK "Docker Desktop er installert og kjører"
                return
            }
        } else {
            Write-Warn "winget er ikke tilgjengelig pa maskinen."
        }

        Write-Fail "Docker Desktop er ikke installert."
        Write-Host "  Installer med en av disse:" -ForegroundColor Yellow
        Write-Host "    1) winget install -e --id Docker.DockerDesktop" -ForegroundColor Yellow
        Write-Host "    2) https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
        Write-Host "  Start deretter Docker Desktop og kjor scriptet pa nytt." -ForegroundColor Yellow
        exit 1
    }

    $dockerInfo = & docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Docker CLI finnes, men Docker Desktop/Engine svarer ikke."
        $startNow = Ask-YesNo "Vil du at scriptet skal proeve aa starte Docker Desktop na?" -DefaultNo:$false
        if ($startNow) {
            if (-not (Start-DockerDesktopApp)) {
                Write-Warn "Klarte ikke starte Docker Desktop automatisk."
            } else {
                Write-Info "Docker Desktop startet. Venter pa Engine (inntil 4 min) ..."
                if (Wait-DockerEngine -TimeoutSeconds 240) {
                    Write-OK "Docker Desktop er installert og kjører"
                    return
                }
            }
        }

        Write-Fail "Docker Desktop/Engine er ikke klar."
        Write-Host "  Hva du ma gjore:" -ForegroundColor Yellow
        Write-Host "    1) Start 'Docker Desktop' fra Start-menyen" -ForegroundColor Yellow
        Write-Host "    2) Vent til status er 'Engine running'" -ForegroundColor Yellow
        Write-Host "    3) Verifiser med: docker info" -ForegroundColor Yellow
        Write-Host "  Teknisk feilmelding fra docker info:" -ForegroundColor Yellow
        Write-Host "  $dockerInfo" -ForegroundColor DarkYellow
        Show-RebootGuidance
        exit 1
    }

    Write-OK "Docker Desktop er installert og kjører"
}

function Ensure-FileFromExample([string]$TargetPath, [string]$ExamplePath) {
    if (Test-Path $TargetPath) {
        return
    }
    if (-not (Test-Path $ExamplePath)) {
        Write-Fail "Mangler eksempel-fil: $ExamplePath"
        exit 1
    }
    Copy-Item $ExamplePath $TargetPath
    Write-Warn "Opprettet $([IO.Path]::GetFileName($TargetPath)) fra eksempel."
}

function Find-InstallMedia {
    <#
    .SYNOPSIS
        Prøver å finne install-mediet (USB e.l.) med .secrets*-filer.
        Sjekker først om scriptet kjøres fra en flyktig enhet,
        deretter scanner alle removable-stasjoner på maskinen.
    .OUTPUTS
        Full sti til mappen som inneholder .secrets*-filer, eller $null.
    #>

    # 1. Kjøres scriptet fra en USB/flyktig stasjon?
    $scriptDriveLetter = (Split-Path -Qualifier $PSScriptRoot).TrimEnd(':')
    try {
        $scriptDisk = Get-CimInstance Win32_LogicalDisk `
            -Filter "DeviceID='${scriptDriveLetter}:'" -ErrorAction SilentlyContinue
        if ($scriptDisk -and $scriptDisk.DriveType -eq 2) {
            $found = Get-ChildItem -Path $PSScriptRoot -Filter ".secrets*" -Force -ErrorAction SilentlyContinue
            if ($found) {
                return $PSScriptRoot
            }
        }
    } catch { }

    # 2. Søk gjennom alle removable-stasjoner etter .secrets*-filer
    try {
        $removable = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=2" -ErrorAction SilentlyContinue
        foreach ($disk in $removable) {
            $root = $disk.DeviceID + "\"
            $found = Get-ChildItem -Path $root -Filter ".secrets*" -Force -ErrorAction SilentlyContinue
            if ($found) {
                return $root
            }
        }
    } catch { }

    return $null
}

function Try-CopySecretsFromMedia(
    [string]$ProjectRootPath,
    [string]$MediaDirPath
) {
    <#
    .SYNOPSIS
        Kopierer alle .secrets*-filer fra install-mediet til prosjektmappen.
        Eksisterende filer overskrives IKKE.
    #>
    if ([string]::IsNullOrWhiteSpace($MediaDirPath)) {
        return
    }
    if (-not (Test-Path $MediaDirPath)) {
        Write-Warn "Install-media-mappe finnes ikke: $MediaDirPath"
        return
    }

    $resolvedProjectRoot = (Resolve-Path $ProjectRootPath).Path
    $resolvedMediaDir    = (Resolve-Path $MediaDirPath).Path
    if ($resolvedProjectRoot -eq $resolvedMediaDir) {
        return
    }

    $secretFiles = Get-ChildItem -Path $resolvedMediaDir -Filter ".secrets*" -Force -ErrorAction SilentlyContinue
    if (-not $secretFiles) {
        Write-Warn "Ingen .secrets*-filer funnet på installasjonsmedia: $resolvedMediaDir"
        return
    }

    $copied  = 0
    $skipped = 0
    foreach ($file in $secretFiles) {
        $target = Join-Path $resolvedProjectRoot $file.Name
        if (Test-Path $target) {
            Write-Info "Hopper over '$($file.Name)' — finnes allerede i prosjektmappen."
            $skipped++
            continue
        }
        Copy-Item $file.FullName $target
        Write-OK "Kopierte '$($file.Name)' fra installasjonsmedia"
        $copied++
    }
    if ($copied -eq 0 -and $skipped -gt 0) {
        Write-Info "Alle .secrets*-filer fantes allerede — ingen endringer."
    } else {
        Write-Info "$copied fil(er) kopiert, $skipped hoppet over."
    }
}

function Get-KeyValueMap([string]$Path) {
    $map = @{}
    if (-not (Test-Path $Path)) {
        return $map
    }
    foreach ($line in Get-Content $Path) {
        if ($line -notmatch "^\s*[A-Za-z_][A-Za-z0-9_]*\s*=") { continue }
        $parts = $line -split "=", 2
        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        $map[$key] = $value
    }
    return $map
}

function Ensure-FirewallRule5173 {
    $ruleName = "Vite dev server (compliance LAN)"
    $existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if ($null -ne $existing) {
        Write-Info "Brannmurregel finnes allerede: $ruleName"
        return
    }
    New-NetFirewallRule `
        -DisplayName $ruleName `
        -Direction Inbound `
        -Protocol TCP `
        -LocalPort 5173 `
        -Action Allow | Out-Null
    Write-OK "Brannmurregel opprettet for port 5173"
}

function Show-Help {
    $defaultRepo   = $RepoUrl
    $defaultDir    = $InstallDir
    $defaultBranch = $Branch
    Write-Host @"

XLENT Compliance - installasjonscript
======================================

Bruk:
  .\install.ps1 [opsjoner]

VANLIGE OPSJONER:
  -Help              Vis denne hjelpen og avslutt.
  -Update            Last ned siste versjon fra GitHub og start systemet pa nytt
                     med re-bygging av containere (-Build implisert).
  -Stop              Stopp kjorende containere og avslutt.

INSTALLASJON / OPPSTART:
  -SkipClone         Ikke klon/pull repo — bruk mappen scriptet ligger i.
  -RepoUrl <url>     GitHub-URL til repoet.
                     (standard: $defaultRepo)
  -InstallDir <sti>  Lokal mappe der repoet skal ligge.
                     (standard: $defaultDir)
  -Branch <branch>   Branch som klones/sjekkes ut.
                     (standard: $defaultBranch)
  -SeedFilesDir <sti> Mappe med .secrets*-filer (USB e.l.) — brukes automatisk
                     hvis tom og scriptet kjores fra en USB-stasjon.

  -Build             Tving re-bygging av Docker-containere.
  -NoBrowser         Ikke apne nettleser automatisk etter oppstart.
  -NoStart           Sett opp filene, men ikke start systemet.
  -OpenLanFirewall   Apne TCP-port 5173 i Windows-brannmur (krever admin).
  -NonInteractive    Ingen sporsmalsett — bruk standardvalg overalt.

EKSEMPLER:
  .\install.ps1                          # Vanlig forrestegangs-installasjon
  .\install.ps1 -Update                  # Oppdater til siste versjon og restart
  .\install.ps1 -Stop                    # Stopp systemet
  .\install.ps1 -Help                    # Vis denne hjelpen
  .\install.ps1 -Build                   # Tving re-bygging av containere
  .\install.ps1 -NoStart                 # Sett opp uten oppstart
  .\install.ps1 -SeedFilesDir E:\        # Bruk E:\ som kilde for .secrets*-filer

"@
    exit 0
}

function Update-ProjectCode([string]$ProjectPath) {
    <#
    .SYNOPSIS
        Henter siste versjon fra GitHub.
        Forsøker git pull --ff-only; tilbyr stash + pull + stash-pop dersom
        lokale endringer blokkerer oppdateringen.
    #>
    Write-Info "Henter siste kode fra GitHub (branch: $Branch) ..."

    $gitFetch = (& git -C $ProjectPath fetch --all --prune 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "git fetch feilet."
        Write-Host "  $gitFetch" -ForegroundColor DarkYellow
        exit 1
    }

    $gitPull = (& git -C $ProjectPath pull --ff-only 2>&1 | Out-String)
    if ($LASTEXITCODE -eq 0) {
        Write-OK "Kode oppdatert til siste versjon."
        return
    }

    Write-Warn "Direkte oppdatering blokkert av lokale endringer:"
    Write-Host "  $gitPull" -ForegroundColor DarkYellow

    $gitStatus = (& git -C $ProjectPath status --short 2>&1 | Out-String).Trim()
    if ($gitStatus) {
        Write-Info "Lokale endringer:"
        foreach ($line in ($gitStatus -split "`n")) {
            if ($line.Trim()) { Write-Host "    $line" -ForegroundColor DarkYellow }
        }
    }

    Write-Warn "Foreslatt losning: midlertidig lagre endringene (git stash), oppdater, gjenopprett."
    $stashAndPull = Ask-YesNo "Lagre lokale endringer, oppdater og gjenopprett (anbefalt)?" -DefaultNo:$false
    if (-not $stashAndPull) {
        Write-Fail "Avbrutt. Los konflikten manuelt og kjor -Update igjen."
        exit 1
    }

    Write-Info "Lagrer lokale endringer midlertidig (git stash) ..."
    $stashOut = (& git -C $ProjectPath stash push --include-untracked -m "install.ps1 -Update backup" 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "git stash feilet."
        Write-Host "  $stashOut" -ForegroundColor DarkYellow
        exit 1
    }

    $pullOut = (& git -C $ProjectPath pull --ff-only 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "git pull feilet selv etter stash. Gjenoppretter lokale endringer ..."
        Write-Host "  $pullOut" -ForegroundColor DarkYellow
        & git -C $ProjectPath stash pop 2>&1 | Out-Null
        exit 1
    }

    Write-OK "Kode oppdatert til siste versjon."
    Write-Info "Gjenoppretter lokale endringer (git stash pop) ..."
    $popOut = (& git -C $ProjectPath stash pop 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "git stash pop feilet — dine endringer ligger i 'git stash list'."
        Write-Host "  $popOut" -ForegroundColor DarkYellow
        Write-Host "  Kjor 'git stash pop' manuelt for a gjenopprette dem." -ForegroundColor Yellow
    } else {
        Write-OK "Lokale endringer gjenopprettet."
    }
}

function Stop-System {
    <#
    .SYNOPSIS
        Finner prosjektmappen og kjorer stop.ps1 (eller docker compose down direkte).
        Krever ikke --SkipClone eller git — finner rot via PSScriptRoot / InstallDir.
    #>
    $stopRoot = $null
    if (Test-Path (Join-Path $PSScriptRoot "stop.ps1")) {
        $stopRoot = $PSScriptRoot
    } elseif (Test-Path (Join-Path $PSScriptRoot "docker-compose.yml")) {
        $stopRoot = $PSScriptRoot
    } elseif (Test-Path (Join-Path $InstallDir "stop.ps1")) {
        $stopRoot = $InstallDir
    } elseif (Test-Path (Join-Path $InstallDir "docker-compose.yml")) {
        $stopRoot = $InstallDir
    }

    if (-not $stopRoot) {
        Write-Fail "Fant ikke stop.ps1 eller docker-compose.yml i kjent plassering."
        Write-Host "  Stopp manuelt med: docker compose down" -ForegroundColor Yellow
        exit 1
    }

    $stopScript = Join-Path $stopRoot "stop.ps1"
    if (Test-Path $stopScript) {
        Write-Info "Stopper systemet via stop.ps1 i $stopRoot ..."
        Push-Location $stopRoot
        try {
            & $stopScript
            if ($LASTEXITCODE -ne 0) {
                Write-Warn "stop.ps1 returnerte exit $LASTEXITCODE — fortsetter."
            }
        } finally {
            Pop-Location
        }
    } else {
        Write-Info "Stopper Docker-containere (docker compose down) i $stopRoot ..."
        Push-Location $stopRoot
        try {
            & docker compose down
        } finally {
            Pop-Location
        }
    }

    Write-OK "Systemet er stoppet."
}

function Resolve-ProjectRoot {
    if ($SkipClone) {
        if (-not (Test-Path (Join-Path $PSScriptRoot "start.ps1"))) {
            Write-Fail "-SkipClone ble brukt, men start.ps1 finnes ikke i script-mappen."
            Write-Host "  Kjor uten -SkipClone for automatisk kloning." -ForegroundColor Yellow
            exit 1
        }
        return $PSScriptRoot
    }

    $hasLocalRepo = (Test-Path (Join-Path $PSScriptRoot ".git")) -and (Test-Path (Join-Path $PSScriptRoot "start.ps1"))
    if ($hasLocalRepo) {
        Write-Info "Lokalt repo oppdaget i script-mappen - bruker eksisterende mappe."
        return $PSScriptRoot
    }

    if (-not (Test-Path $InstallDir)) {
        New-Item -ItemType Directory -Path $InstallDir | Out-Null
    }

    if ((-not (Test-Path (Join-Path $InstallDir ".git"))) -and ((Get-ChildItem -Force $InstallDir | Measure-Object).Count -gt 0)) {
        Write-Fail "InstallDir finnes og er ikke tom, men er ikke et git-repo: $InstallDir"
        Write-Host "  Velg en tom mappe med -InstallDir, eller slett innholdet i mappen." -ForegroundColor Yellow
        exit 1
    }

    $hasGit = Test-Path (Join-Path $InstallDir ".git")
    if ($hasGit) {
        Write-Info "Repo finnes fra for - oppdaterer branch '$Branch'."
        $gitFetch = (& git -C $InstallDir fetch --all --prune 2>&1 | Out-String)
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "git fetch feilet."
            Write-Host "  $gitFetch" -ForegroundColor DarkYellow
            exit 1
        }

        $gitCheckout = (& git -C $InstallDir checkout $Branch 2>&1 | Out-String)
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "git checkout $Branch feilet."
            Write-Host "  $gitCheckout" -ForegroundColor DarkYellow
            exit 1
        }

        $gitPull = (& git -C $InstallDir pull --ff-only 2>&1 | Out-String)
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "git pull --ff-only feilet — lokale endringer kan blokkere oppdatering."
            Write-Host "  $gitPull" -ForegroundColor DarkYellow
            $gitStatus = (& git -C $InstallDir status --short 2>&1 | Out-String).Trim()
            if ($gitStatus) {
                Write-Info "Lokale endringer i repoet:"
                foreach ($statusLine in ($gitStatus -split "`n")) {
                    if ($statusLine.Trim()) { Write-Host "    $statusLine" -ForegroundColor DarkYellow }
                }
            }
            Write-Warn "Alternativer:"
            Write-Host "    A) Fortsett uten kode-oppdatering (beholder lokale endringer)" -ForegroundColor Yellow
            Write-Host "    B) Avbryt og løs git-konflikten manuelt før du kjører scriptet igjen" -ForegroundColor Yellow
            $skipUpdate = Ask-YesNo "Vil du fortsette uten kode-oppdatering (A)?" -DefaultNo:$false
            if (-not $skipUpdate) {
                Write-Fail "Avbrutt. Tips: 'git stash' -> kjør scriptet -> 'git stash pop'"
                exit 1
            }
            Write-Warn "Fortsetter uten kode-oppdatering. Lokale endringer er beholdt."
        }
    } else {
        Write-Info "Kloner repo til $InstallDir ..."
        $gitClone = (& git clone --branch $Branch $RepoUrl $InstallDir 2>&1 | Out-String)
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "git clone feilet."
            Write-Host "  $gitClone" -ForegroundColor DarkYellow
            exit 1
        }
    }
    return $InstallDir
}

Write-Header "XLENT Compliance - installasjon"
$script:IsNonInteractive = [bool]$NonInteractive
if ($script:IsNonInteractive) {
    Write-Info "NonInteractive-modus aktiv: ingen prompts, bruker standard handlinger."
}

# ── Tidlig avslutning for -Help og -Stop ──────────────────────────────────────
if ($Help) { Show-Help }   # avslutter med exit 0

Ensure-GitReady
Ensure-WSLReady
Ensure-DockerDesktopReady

if ($Stop) {
    Stop-System
    exit 0
}

$projectRoot = Resolve-ProjectRoot
Write-OK "Prosjektmappe: $projectRoot"

if ($Update) {
    Write-Header "Oppdaterer kode"
    Update-ProjectCode -ProjectPath $projectRoot
}

if ($OpenLanFirewall) {
    if (-not (Test-IsAdministrator)) {
        Write-Warn "-OpenLanFirewall krever administrator-rettigheter. Hopper over."
    } else {
        Ensure-FirewallRule5173
    }
}

$envFile     = Join-Path $projectRoot ".env"
$envExample  = Join-Path $projectRoot ".env.example"
$secretsFile = Join-Path $projectRoot ".secrets"
$secretsExample = Join-Path $projectRoot ".secrets.example"

# Opprett .env og .secrets fra eksempel-filer om de mangler (fallback)
Ensure-FileFromExample -TargetPath $envFile     -ExamplePath $envExample
Ensure-FileFromExample -TargetPath $secretsFile -ExamplePath $secretsExample

# ── Kopier .secrets*-filer fra installasjonsmedia (USB e.l.) ─────────────────
Write-Header "Installasjonsmedia"
if (-not [string]::IsNullOrWhiteSpace($SeedFilesDir)) {
    $mediaDir = $SeedFilesDir
    Write-Info "Bruker angitt install-media-mappe: $mediaDir"
} else {
    Write-Info "Søker etter installasjonsmedia med .secrets*-filer ..."
    $mediaDir = Find-InstallMedia
    if ($mediaDir) {
        Write-OK "Installasjonsmedia funnet: $mediaDir"
    } else {
        Write-Warn "Fant ikke installasjonsmedia (USB e.l.) med .secrets*-filer."
        Write-Info "Tips: Bruk -SeedFilesDir <sti> for å angi mappen manuelt."
        Write-Info "      Rediger .secrets manuelt med dine API-nøkler ved behov."
    }
}
if ($mediaDir) {
    Try-CopySecretsFromMedia -ProjectRootPath $projectRoot -MediaDirPath $mediaDir
}

$secrets = Get-KeyValueMap -Path $secretsFile
$openai = ""
$anthropic = ""
if ($secrets.ContainsKey("OPENAI_API_KEY")) { $openai = $secrets["OPENAI_API_KEY"] }
if ($secrets.ContainsKey("ANTHROPIC_API_KEY")) { $anthropic = $secrets["ANTHROPIC_API_KEY"] }

if ([string]::IsNullOrWhiteSpace($openai) -and [string]::IsNullOrWhiteSpace($anthropic)) {
    Write-Warn "Ingen LLM-nokler funnet i .secrets."
    Write-Warn "Legg inn minst OPENAI_API_KEY eller ANTHROPIC_API_KEY for full funksjon."
}

if ($NoStart) {
    Write-Header "Ferdig"
    Write-OK "Oppsett fullfort uten oppstart."
    Write-Info "Neste steg: rediger .secrets ved behov, kjor deretter .\\start.ps1"
    exit 0
}

# Sjekk om systemet allerede kjorer
Write-Header "Starter systemet"
$frontendAlive = Test-HttpAvailable -Url "http://localhost:5173" -TimeoutSeconds 3
$apiAlive = Test-HttpAvailable -Url "http://localhost:8000/docs" -TimeoutSeconds 3
if ($frontendAlive -and $apiAlive) {
    Write-OK "Systemet kjorer allerede (frontend og API svarer)."
    if ($Update) {
        # -Update betyr alltid restart — ikke spor
        Write-Info "-Update angitt: oppdaterer og starter containerne pa nytt ..."
    } else {
        $restartAnyway = Ask-YesNo "Vil du starte/oppdatere containerne likevel?" -DefaultNo:$true
        if (-not $restartAnyway) {
            Write-Header "Installasjon ferdig"
            Write-OK "Frontend:      http://localhost:5173"
            Write-OK "API:           http://localhost:8000"
            Write-OK "API docs:      http://localhost:8000/docs"
            Write-Info "Stopp med: .\\stop.ps1"
            exit 0
        }
        Write-Info "Fortsetter med oppstart (kan midlertidig avbryte tjenestene) ..."
    }
} elseif ($frontendAlive -or $apiAlive) {
    Write-Warn "Systemet er delvis oppe. Starter/reparerer containerne ..."
}
$startScript = Join-Path $projectRoot "start.ps1"
if (-not (Test-Path $startScript)) {
    Write-Fail "Fant ikke start.ps1 i $projectRoot"
    exit 1
}

$startArgs = @()
if ($Build -or $Update) { $startArgs += "-Build" }   # -Update impliserer re-bygging
if ($NoBrowser) { $startArgs += "-NoBrowser" }

Push-Location $projectRoot
try {
    & $startScript @startArgs
    if ($LASTEXITCODE -ne 0) {
        $startExit = $LASTEXITCODE
        Write-Warn "start.ps1 returnerte exit $startExit. Verifiserer tjenestestatus ..."
        $frontendUp = Test-HttpAvailable -Url "http://localhost:5173" -TimeoutSeconds 6
        $apiUp = Test-HttpAvailable -Url "http://localhost:8000/docs" -TimeoutSeconds 6
        if ($frontendUp -and $apiUp) {
            Write-Warn "start.ps1 returnerte feil, men frontend og API svarer. Fortsetter."
        } else {
            Write-Fail "start.ps1 feilet med exit $startExit, og tjenestene svarer ikke."
            Write-Host "  Sjekk logger med:" -ForegroundColor Yellow
            Write-Host "    docker compose logs -f" -ForegroundColor Yellow
            exit $startExit
        }
    }
} finally {
    Pop-Location
}

Write-Header "Installasjon ferdig"
Write-OK "Frontend:      http://localhost:5173"
Write-OK "API:           http://localhost:8000"
Write-OK "API docs:      http://localhost:8000/docs"
Write-Info "Stopp med: .\\stop.ps1"
