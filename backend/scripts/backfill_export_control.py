#!/usr/bin/env python3
"""Backfill eksportkontroll-status for allerede screenede fakturaer.

Fakturaer screenet før eksportkontroll-funksjonen fantes har tom
``export_control_status``, og vises derfor ikke i arbeidslista. Dette
scriptet beregner status for dem.

Kjør:
  docker compose exec api python scripts/backfill_export_control.py
  docker compose exec api python scripts/backfill_export_control.py --no-rescore

Med ``--no-rescore`` settes kun export_control_status/summary, uten å røre
compliance_score. Standard eskalerer også score for fakturaer uten manuell
review-beslutning.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

sys.path.insert(0, "/app")


async def run(rescore: bool) -> None:
    from app.core.database import get_session_factory
    from app.services import export_control_service as svc

    async with get_session_factory()() as session:
        result = await svc.backfill_export_control(session, rescore=rescore)

    print(
        f"Ferdig: {result['processed']} fakturaer behandlet, "
        f"{result['flagged']} flagget, {result['rescored']} re-skåret."
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Backfill eksportkontroll-status")
    ap.add_argument(
        "--no-rescore",
        action="store_true",
        help="Ikke eskalér compliance_score, kun sett export_control_status",
    )
    args = ap.parse_args()
    asyncio.run(run(rescore=not args.no_rescore))


if __name__ == "__main__":
    main()
