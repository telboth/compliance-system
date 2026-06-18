#!/usr/bin/env python3
"""Importer eksportkontroll-varelister (Vareliste I/II) til databasen.

Tre moduser:

  --seed
      Last inn kategori-baselinen fra den statiske referansen
      (app/data/export_control_reference.py). Gjør at referanse-UI,
      arbeidsliste og sync-status har innhold umiddelbart. Kjør denne først.

  --excel PATH [--version V] [--list II]
      Parse EU-kommisjonens offisielle Annex I-Excel (Vareliste II / dual-use)
      og last inn alle kontrollnumre. Excel-fila lastes ned manuelt fra
      EU/CIRCABC (den ligger ikke bak en stabil åpen URL):
        https://policy.trade.ec.europa.eu/help-exporters-and-importers/exporting-dual-use-items_en
      (Excel-fila er kun et hjelpeverktøy uten rettslig kraft — den
       autoritative kilden er forordningsteksten på EUR-Lex.)

  --csv PATH [--version V] [--list II]
      Parse en enkel CSV med kolonnene: item_code,title[,list_code][,regime].

Eksempler:
  docker compose exec api python scripts/import_export_control_list.py --seed
  docker compose exec api python scripts/import_export_control_list.py \
      --excel /data/eu_dual_use_annex_i_2024-09.xlsx --version EU-2021/821-2024-09

Idempotent: punkter med samme (kode, kilde-versjon) oppdateres, ikke dupliseres.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import re
import sys

sys.path.insert(0, "/app")

# Kontrollkode-mønster: ML1..ML22 eller dual-use [0-9][A-E][0-9]{3}(.underpunkt)
_CODE_RE = re.compile(r"^\s*(ML\s?\d{1,2}|[0-9][A-E]\d{3})([.\w]*)\s*$", re.IGNORECASE)


def _looks_like_code(text: str) -> bool:
    return bool(_CODE_RE.match(text.strip())) if text else False


def _classify_list_and_category(item_code: str) -> tuple[str, str, str | None]:
    """Utled (list_code, category, group) fra et kontrollnummer."""
    from app.data.export_control_reference import parse_control_code

    sm = parse_control_code(item_code)
    if sm is not None:
        return sm.list_code, sm.category, sm.group
    # Fallback: militært hvis starter med ML
    if item_code.upper().startswith("ML"):
        return "I", item_code.upper(), None
    return "II", item_code[:1], (item_code[1:2].upper() if len(item_code) > 1 else None)


def _parse_excel(path: str) -> list[dict]:
    """Parse EU Annex I-Excel robust: finn kontrollkode + beste tittel per rad."""
    try:
        import openpyxl
    except ImportError:
        print("FEIL: openpyxl er ikke installert.", file=sys.stderr)
        sys.exit(2)

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows_out: list[dict] = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if not cells:
                continue
            code_cell = next((c for c in cells if _looks_like_code(c)), None)
            if code_cell is None:
                continue
            # Tittel = lengste celle som ikke er selve koden
            title_candidates = [c for c in cells if c != code_cell]
            title = max(title_candidates, key=len) if title_candidates else None
            rows_out.append({"item_code": code_cell, "title": title})
    return rows_out


def _parse_csv(path: str) -> list[dict]:
    rows_out: list[dict] = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            code = (r.get("item_code") or r.get("code") or "").strip()
            if not code:
                continue
            rows_out.append(
                {
                    "item_code": code,
                    "title": (r.get("title") or r.get("description") or "").strip() or None,
                    "list_code": (r.get("list_code") or "").strip() or None,
                    "regime": (r.get("regime") or "").strip() or None,
                }
            )
    return rows_out


async def _load_rows(rows: list[dict], *, source_version: str, force_list: str | None) -> None:
    from app.core.database import get_session_factory
    from app.services import export_control_service as svc

    created = updated = 0
    async with get_session_factory()() as session:
        for r in rows:
            item_code = r["item_code"]
            list_code, category, group = _classify_list_and_category(item_code)
            if r.get("list_code"):
                list_code = r["list_code"]
            if force_list:
                list_code = force_list
            is_new = await svc.upsert_item(
                session,
                list_code=list_code,
                category=category,
                group=group,
                item_code=item_code,
                title=r.get("title"),
                regime=r.get("regime"),
                source_version=source_version,
            )
            created += int(is_new)
            updated += int(not is_new)
        await session.commit()
    print(f"Ferdig: {created} nye, {updated} oppdatert (kilde='{source_version}').")


async def _seed() -> None:
    from app.core.database import get_session_factory
    from app.services import export_control_service as svc

    async with get_session_factory()() as session:
        created = await svc.seed_reference_categories(session)
        await session.commit()
        total = await svc.count_items(session)
    print(f"Baseline seedet: {created} nye kategori-rader. Totalt {total} punkter i databasen.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Importer eksportkontroll-varelister")
    ap.add_argument("--seed", action="store_true", help="Last inn kategori-baseline")
    ap.add_argument("--excel", help="Sti til EU Annex I-Excel (.xlsx)")
    ap.add_argument("--csv", help="Sti til CSV (item_code,title[,list_code][,regime])")
    ap.add_argument("--version", default="EU-annex-i", help="Kilde-versjon for sporbarhet")
    ap.add_argument("--list", dest="force_list", choices=["I", "II"], help="Tving listekode")
    args = ap.parse_args()

    if args.seed:
        asyncio.run(_seed())
        return
    if args.excel:
        rows = _parse_excel(args.excel)
        print(f"Leste {len(rows)} kontrollnumre fra Excel.")
        asyncio.run(_load_rows(rows, source_version=args.version, force_list=args.force_list))
        return
    if args.csv:
        rows = _parse_csv(args.csv)
        print(f"Leste {len(rows)} rader fra CSV.")
        asyncio.run(_load_rows(rows, source_version=args.version, force_list=args.force_list))
        return
    ap.print_help()


if __name__ == "__main__":
    main()
