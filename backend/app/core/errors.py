"""
Felles unntakshierarki og FastAPI-feilhåndterere.

Alle forretningsspesifikke unntak skal arve fra `ApplicationError` slik at
de kan oversettes konsistent til HTTP-svar. Resten lar vi FastAPI håndtere.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class ApplicationError(Exception):
    """Base for alle forretningsfeil. Skal aldri kastes direkte."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(ApplicationError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class ValidationError(ApplicationError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "VALIDATION_ERROR"


class UnsupportedFileTypeError(ValidationError):
    code = "UNSUPPORTED_FILE_TYPE"


class FileTooLargeError(ValidationError):
    code = "FILE_TOO_LARGE"


class ParsingError(ApplicationError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "PARSING_ERROR"


def register_exception_handlers(app: FastAPI) -> None:
    """Registrer feilhåndterere på FastAPI-app-en."""

    @app.exception_handler(ApplicationError)
    async def _application_error_handler(
        request: Request, exc: ApplicationError
    ) -> JSONResponse:
        logger.warning(
            "application_error",
            code=exc.code,
            message=exc.message,
            path=request.url.path,
            details=exc.details,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "detail": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled_error",
            path=request.url.path,
            exc_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": "INTERNAL_ERROR",
                "detail": "En uventet feil oppstod.",
            },
        )
