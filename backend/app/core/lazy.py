"""
Mønster for lazy imports av tunge pakker.

Tunge avhengigheter (docling, anthropic, openai, celery) lastes IKKE ved
modulnivå — det gjør applikasjonen treg å starte og laster ressurser som
kanskje aldri brukes (f.eks. Docling-modeller på en maskin som kun kjører
sanksjonsscreening).

Bruk dette mønsteret i alle moduler som importerer slike pakker:

    # Øverst i filen — kun lette standard-library/pydantic-imports
    from __future__ import annotations
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        # Brukes kun av type-checker, lastes aldri ved kjøretid
        from docling.document_converter import DocumentConverter

    # Inne i funksjonen som faktisk trenger pakken:
    def build_converter() -> "DocumentConverter":
        from docling.document_converter import DocumentConverter  # lazy
        return DocumentConverter()

Lazy singleton-mønster (for objekter som er dyre å opprette):

    _instance: SomeHeavyClass | None = None

    def get_instance() -> SomeHeavyClass:
        global _instance
        if _instance is None:
            from heavy_package import SomeHeavyClass  # lazy
            _instance = SomeHeavyClass()
        return _instance

Moduler som skal følge dette mønsteret:
  - app/parsers/docling_parser.py   (docling)
  - app/llm/claude.py               (anthropic)   — Sprint 2
  - app/llm/openai_client.py        (openai)      — Sprint 2
  - app/tasks/celery_app.py         (celery)      — Sprint 2
"""
