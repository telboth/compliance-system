/**
 * App version — bump this string on every release.
 * Format: v<major>.<minor>.<patch>
 *
 * History:
 *   v0.8.1 — initial About page, i18n language switcher, install.ps1 -Update/-Help/-Stop
 *   v0.8.2 — DEKSA eksportkontroll (Vareliste I+II), catch-all sluttbruker-screening,
 *             KRI-fix (screened_at + GroupBy), samlet arbeidsliste med flagg-merkelapper
 *   v0.8.3 — CAS/synonym-matching mot DB-importert vareliste, månedlig auto-sjekk av
 *             DEKSA-lister og embargo, admin-UI for listesynkronisering (/list-admin),
 *             embargo-lista migrert fra hardkodet Python til DB med auto-oppdatering
 *   v0.8.4 — 49 kjemikalier seedet med ekte CAS-numre og synonymer (ML7 stridsmidler,
 *             1C002/1C011 metaller, 1C350/1C450 CWC-forløpere, 1C111/1C210 eksplosiver),
 *             utvidet keyword-leksikon for kategori 1 og ML7
 */
export const APP_VERSION = "v0.8.4";
