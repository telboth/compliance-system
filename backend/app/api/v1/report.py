"""Compliance-rapport — HTML-rapport for utskrift/PDF-eksport.

Endepunkt: GET /invoices/{invoice_id}/report
Returnerer en selvstending HTML-side optimalisert for print-til-PDF.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import selectinload

from app.core.database import SessionDep
from app.models.invoice import Invoice, InvoiceStatus

router = APIRouter()

# ── HTML-template (inline) ────────────────────────────────────────────────────

_REPORT_CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 11pt; color: #111; background: #fff; }
  .page { max-width: 800px; margin: 0 auto; padding: 32px 40px; }
  h1 { font-size: 20pt; font-weight: 700; color: #1a1a2e; margin-bottom: 4px; }
  h2 { font-size: 12pt; font-weight: 600; color: #333; margin: 20px 0 8px; border-bottom: 1px solid #e0e0e0; padding-bottom: 4px; }
  h3 { font-size: 10pt; font-weight: 600; color: #444; margin: 10px 0 4px; }
  .subtitle { font-size: 9pt; color: #666; margin-bottom: 24px; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 9pt; font-weight: 700; }
  .badge-red    { background: #fee2e2; color: #b91c1c; }
  .badge-yellow { background: #fef9c3; color: #854d0e; }
  .badge-green  { background: #dcfce7; color: #166534; }
  .badge-gray   { background: #f3f4f6; color: #4b5563; }
  .badge-approved { background: #dcfce7; color: #166534; }
  .badge-blocked  { background: #fee2e2; color: #b91c1c; }
  dl.meta { display: grid; grid-template-columns: 180px 1fr; gap: 4px 16px; font-size: 10pt; }
  dl.meta dt { color: #666; }
  dl.meta dd { font-weight: 500; }
  table { width: 100%; border-collapse: collapse; font-size: 9pt; margin-top: 6px; }
  th { background: #f8f9fa; text-align: left; padding: 5px 8px; font-weight: 600; color: #555; border-bottom: 2px solid #ddd; }
  td { padding: 4px 8px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }
  tr:last-child td { border-bottom: none; }
  .hit-red    { color: #b91c1c; font-weight: 600; }
  .hit-yellow { color: #854d0e; font-weight: 600; }
  .section-box { border: 1px solid #e0e0e0; border-radius: 6px; padding: 12px 16px; margin-bottom: 12px; }
  .decision-box { border: 2px solid; border-radius: 6px; padding: 12px 16px; margin-bottom: 12px; }
  .decision-approved { border-color: #86efac; background: #f0fdf4; }
  .decision-blocked  { border-color: #fca5a5; background: #fef2f2; }
  .footer { margin-top: 32px; border-top: 1px solid #e0e0e0; padding-top: 12px; font-size: 8pt; color: #999; }
  .watermark { font-size: 8pt; color: #aaa; margin-bottom: 16px; }
  @media print {
    body { font-size: 10pt; }
    .page { padding: 0; }
    @page { margin: 20mm 15mm; }
  }
"""


def _score_badge(score: str | None) -> str:
    if score == "red":
        return '<span class="badge badge-red">🔴 RØD</span>'
    if score == "yellow":
        return '<span class="badge badge-yellow">🟡 GUL</span>'
    if score == "green":
        return '<span class="badge badge-green">🟢 GRØNN</span>'
    return '<span class="badge badge-gray">—</span>'


def _status_badge(status_val: str) -> str:
    if status_val == "approved":
        return '<span class="badge badge-approved">✓ Godkjent</span>'
    if status_val == "blocked":
        return '<span class="badge badge-blocked">🔒 Blokkert</span>'
    return f'<span class="badge badge-gray">{status_val}</span>'


def _esc(v: object) -> str:
    """Enkel HTML-escaping."""
    return str(v or "—").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt_date(d: date | None) -> str:
    if d is None:
        return "—"
    if isinstance(d, str):
        return d
    return d.strftime("%d.%m.%Y")


