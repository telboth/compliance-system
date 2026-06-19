# Changelog

Alle vesentlige endringer i XLENT Compliance dokumenteres her. Formatet følger [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) og prosjektet bruker [semantisk versjonering](https://semver.org/lang/no/).

## [Unreleased]

## [0.8.5] - 2026-06-19

### Added

- Klikkbar fakturapreview fra Fakturaer, Arbeidslister og relaterte tabeller.
- Utvidet Regulatorisk Radar og sanksjonsstatus for eksterne kilder, inkludert World Bank Debarred og tydeligere kildehelse.
- Synlig DEKSA-/eksportkontrollstatus i sanksjonsbildet.

### Changed

- Forenklet arbeidsliste-/review-kø-opplevelse og samlet fakturasøk under Fakturaer.
- Ryddet repo-/worktree-oppsett slik at `compliance-system-sync` er aktiv hovedmappe.
- Ryddet backend CI, testoppsett og runtime-artefakter.

### Fixed

- Blank frontend ved stale Vite-chunks/top-level renderfeil håndteres med root error boundary og preload-reload.
- Liste- og feedstatus viser mer konsistent siste oppdatering.
- GitHub Actions backend-jobb er grønn på `main`.

### Sprint 1 — Fundament

- Initielt prosjektskjelett: FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL, Redis
- Docker Compose for lokal utvikling (postgres + redis + api + worker + frontend)
- Datamodell for invoices, invoice_lines, entities, customers
- PDF-parser med autodeteksjon (pdfplumber for digitale PDF-er, Tesseract for skannet materiale)
- Endepunkter: `POST /api/v1/invoices/upload`, `GET /api/v1/invoices`, `GET /api/v1/invoices/{id}`, `GET /api/v1/health`
- Frontend-skjelett: Vite + React + TypeScript + Tailwind + TanStack Query
- pytest-oppsett med async testdatabase
