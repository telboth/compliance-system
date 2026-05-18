FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Docling trenger libGL (for OpenCV) og libglib. Ingen Tesseract — Docling
# håndterer OCR selv via EasyOCR som del av sin interne pipeline.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installer avhengigheter. Docling er stor (~1-2 GB med ML-modeller som lastes
# ned ved første kjøring). For å unngå nedlasting i hvert bygg, pre-fetches
# modellene nedenfor etter at pakken er installert.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e ".[dev]"

# Pre-fetch Doclings standard-modeller så de er klare ved oppstart.
# Hoppes over hvis SKIP_DOCLING_PREFETCH=1 (nyttig i CI for å spare tid).
ARG SKIP_DOCLING_PREFETCH=0
RUN if [ "$SKIP_DOCLING_PREFETCH" = "0" ]; then \
        python -c "from docling.document_converter import DocumentConverter; DocumentConverter()"; \
    fi

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