def _fmt_datetime(dt: object) -> str:
    if dt is None:
        return "—"
    try:
        from datetime import datetime
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        return dt.strftime("%d.%m.%Y %H:%M UTC")
    except Exception:
        return str(dt)


def build_report_html(invoice: Invoice) -> str:
    from datetime import datetime, timezone

    generated_at = datetime.now(tz=timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    score_val = invoice.compliance_score.value if invoice.compliance_score else None
    status_val = invoice.status.value

    # ── Metadata-seksjon ──────────────────────────────────────────────────────
    meta_rows = [
        ("Fakturanummer", _esc(invoice.invoice_number)),
        ("Retning", "Utgående" if invoice.direction.value == "outgoing" else "Innkommende"),
        ("Fakturadato", _fmt_date(invoice.invoice_date)),
        ("Beløp", f"{_esc(invoice.total_amount)} {_esc(invoice.currency)}" if invoice.total_amount else "—"),
        ("Destinasjonsland", _esc(invoice.destination_country)),
        ("Incoterms", _esc(invoice.incoterms)),
        ("Transportmåte", _esc(invoice.transport_mode)),
        ("PO-nummer", _esc(invoice.po_number)),
        ("Compliance-score", _score_badge(score_val)),
        ("Status", _status_badge(status_val)),
        ("Original filnavn", _esc(invoice.original_filename)),
        ("Lastet opp", _fmt_datetime(invoice.created_at)),
    ]
    meta_html = "\n".join(
        f"<dt>{label}</dt><dd>{val}</dd>" for label, val in meta_rows
    )

    # ── Parter ────────────────────────────────────────────────────────────────
    entities_html = ""
    if invoice.entities:
        rows = ""
        for e in invoice.entities:
            rows += (
                f"<tr><td>{_esc(e.name)}</td>"
                f"<td>{_esc(e.role.value if e.role else None)}</td>"
                f"<td>{_esc(e.entity_type.value if e.entity_type else None)}</td>"
                f"<td>{_esc(e.country)}</td>"
                f"<td>{_esc(e.email)}</td></tr>"
            )
        entities_html = f"""
        <h2>Parter og entiteter</h2>
        <table>
          <thead><tr><th>Navn</th><th>Rolle</th><th>Type</th><th>Land</th><th>E-post</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>"""
    else:
        entities_html = "<h2>Parter og entiteter</h2><p style='color:#888;font-size:9pt'>Ingen parter registrert.</p>"

    # ── Varelinjer ────────────────────────────────────────────────────────────
    lines_html = ""
    if invoice.lines:
        rows = ""
        for ln in invoice.lines:
            rows += (
                f"<tr><td>{_esc(ln.line_number)}</td>"
                f"<td>{_esc(ln.description)}</td>"
                f"<td>{_esc(ln.hs_code)}</td>"
                f"<td>{_esc(ln.eccn)}</td>"
                f"<td>{_esc(ln.quantity)} {_esc(ln.unit_of_measure)}</td>"
                f"<td>{_esc(ln.unit_price)}</td>"
                f"<td>{_esc(ln.total_price)} {_esc(ln.currency)}</td>"
                f"<td>{_esc(ln.country_of_origin)}</td></tr>"
            )
        lines_html = f"""
        <h2>Varelinjer</h2>
        <table>
          <thead><tr><th>#</th><th>Beskrivelse</th><th>HS-kode</th><th>ECCN</th>
          <th>Kvantum</th><th>Enhetspris</th><th>Totalpris</th><th>Opprinnelsesland</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>"""
    else:
        lines_html = "<h2>Varelinjer</h2><p style='color:#888;font-size:9pt'>Ingen varelinjer registrert.</p>"

    # ── Compliance-kommentar ──────────────────────────────────────────────────
    comments_html = ""
    if invoice.comments:
        comments_html = f"""
        <h2>LLM-analyse og compliance-notater</h2>
        <div class="section-box" style="font-size:9pt;white-space:pre-wrap">{_esc(invoice.comments)}</div>"""

    if invoice.instructions:
        comments_html += f"""
        <h2>Instruksjoner fra dokumentet</h2>
        <div class="section-box" style="font-size:9pt;white-space:pre-wrap">{_esc(invoice.instructions)}</div>"""

    # ── Review-beslutning ─────────────────────────────────────────────────────
    decision_html = ""
    if invoice.review_decision:
        is_approved = invoice.review_decision == "approved"
        decision_html = f"""
        <h2>Manuell review-beslutning</h2>
        <div class="decision-box {'decision-approved' if is_approved else 'decision-blocked'}">
          <p style="font-weight:700;font-size:12pt">
            {'✓ Godkjent' if is_approved else '🔒 Blokkert'}
          </p>
          <dl class="meta" style="margin-top:8px">
            <dt>Besluttet av</dt><dd>{_esc(invoice.reviewed_by)}</dd>
            <dt>Tidspunkt</dt><dd>{_fmt_datetime(invoice.reviewed_at)}</dd>
            <dt>Begrunnelse</dt><dd>{_esc(invoice.review_reason)}</dd>
          </dl>
        </div>"""
    else:
        decision_html = """
        <h2>Manuell review-beslutning</h2>
        <div class="section-box" style="color:#888;font-size:9pt">Ingen beslutning fattet ennå.</div>"""

    # ── Avslutt ───────────────────────────────────────────────────────────────
    title = _esc(invoice.original_filename or invoice.invoice_number or str(invoice.id))

    return f"""<!DOCTYPE html>
<html lang="no">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Compliance-rapport — {title}</title>
  <style>{_REPORT_CSS}</style>
</head>
<body>
  <div class="page">
    <p class="watermark">XLENT Compliance System — konfidensielt dokument</p>
    <h1>{title}</h1>
    <p class="subtitle">
      Compliance-rapport generert {generated_at} &nbsp;|&nbsp;
      Invoice-ID: {invoice.id}
    </p>

    <h2>Fakturainformasjon</h2>
    <dl class="meta">{meta_html}</dl>

    {entities_html}
    {lines_html}
    {comments_html}
    {decision_html}

    <div class="footer">
      Rapport generert av XLENT Compliance System {generated_at}.
      Dette dokumentet er ment som intern dokumentasjon og skal ikke deles med uautoriserte parter.
      Invoice-ID: {invoice.id}
    </div>
  </div>
</body>
</html>"""


# ── Endepunkt ─────────────────────────────────────────────────────────────────

REPORTABLE_STATUSES = {
    InvoiceStatus.SCREENED,
    InvoiceStatus.APPROVED,
    InvoiceStatus.BLOCKED,
    InvoiceStatus.REVIEWED,
}


@router.get(
    "/{invoice_id}/report",
    response_class=HTMLResponse,
    summary="Generer HTML compliance-rapport for utskrift/PDF",
)
async def get_invoice_report(
    invoice_id: uuid.UUID,
    session: SessionDep,
) -> HTMLResponse:
    """Returnerer en selvstending HTML-side optimalisert for print-til-PDF.

    Åpne i ny fane og bruk nettleserens utskriftsdialog for å lagre som PDF.
    Kun tilgjengelig for fakturaer med status screened, approved eller blocked.
    """
    from sqlalchemy import select

    stmt = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(
            selectinload(Invoice.entities),
            selectinload(Invoice.lines),
        )
    )
    result = await session.execute(stmt)
    invoice = result.scalar_one_or_none()

    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice ikke funnet")

    if invoice.status not in REPORTABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Rapport er kun tilgjengelig for screened/approved/blocked-fakturaer. "
                   f"Nåværende status: {invoice.status.value}",
        )

    html = build_report_html(invoice)
    return HTMLResponse(content=html, status_code=200)
