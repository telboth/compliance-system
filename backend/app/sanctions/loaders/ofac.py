"""Parser for OFAC CSV feeds."""

from __future__ import annotations

import csv
import io


def parse_ofac_count(payload: bytes) -> int:
    """Returner antall datarader i OFAC CSV."""
    text = payload.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return 0
    # Trekk fra header.
    return max(0, len(rows) - 1)
