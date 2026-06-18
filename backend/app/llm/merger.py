"""
Merger — kombinerer LLM-ekstraksjon og heuristiske funn.

Prinsipp:
  LLM gir kontekstuell forståelse (hvilket felt tilhører hvilken entitet).
  Heuristikk gir recall (finner verdier LLM mista pga. rar Markdown).

Merge-regler (i prioritert rekkefølge):
  1. LLM fant verdi med konfidens ≥ terskel → behold, ignorer heuristikk
  2. LLM fant verdi, konfidens < terskel, heuristikk BEKREFTER → boost til 0.85
  3. LLM fant verdi, konfidens < terskel, heuristikk AVVIKER → behold LLM, logg avvik
  4. LLM fant INGENTING, heuristikk fant noe → fyll inn med konfidens 0.75
     (bevisst under terskelen → flagges automatisk til manuell review)
  5. Duplikat verdi → behold én, logg i kommentar

Konfidens 0.75 for heuristikk-only er ærlig: vi fant verdien via
mønstergjenkjenning, ikke via kontekstuell forståelse.

Entitets-deduplisering:
  Etter alle heuristikk-passes kjøres automatisk navne-basert deduplisering
  av entiteter. To roller anses som funksjonelt ekvivalente:
    consignor ↔ seller  (avsender = selger i direktehandel)
    consignee ↔ buyer   (mottaker = kjøper i direktehandel)
  Har to entiteter med ekvivalente roller likt navn, slås de sammen til én.
  Den kommersielle rollen (seller / buyer) vinner.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from app.core.logging import get_logger
from app.llm.extraction import ExtractedEntity, FieldValue, InvoiceExtractionResult
from app.llm.heuristics import HeuristicResult

logger = get_logger(__name__)

# Konfidens tildelt heuristikk-only funn — bevisst under standard terskel (0.8)
# slik at feltet flagges for manuell review.
_HEURISTIC_CONFIDENCE = 0.75

# Konfidens brukt når heuristikk bekrefter et svakt LLM-felt.
_BOOSTED_CONFIDENCE = 0.85

# Antall tegn rundt epostadresse vi ser på for å finne nærmeste entitet.
_EMAIL_PROXIMITY_WINDOW = 400

# ── Entitets-deduplisering — konstanter ───────────────────────────────────────

# Roller som anses som funksjonelt ekvivalente (consignor = avsender/selger,
# consignee = mottaker/kjøper). Begge rollene i et par slås sammen dersom
# de tilhørende entitetene har tilstrekkelig likt navn.
_EQUIVALENT_ROLE_PAIRS: list[frozenset[str]] = [
    frozenset({"seller", "consignor"}),
    frozenset({"buyer", "consignee"}),
]

# Prioritet brukt til å velge "vinnende" rolle når to entiteter slås sammen.
# Høyere tall = prioritert. Kommersielle roller (seller/buyer) vinner over
# transportroller (consignor/consignee).
_ROLE_PRIORITY: dict[str, int] = {
    "seller": 10,
    "buyer": 10,
    "end_user": 8,
    "consignee": 6,
    "consignor": 6,
    "delivery_address": 4,
    "other": 1,
}

# Minimum tegn i korteste navn for at substring-match skal brukes.
# Hindrer at korte forkortelser som "AS" gir falske positiver.
_MIN_SUBSTR_LEN = 4

# ── Dato-fallback — konstanter ────────────────────────────────────────────────

# Konfidens for dato hentet fra filnavn — synlig under terskel → flagges for review.
_FILENAME_DATE_CONFIDENCE = 0.50

# Regex-mønstre brukt til å hente dato fra filnavn (prøves i rekkefølge).
# Gruppe 1, 2, 3 tolkes som enten (år,mnd,dag) eller (dag,mnd,år) avh. mønster.
_RE_DATE_ISO = re.compile(
    r"(\d{4})[-_](\d{1,2})[-_](\d{1,2})"  # 2024-03-15  /  2024_3_5
)
_RE_DATE_EU = re.compile(
    r"(\d{1,2})[._-](\d{1,2})[._-](\d{4})"  # 15.03.2024  /  15-3-2024
)
_RE_DATE_COMPACT = re.compile(
    r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)"  # 20240315
)


def merge(
    llm: InvoiceExtractionResult,
    heuristic: HeuristicResult,
    raw_text: str,
    threshold: float = 0.8,
    filename: str | None = None,
) -> InvoiceExtractionResult:
    """Flett heuristiske funn inn i LLM-resultatet og deduplisér entiteter.

    Muterer llm in-place og returnerer den. Eventuelle uattribuerte funn
    og utførte sammenslåinger legges til i llm.comments slik at de er
    synlige for reviewer.

    Args:
        llm:        Ekstraksjonresultat fra LLM-klienten.
        heuristic:  Funn fra HeuristicExtractor.
        raw_text:   Rå Markdown-tekst fra Docling — brukes til nærhetssøk.
        threshold:  Konfidensterskelen fra Settings.
        filename:   Originalt filnavn (f.eks. «invoice_2024-03-15.pdf»).
                    Brukes til dato-fallback hvis LLM ikke fant fakturadato.
    """
    notes: list[str] = []

    if not heuristic.is_empty():
        _merge_entity_hints(llm, heuristic, notes)
        _merge_emails(llm, heuristic, raw_text, notes)
        _merge_line_field(llm, heuristic.hs_codes, "hs_code", "HS-kode", notes, threshold)
        _merge_line_field(llm, heuristic.eccn_codes, "eccn", "ECCN", notes, threshold)
        _merge_line_field(llm, heuristic.serial_numbers, "serial_number", "serienummer", notes, threshold)
        _propagate_currency(llm, heuristic)
        _merge_po_number(llm, heuristic, notes)

    # Dato-fallback: filnavn (kjøres alltid — dagens dato brukes IKKE som fallback)
    _apply_date_fallback(llm, filename, notes)

    # Entitets-deduplisering: consignor/seller, consignee/buyer (kjøres alltid)
    _deduplicate_entities(llm, notes)

    # Fjern tomme eller plassholderentiteter som LLM returnerte uten navn
    _filter_empty_entities(llm, notes)

    if notes:
        addition = f"Auto: {' | '.join(notes)}"
        llm.comments = f"{llm.comments}\n{addition}".strip() if llm.comments else addition
        logger.debug("merge_notes", count=len(notes), notes=notes)

    return llm


# ── Entity-hint-merge (Consignee/Consignor) ───────────────────────────────────


def _merge_entity_hints(
    llm: InvoiceExtractionResult,
    heuristic: HeuristicResult,
    notes: list[str],
) -> None:
    """Bruk Consignee/Consignor-hint til å validere og supplere LLM-entiteter.

    Hvis LLM allerede har en entitet med riktig rolle → behold (LLM har kontekst).
    Hvis rollen mangler → legg til entiteten med heuristisk konfidens.
    """
    if not heuristic.entity_hints:
        return

    for hint_name, hint_role in heuristic.entity_hints:
        # Sjekk om LLM allerede har en entitet med denne rollen
        existing = [e for e in llm.entities if e.role == hint_role]

        if existing:
            # LLM har rollen — sjekk om noen av dem matcher hint-navnet
            names_match = any(
                hint_name.lower() in e.name.lower() or e.name.lower() in hint_name.lower() for e in existing
            )
            if not names_match and existing[0].confidence < _BOOSTED_CONFIDENCE:
                # LLM fant en entitet med denne rollen, men navnene avviker — logg
                notes.append(
                    f"Consignee/Consignor-hint «{hint_name}» ({hint_role}) avviker fra LLM-entitet «{existing[0].name}»"
                )
        else:
            # LLM mangler denne rollen helt — legg til fra heuristikk
            llm.entities.append(
                ExtractedEntity(
                    name=hint_name,
                    role=hint_role,
                    entity_type="company",
                    confidence=_HEURISTIC_CONFIDENCE,
                )
            )
            logger.debug(
                "heuristic_entity_added",
                name=hint_name,
                role=hint_role,
            )


# ── Epost-merge ───────────────────────────────────────────────────────────────


def _merge_emails(
    llm: InvoiceExtractionResult,
    heuristic: HeuristicResult,
    raw_text: str,
    notes: list[str],
) -> None:
    """Attribuer heuristiske epostadresser til entiteter eller logg dem."""
    if not heuristic.emails:
        return

    # Normaliser alle epost-adresser LLM allerede har satt
    attributed: set[str] = {e.email.lower() for e in llm.entities if e.email}

    unattributed = [e for e in heuristic.emails if e not in attributed]
    if not unattributed:
        return

    still_unattributed: list[str] = []

    for email in unattributed:
        entity = _find_nearest_entity(email, llm.entities, raw_text)
        if entity is not None and entity.email is None:
            entity.email = email
            logger.debug("heuristic_email_attributed", email=email, entity=entity.name)
        else:
            still_unattributed.append(email)

    if still_unattributed:
        notes.append(f"ukjent epost ikke tilordnet entitet: {', '.join(still_unattributed)}")


def _find_nearest_entity(
    email: str,
    entities: list[ExtractedEntity],
    text: str,
) -> ExtractedEntity | None:
    """Finn entiteten hvis navn ligger nærmest epostadressen i teksten.

    Søker innenfor et vindu på ±400 tegn rundt epostens posisjon og
    returnerer entiteten med kortest avstand til epostens posisjon.
    """
    email_pos = text.find(email)
    if email_pos == -1:
        return None

    window_start = max(0, email_pos - _EMAIL_PROXIMITY_WINDOW)
    window_end = min(len(text), email_pos + _EMAIL_PROXIMITY_WINDOW)
    window = text[window_start:window_end]

    best_entity: ExtractedEntity | None = None
    best_dist = float("inf")

    for entity in entities:
        if entity.name not in window:
            continue
        name_pos_in_window = window.find(entity.name)
        # Konverter tilbake til absolutt posisjon for sammenlignbar avstand
        name_abs = window_start + name_pos_in_window
        dist = abs(name_abs - email_pos)
        if dist < best_dist:
            best_dist = dist
            best_entity = entity

    return best_entity


# ── Linje-felt-merge (HS-kode, ECCN, serienummer) ────────────────────────────


def _normalize(value: str, field_name: str) -> str:
    """Normaliser en feltverdi for dedupliceringssammenligning."""
    v = value.upper().strip()
    if field_name == "hs_code":
        # 8517.12.00 == 85171200 — sammenlign uten punktum
        return v.replace(".", "")
    return v


def _merge_line_field(
    llm: InvoiceExtractionResult,
    heuristic_values: list[str],
    field_name: str,
    display_name: str,
    notes: list[str],
    threshold: float,
) -> None:
    """Flett heuristiske linje-feltverdier inn i LLM-linjer.

    Strategier (i prioritert rekkefølge):
      A. Heuristikk bekrefter svakt LLM-felt → boost konfidens
      B. 1 heuristisk verdi, N linjer uten felt → sett på alle
      C. N verdier == N linjer uten felt → parvis tilordning etter rekkefølge
      D. Tvetydighet → logg i kommentar
    """
    if not heuristic_values:
        return

    if not llm.lines:
        notes.append(f"fant {display_name} via heuristikk men ingen linjer å tilordne: {', '.join(heuristic_values)}")
        return

    # Normaliser heuristiske verdier for sammenligning
    h_normalized = [_normalize(v, field_name) for v in heuristic_values]

    # ── Strategi A: bekreft/boost svake LLM-felt ──────────────────────────
    for line in llm.lines:
        llm_val = getattr(line, field_name)
        if llm_val is None:
            continue
        llm_norm = _normalize(llm_val, field_name)
        if llm_norm in h_normalized and line.confidence < threshold:
            line.confidence = _BOOSTED_CONFIDENCE
            logger.debug(
                "heuristic_boosted_confidence",
                field=field_name,
                value=llm_val,
                new_confidence=_BOOSTED_CONFIDENCE,
            )

    # Finn heuristiske verdier IKKE allerede i LLM-linjer
    attributed_norms = {
        _normalize(getattr(line, field_name), field_name) for line in llm.lines if getattr(line, field_name) is not None
    }
    unattributed = [
        (orig, norm) for orig, norm in zip(heuristic_values, h_normalized, strict=False) if norm not in attributed_norms
    ]

    if not unattributed:
        return

    lines_without = [line for line in llm.lines if getattr(line, field_name) is None]

    if not lines_without:
        # Alle linjer har allerede feltet — heuristikk fant noe ekstra
        extra = [v for v, _ in unattributed]
        notes.append(f"ekstra {display_name} ikke tilordnet noen linje: {', '.join(extra)}")
        return

    # ── Strategi B: én verdi → sett på alle linjer uten feltet ───────────
    if len(unattributed) == 1:
        value = unattributed[0][0]
        for line in lines_without:
            setattr(line, field_name, value)
            if line.confidence < _HEURISTIC_CONFIDENCE:
                line.confidence = _HEURISTIC_CONFIDENCE
        logger.debug(
            "heuristic_fill_single",
            field=field_name,
            value=value,
            line_count=len(lines_without),
        )
        return

    # ── Strategi C: N verdier == N linjer → parvis tilordning ────────────
    if len(unattributed) == len(lines_without):
        for line, (value, _) in zip(lines_without, unattributed, strict=False):
            setattr(line, field_name, value)
            if line.confidence < _HEURISTIC_CONFIDENCE:
                line.confidence = _HEURISTIC_CONFIDENCE
        logger.debug(
            "heuristic_fill_paired",
            field=field_name,
            count=len(unattributed),
        )
        return

    # ── Strategi D: tvetydighet — logg ───────────────────────────────────
    notes.append(
        f"{len(unattributed)} {display_name}-verdier kunne ikke tilordnes "
        f"{len(lines_without)} linje(r): {', '.join(v for v, _ in unattributed)}"
    )


# ── Valuta-propagering ────────────────────────────────────────────────────────


def _propagate_currency(
    llm: InvoiceExtractionResult,
    heuristic: HeuristicResult,
) -> None:
    """Fyll inn valuta på linjer som mangler den.

    Prioritet:
      1. LLM-ekstrahertet per-linje-valuta — behold (LLM leste kolonnehode)
      2. Dokument-valuta fra LLM (invoice.currency) — propagér til alle linjer uten valuta
      3. Valuta funnet via heuristikk — brukes hvis LLM-dokument-valuta mangler

    Kalles alltid, selv om heuristic.currency er None.
    """
    if not llm.lines:
        return

    # Finn beste dokument-valuta
    doc_currency: str | None = None
    if llm.currency.value:
        doc_currency = llm.currency.value.upper()[:3]
    elif heuristic.currency:
        doc_currency = heuristic.currency
        # Fyll inn manglende dokument-valuta på invoice-nivå også
        if not llm.currency.value:
            from app.llm.extraction import FieldValue

            llm.currency = FieldValue(value=doc_currency, confidence=_HEURISTIC_CONFIDENCE)
            logger.debug("heuristic_currency_set_on_invoice", currency=doc_currency)

    if not doc_currency:
        return

    filled = 0
    for line in llm.lines:
        if line.currency is None:
            line.currency = doc_currency
            filled += 1

    if filled:
        logger.debug(
            "currency_propagated_to_lines",
            currency=doc_currency,
            lines_filled=filled,
        )


# ── Entitets-deduplisering ────────────────────────────────────────────────────


def _names_similar(n1: str | None, n2: str | None) -> bool:
    """Returner True hvis navnene sannsynligvis peker på samme firma.

    Sjekker:
    - Eksakt match (case-insensitive)
    - Det korteste navnet finnes som delstreng i det lengste (minimum _MIN_SUBSTR_LEN tegn)

    «Minimum tegn»-sjekken hindrer at korte forkortelser («AS», «AB») gir
    falske positiver på tvers av ulike selskaper.
    """
    if not n1 or not n2:
        return False
    a = n1.lower().strip()
    b = n2.lower().strip()
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return len(shorter) >= _MIN_SUBSTR_LEN and shorter in longer


def _merge_two(primary: ExtractedEntity, secondary: ExtractedEntity) -> ExtractedEntity:
    """Slå sammen to entiteter — primary sin rolle og navn prioriteres.

    Feltene adresse, land, telefon og epost arves fra secondary dersom
    primary mangler dem (best-effort kombinasjon).
    """
    return ExtractedEntity(
        name=primary.name or secondary.name,
        role=primary.role,
        entity_type=primary.entity_type or secondary.entity_type,
        country=primary.country or secondary.country,
        address=primary.address or secondary.address,
        phone=primary.phone or secondary.phone,
        email=primary.email or secondary.email,
        confidence=max(primary.confidence, secondary.confidence),
    )


def _filter_empty_entities(
    llm: InvoiceExtractionResult,
    notes: list[str],
) -> None:
    """Fjern entiteter der LLM returnerte tomt navn eller plassholder-tekst.

    Eksempler på plassholdere LLM kan returnere:
      - tomt navn: ``""``
      - parentesform: ``"(Sender)"``, ``"(Receiver)"``, ``"(Unknown)"``
    """
    before = len(llm.entities)
    llm.entities = [
        e
        for e in llm.entities
        if e.name and e.name.strip() and not (e.name.strip().startswith("(") and e.name.strip().endswith(")"))
    ]
    removed = before - len(llm.entities)
    if removed:
        notes.append(f"fjernet {removed} tom(me)/plassholder-entitet(er)")
        logger.debug("entities_filtered", removed=removed)


def _deduplicate_entities(
    llm: InvoiceExtractionResult,
    notes: list[str],
) -> None:
    """Slå sammen dupliserte entiteter in-place på llm.entities.

    To regler (begge krever navne-likhet):

    1. Samme rolle, likt navn → behold den med høyest konfidens.
    2. Ekvivalent rolle (consignor↔seller, consignee↔buyer), likt navn →
       slå sammen; kommersielle roller (seller/buyer) vinner over transport-
       roller (consignor/consignee).

    Algoritmen gjentas til ingen flere sammenslåinger er mulig (fixed-point).
    """
    if len(llm.entities) <= 1:
        return

    entities = list(llm.entities)
    merged_log: list[str] = []
    changed = True

    while changed:
        changed = False
        n = len(entities)
        for i in range(n):
            for j in range(i + 1, n):
                e1, e2 = entities[i], entities[j]

                same_role = e1.role == e2.role
                equiv_role = any(e1.role in pair and e2.role in pair for pair in _EQUIVALENT_ROLE_PAIRS)

                if not (same_role or equiv_role):
                    continue
                if not _names_similar(e1.name, e2.name):
                    continue

                # Bestem primær entitet: høyest rolle-prioritet, deretter høyest konfidens
                p1 = _ROLE_PRIORITY.get(e1.role, 0)
                p2 = _ROLE_PRIORITY.get(e2.role, 0)
                if (p1, e1.confidence) >= (p2, e2.confidence):
                    primary, secondary = e1, e2
                else:
                    primary, secondary = e2, e1

                merged = _merge_two(primary, secondary)
                merged_log.append(f"{secondary.role} «{secondary.name}» -> {primary.role} «{primary.name}»")
                logger.info(
                    "entity_deduplicated",
                    name=merged.name,
                    kept_role=merged.role,
                    removed_role=secondary.role,
                )

                # Erstatt de to med den sammenslåtte entiteten
                entities = [e for k, e in enumerate(entities) if k not in {i, j}]
                entities.append(merged)
                changed = True
                break  # start ny iterasjon med oppdatert liste
            if changed:
                break

    llm.entities = entities

    if merged_log:
        notes.append(f"entitetsmerging: {'; '.join(merged_log)}")


# ── PO-nummer-merge ───────────────────────────────────────────────────────────


def _merge_po_number(
    llm: InvoiceExtractionResult,
    heuristic: HeuristicResult,
    notes: list[str],
) -> None:
    """Fyll inn PO-nummer fra heuristikk hvis LLM ikke fant det.

    Bekreftelse: hvis LLM fant et svakt treff og heuristikk matcher
    (case-insensitive), boostes konfidensen til _BOOSTED_CONFIDENCE.
    """
    if not heuristic.po_number:
        return

    if llm.po_number.value:
        # LLM fant noe — sjekk om heuristikk bekrefter
        if (
            llm.po_number.confidence < _BOOSTED_CONFIDENCE
            and heuristic.po_number.upper() in llm.po_number.value.upper()
        ):
            llm.po_number.confidence = _BOOSTED_CONFIDENCE
            logger.debug(
                "heuristic_po_boosted",
                value=llm.po_number.value,
                new_confidence=_BOOSTED_CONFIDENCE,
            )
    else:
        # LLM fant ingenting — fyll inn fra heuristikk
        llm.po_number = FieldValue(
            value=heuristic.po_number,
            confidence=_HEURISTIC_CONFIDENCE,
        )
        notes.append(f"PO-nummer fra heuristikk: {heuristic.po_number}")
        logger.info("heuristic_po_number_set", value=heuristic.po_number)


# ── Dato-fallback ─────────────────────────────────────────────────────────────


def _extract_date_from_filename(filename: str) -> date | None:
    """Forsøk å ekstrahere en dato fra filnavnet.

    Prøver tre mønstre i prioritert rekkefølge:
      1. ISO med skilletegn:  2024-03-15  /  2024_3_5
      2. Europeisk format:    15.03.2024  /  15-3-2024
      3. Kompakt ISO:         20240315  (validerer mnd/dag i regex)
    """
    stem = Path(filename).stem  # fjern filtype

    for pattern, year_idx, month_idx, day_idx in [
        (_RE_DATE_ISO, 1, 2, 3),
        (_RE_DATE_EU, 3, 2, 1),
        (_RE_DATE_COMPACT, 1, 2, 3),
    ]:
        for m in pattern.finditer(stem):
            try:
                return date(int(m.group(year_idx)), int(m.group(month_idx)), int(m.group(day_idx)))
            except ValueError:
                continue  # ugyldig dato (f.eks. 31. februar) — prøv neste

    return None


def _apply_date_fallback(
    llm: InvoiceExtractionResult,
    filename: str | None,
    notes: list[str],
) -> None:
    """Fyll inn fakturadato hvis LLM ikke fant den.

    Fallback: dato fra filnavnet (konfidens 0.50 → flagges for manuell review).
    Dagens dato brukes IKKE som fallback — et tomt datofelt (confidence 0.0)
    er bedre enn en fabrikert dato som ser korrekt ut.
    """
    if llm.invoice_date.value:
        return  # LLM fant datoen — ingenting å gjøre

    # Forsøk: dato fra filnavn
    if filename:
        found = _extract_date_from_filename(filename)
        if found:
            llm.invoice_date = FieldValue(value=found.isoformat(), confidence=_FILENAME_DATE_CONFIDENCE)
            notes.append(f"fakturadato fra filnavn: {found.isoformat()}")
            logger.info("date_fallback_from_filename", filename=filename, date=found.isoformat())
            return

    # Ingen fallback funnet — la datoen stå som null (confidence 0.0).
    # Feltet vil da ikke påvirke den totale konfidensscoren og vil vises
    # som tomt for reviewer.
    logger.info("date_not_found_no_fallback", filename=filename)
