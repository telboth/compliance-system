# XLENT Compliance System

Docker-basert compliance-applikasjon (API, worker, frontend, PostgreSQL, Redis, Elasticsearch, Yente).

## Rask oppstart (Windows)

Forutsetninger:
- Docker Desktop
- Git

### Alternativ 0: Ingen manuell git clone (bootstrap)
```powershell
$script = "$env:TEMP\install-compliance.ps1"
Invoke-WebRequest -UseBasicParsing "https://raw.githubusercontent.com/telboth/compliance-system/main/install.ps1" -OutFile $script
powershell -ExecutionPolicy Bypass -File $script
```
Dette kloner automatisk repo til `C:\Users\<bruker>\compliance-system` og starter systemet.
For helautomatisk kjøring uten spørsmål:
```powershell
powershell -ExecutionPolicy Bypass -File $script -NonInteractive
```
Merk: Ved første Docker-installasjon kan Windows-restart være nødvendig (typisk WSL2-oppdatering).
Hvis du kjører scriptet fra USB og mangler `.env`/`.secrets`, kan du legge disse filene ved siden av scriptet.
Scriptet prøver automatisk å kopiere manglende filer fra script-mappen.

### Alternativ A: Repo er allerede klonet
```powershell
cd C:\path\to\compliance-system
.\install.ps1 -SkipClone
```

### Alternativ B: Klon + oppsett i ett
```powershell
git clone https://github.com/<org>/<repo>.git C:\apps\compliance-system
cd C:\apps\compliance-system
.\install.ps1 -SkipClone
```

## Scriptoversikt

- `install.ps1`: installasjon/oppsett for ny maskin, valgfritt klon/pull, oppretter `.env`/`.secrets`, starter systemet.
- `start.ps1`: starter containere + kjører migrasjoner.
- `stop.ps1`: stopper containere (`-Clean` sletter data-volumer).

## Første gangs konfigurasjon

- Legg inn minst én LLM-nøkkel i `.secrets`:
  - `OPENAI_API_KEY` eller `ANTHROPIC_API_KEY`
- Scriptet oppretter `.env` og `.secrets` automatisk fra eksempel-filer hvis de mangler.
- Hvis du får `exit 137` ved oppstart på en svak maskin, reduser ES-heap i `.env`:
  - `ELASTICSEARCH_JAVA_OPTS=-Xms256m -Xmx256m`

## URL-er

- Frontend: `http://localhost:5173`
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
