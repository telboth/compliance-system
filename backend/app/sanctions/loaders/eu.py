"""Parser for EU Financial Sanctions XML."""

from __future__ import annotations

import xml.etree.ElementTree as ET


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def parse_eu_count(payload: bytes) -> int:
    """Returner antall entiteter i EU-listen."""
    root = ET.fromstring(payload)  # noqa: S314
    count = sum(1 for elem in root.iter() if _local_name(elem.tag).lower() == "sanctionentity")
    if count:
        return count

    # Fallback for alternative struktur.
    return sum(1 for elem in root.iter() if _local_name(elem.tag).lower() in {"entity", "person"})
