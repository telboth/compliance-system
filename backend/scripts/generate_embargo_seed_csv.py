"""Generer en seed-CSV for embargo-lista basert paa den statiske listen.

Bruk:
  python scripts/generate_embargo_seed_csv.py > embargo_seed.csv

CSV-en kan lastes opp til en webserver og peke paa med
PUT /api/v1/embargo/sync/url?url=<din-url>
"""

import csv
import sys

from app.sanctions.embargo import SEED_LIST

writer = csv.writer(sys.stdout)
writer.writerow(["iso2", "name", "sources", "scope", "note"])
for entry in SEED_LIST:
    writer.writerow(
        [
            entry.iso2,
            entry.name,
            ", ".join(entry.sources),
            entry.scope,
            entry.note,
        ]
    )
