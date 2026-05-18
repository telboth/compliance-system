# Changelog

Alle vesentlige endringer i XLENT Compliance dokumenteres her. Formatet følger [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) og prosjektet bruker [semantisk versjonering](https://semver.org/lang/no/).

## [Unreleased]

### Sprint 1 — Fundament

- Initielt prosjektskjelett: FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL, Redis
- Docker Compose for lokal utvikling (postgres + redis + api + worker + frontend)
- Datamodell for invoices, invoice_lines, entities, customers
- PDF-parser med autodeteksjon (pdfplumber for digitale PDF-er, Tesseract for skannet materiale)
- Endepunkter: `POST /api/v1/invoices/upload`, `GET /api/v1/invoices`, `GET /api/v1/invoices/{id}`, `GET /api/v1/health`
- Frontend-skjelett: Vite + React + TypeScript + Tailwind + TanStack Query
- pytest-oppsett med async testdatabase
