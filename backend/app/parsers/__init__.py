"""
Dokumentparsing for invoices via Docling — støtter PDF og XLSX.

`parse_document` er det eneste grensesnittet resten av applikasjonen bruker.
`parse_pdf` er et alias for bakoverkompatibilitet internt i Sprint 1.
"""

from app.parsers.models import ParsedDocument, ParserMethod, SourceFileType
from app.parsers.router import parse_document

# Alias brukt av invoice_service inntil det byttes i Sprint 2
parse_pdf = parse_document

__all__ = ["ParsedDocument", "ParserMethod", "SourceFileType", "parse_document", "parse_pdf"]
