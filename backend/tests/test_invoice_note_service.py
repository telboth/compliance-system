"""Tester for invoice_note_service — spesielt e-postdomene-merknader."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.invoice_note_service import derive_email_note


def _mock_invoice(
    raw_text: str = "", entity_emails: list[str | None] | None = None, entity_names: list[str] | None = None
) -> MagicMock:
    """Enkel mock av Invoice-objektet for isolert testing."""
    invoice = MagicMock()
    invoice.raw_text = raw_text

    entities = []
    for i, name in enumerate(entity_names or []):
        e = MagicMock()
        e.name = name
        e.email = (entity_emails or [])[i] if entity_emails and i < len(entity_emails) else None
        entities.append(e)
    invoice.entities = entities
    return invoice


# ---------------------------------------------------------------------------
# Logistikkdomener skal IKKE generere e-postmerknad-advarsel
# ---------------------------------------------------------------------------


class TestEmailNoteLogisticsWhitelist:
    def test_bollore_domain_does_not_warn(self) -> None:
        """bollore.com er logistikkselskap — skal ikke flagges som avvik."""
        invoice = _mock_invoice(
            raw_text="Contact: freight@bollore.com for shipment details.",
            entity_names=["Acme Corp", "BuyerAS"],
        )
        status, text = derive_email_note(invoice)
        assert status == "ok", f"bollore.com burde ikke gi advarsel, fikk: status={status!r}, tekst={text!r}"
        assert "bollore" not in text.lower()

    def test_dhl_domain_does_not_warn(self) -> None:
        invoice = _mock_invoice(
            raw_text="Tracking via tracking@dhl.com.",
            entity_names=["Seller AS"],
        )
        status, _ = derive_email_note(invoice)
        assert status == "ok"

    def test_maersk_domain_does_not_warn(self) -> None:
        invoice = _mock_invoice(
            raw_text="Booking: booking@maersk.com",
            entity_names=["ExportCo"],
        )
        status, _ = derive_email_note(invoice)
        assert status == "ok"

    def test_bring_domain_does_not_warn(self) -> None:
        invoice = _mock_invoice(
            raw_text="Levering via ordrer@bring.com",
            entity_names=["NordicSeller AS"],
        )
        status, _ = derive_email_note(invoice)
        assert status == "ok"

    def test_logistics_plus_entity_email_ok(self) -> None:
        """Logistikkdomene i raw_text + matchende entitets-e-post → OK.

        'selleras.com' matcher entitetsnavnet 'Selleras' (token-match),
        'fedex.com' er logistikkdomene og skal ikke gi avvik.
        """
        invoice = _mock_invoice(
            raw_text="Ship via info@fedex.com. Contact: ceo@selleras.com",
            entity_names=["Selleras"],
            entity_emails=["ceo@selleras.com"],
        )
        status, _ = derive_email_note(invoice)
        assert status == "ok"

    def test_multiple_logistics_domains_no_warn(self) -> None:
        """Flere logistikkdomener på samme faktura — ingen advarsel."""
        invoice = _mock_invoice(
            raw_text="DHL: info@dhl.com, Maersk: booking@maersk.com, DSV: ops@dsv.com",
            entity_names=["Seller AS", "Buyer Ltd"],
        )
        status, _ = derive_email_note(invoice)
        assert status == "ok"

    # -----------------------------------------------------------------------
    # Kontrollsaker — ikke-logistikk skal fortsatt varsle
    # -----------------------------------------------------------------------

    def test_unknown_domain_still_warns(self) -> None:
        """Et ukjent domene som ikke matcher entitetsnavn skal fortsatt gi advarsel."""
        invoice = _mock_invoice(
            raw_text="Contact: info@suspektfirma.ru",
            entity_names=["Seller AS"],
        )
        status, _ = derive_email_note(invoice)
        assert status == "warn"

    def test_free_mail_still_warns(self) -> None:
        """Gmail-adresse skal fortsatt gi advarsel."""
        invoice = _mock_invoice(
            raw_text="Faktura fra selger123@gmail.com",
            entity_names=["Seller AS"],
        )
        status, _ = derive_email_note(invoice)
        assert status in ("warn", "error")

    def test_no_emails_is_ok(self) -> None:
        invoice = _mock_invoice(raw_text="Ingen e-post her.", entity_names=["Acme"])
        status, text = derive_email_note(invoice)
        assert status == "ok"
        assert "ingen" in text.lower() or "no" in text.lower()
