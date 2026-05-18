# LAN-testing — la en kollega teste compliance-systemet

Denne guiden beskriver hvordan du starter systemet slik at en kollega på **samme lokale nettverk**
(kontor-WiFi, hjemmenett, VPN-hub) kan teste applikasjonen i sin nettleser uten å installere noe.

---

## Forutsetninger

| Krav | Detalj |
|------|--------|
| Docker Desktop | Kjører på *din* maskin |
| API-nøkler | `ANTHROPIC_API_KEY` og/eller `OPENAI_API_KEY` satt i `.env` |
| Brannmur | Port **5173** må være åpen innover på din maskin (se punkt 3) |

---

## 1 — Finn maskinens LAN-IP

**Windows (PowerShell / cmd):**
```
ipconfig
```
Se etter `IPv4 Address` under det aktive nettverkskortet (f.eks. `192.168.1.42`).

**macOS / Linux:**
```
ip addr   # eller: ifconfig
```
Se etter `inet`-linjen under `eth0` / `en0` / `wlan0`.

> Tips: IP-en starter vanligvis med `192.168.x.x` eller `10.x.x.x`.

---

## 2 — Start systemet

```bash
# Fra rot-mappen i prosjektet:
docker compose up --build
```

Første gang tar dette 3–5 minutter (Elasticsearch og Yente trenger tid på å starte).
Vent til du ser noe à la:

```
frontend-1  |   VITE v5.x.x  ready in 800 ms
frontend-1  |   ➜  Local:   http://localhost:5173/
frontend-1  |   ➜  Network: http://192.168.1.42:5173/
```

---

## 3 — Åpne port 5173 i Windows-brannmuren (én gang)

Kjør i PowerShell som administrator:

```powershell
New-NetFirewallRule `
  -DisplayName "Vite dev server (compliance LAN)" `
  -Direction Inbound `
  -Protocol TCP `
  -LocalPort 5173 `
  -Action Allow
```

For å fjerne regelen igjen etterpå:
```powershell
Remove-NetFirewallRule -DisplayName "Vite dev server (compliance LAN)"
```

---

## 4 — Kollegaen åpner applikasjonen

Send kollegaen denne URL-en (bytt ut IP-en med din fra punkt 1):

```
http://192.168.1.42:5173
```

Det er alt. Ingen installasjon, ingen konfigurasjon.

---

## Slik fungerer det (teknisk)

```
Kollegaens nettleser
        │
        │  HTTP/WS  port 5173
        ▼
   Vite dev-server  (Docker-container på din maskin)
        │
        │  /api/* proxyes server-side
        ▼
   FastAPI  (Docker-container, intern port 8000)
```

- Nettleseren kommuniserer **kun** med port 5173 — én origin, ingen CORS-problemer.
- Vite proxy-er alle `/api/*`-kall internt i Docker-nettverket til `http://api:8000`.
- Hot Module Replacement (HMR/auto-reload) fungerer over LAN fordi Vite sender
  WebSocket-adressen tilbake til klientens *egen* host, ikke hardkodet `localhost`.

---

## Feilsøking

| Symptom | Løsning |
|---------|---------|
| Kollegaen får "Connection refused" | Sjekk at port 5173 er åpen (punkt 3) |
| Siden laster, men API-kall feiler | Sjekk at `docker compose up` kjører og at Vite-loggen ikke viser proxy-feil |
| HMR/reload fungerer ikke på kollegaens PC | Normalt — det er et kjent Edge-case. Full reload (F5) fungerer alltid |
| Elasticsearch starter ikke | Gi det 2–3 minutter ekstra; første indeksering av sanksjonslister tar tid |

---

## Stoppe systemet

```bash
docker compose down
```

Data (PostgreSQL, uploads) bevares i Docker-volumene til neste gang.
