from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from existing_pipeline.exceptions import PipelineModuleMissingError

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for all API-raised errors. Carries an HTTP status and a
    stable machine-readable `code` so clients don't have to parse prose."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "APP_ERROR"

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class ValidationAppError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "VALIDATION_ERROR"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "AUTHENTICATION_ERROR"


class AuthorizationError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "AUTHORIZATION_ERROR"


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "RATE_LIMITED"


class PipelineNotImplementedError(AppError):
    """Raised when the request is engineering-valid but depends on a
    pipeline module that is currently a stub (see existing_pipeline/)."""
    status_code = status.HTTP_501_NOT_IMPLEMENTED
    code = "PIPELINE_MODULE_MISSING"


class MissingInputError(AppError):
    """Mirrors the original pipeline's MissingInputError so the API layer
    doesn't have to guess at defaults on its behalf (spec: never invent
    missing engineering inputs)."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "MISSING_INPUT"


def _envelope(code: str, message: str, details: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    return {"success": False, "error": {"code": code, "message": message, "details": details or {}}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content=_envelope(exc.code, exc.message, exc.details))

    @app.exception_handler(PipelineModuleMissingError)
    async def pipeline_missing_handler(request: Request, exc: PipelineModuleMissingError):
        return JSONResponse(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            content=_envelope("PIPELINE_MODULE_MISSING", str(exc)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope("VALIDATION_ERROR", "Request validation failed.", {"errors": exc.errors()}),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope("HTTP_ERROR", str(exc.detail)),
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        # Covers ValueErrors raised directly by the existing pipeline modules
        # (capacity.py, grouping.py, csv_loader.py, ...) -- surfaced as a
        # validation error rather than a 500, per spec section 35.
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope("VALIDATION_ERROR", str(exc)),
        )

    @app.exception_handler(FileNotFoundError)
    async def file_not_found_handler(request: Request, exc: FileNotFoundError):
        return JSONResponse(status_code=404, content=_envelope("NOT_FOUND", str(exc)))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope("INTERNAL_ERROR", "An unexpected error occurred."),
        )
