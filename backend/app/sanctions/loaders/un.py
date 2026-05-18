"""Parser for UN consolidated XML."""

from __future__ import annotations

import xml.etree.ElementTree as ET


def parse_un_count(payload: bytes) -> int:
    """Returner antall entiteter i UN-listen."""
    root = ET.fromstring(payload)  # noqa: S314
    individual = root.findall(".//INDIVIDUAL")
    entities = root.findall(".//ENTITY")
    if individual or entities:
        return len(individual) + len(entities)

    # Fallback dersom struktur avviker.
    names = root.findall(".//FIRST_NAME") + root.findall(".//NAME_ORIGINAL_SCRIPT")
    return len(names)
