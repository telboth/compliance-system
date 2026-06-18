# Deploy- og driftsdokumentasjon

Detaljeres ut etter Sprint 6 (hardening). Dette er målbildet for produksjon, mens dagens repo inneholder `docker-compose.yml` for lokal utvikling:

## Lokal utvikling

Se `README.md` for kjapp start.

## Produksjon (planlagt MVP-oppsett)

- Én Azure VM eller AWS EC2-instans
- Docker Compose med `docker-compose.prod.yml` (kommer i Sprint 6)
- Nginx reverse proxy med TLS-terminering (Let's Encrypt)
- Daglige PostgreSQL-backups til Azure Blob / S3
- Health checks via `/api/v1/health`
- Logger samles inn via Docker logging driver

## Skalering

MVP er bygget for én kunde per instans. Multi-tenant kommer i fase 3.
