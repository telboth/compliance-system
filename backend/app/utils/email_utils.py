"""Delte hjelpefunksjoner for e-postadresse-håndtering."""

from __future__ import annotations

import re

# Felles mønster for RFC-5321-lignende e-postadresser.
# Brukes av invoice_note_service, invoice_search_service og screening_service
# slik at alle moduler finner de samme adressene.
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def extract_emails(text: str) -> list[str]:
    """Returner alle unike e-postadresser funnet i `text` (lowercase)."""
    return [m.group(0).lower() for m in EMAIL_RE.finditer(text)]
