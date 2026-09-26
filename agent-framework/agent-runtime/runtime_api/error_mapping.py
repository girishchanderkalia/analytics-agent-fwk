"""Translate persisted runtime exceptions to HTTP responses."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from host.runtime_models import (
    ConversationStateError,
    InvalidRuntimeCommandError,
    RuntimeServiceError,
)
from persistence.persistence_models import (
    ConversationConflictError,
    ConversationNotFoundError,
    ConversationStoreError,
    InvalidConversationError,
)

from .dependencies import RuntimeServiceUnavailableError


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    """Create the common API error envelope."""

    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }

    if details is not None:
        body["error"]["details"] = details

    return JSONResponse(status_code=status_code, content=body)


def install_error_handlers(app: FastAPI) -> None:
    """Register persisted Runtime API exception mappings."""

    @app.exception_handler(ConversationNotFoundError)
    async def conversation_not_found(
        request: Request,
        exc: ConversationNotFoundError,
    ) -> JSONResponse:
        del request
        return error_response(404, "conversation_not_found", str(exc))

    @app.exception_handler(ConversationConflictError)
    async def conversation_conflict(
        request: Request,
        exc: ConversationConflictError,
    ) -> JSONResponse:
        del request
        return error_response(409, "conversation_version_conflict", str(exc))

    @app.exception_handler(ConversationStateError)
    async def conversation_state(
        request: Request,
        exc: ConversationStateError,
    ) -> JSONResponse:
        del request
        return error_response(409, "conversation_state_conflict", str(exc))

    @app.exception_handler(InvalidRuntimeCommandError)
    async def invalid_command(
        request: Request,
        exc: InvalidRuntimeCommandError,
    ) -> JSONResponse:
        del request
        return error_response(422, "invalid_runtime_command", str(exc))

    @app.exception_handler(InvalidConversationError)
    async def invalid_conversation(
        request: Request,
        exc: InvalidConversationError,
    ) -> JSONResponse:
        del request
        return error_response(422, "invalid_conversation", str(exc))

    @app.exception_handler(RuntimeServiceUnavailableError)
    async def missing_service(
        request: Request,
        exc: RuntimeServiceUnavailableError,
    ) -> JSONResponse:
        del request
        return error_response(503, "runtime_service_unavailable", str(exc))

    @app.exception_handler(ConversationStoreError)
    async def store_error(
        request: Request,
        exc: ConversationStoreError,
    ) -> JSONResponse:
        del request
        return error_response(500, "conversation_store_error", str(exc))

    @app.exception_handler(RuntimeServiceError)
    async def runtime_error(
        request: Request,
        exc: RuntimeServiceError,
    ) -> JSONResponse:
        del request
        return error_response(500, "runtime_service_error", str(exc))

    @app.exception_handler(RequestValidationError)
    async def request_validation(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        del request
        details = [
            {
                "location": list(error.get("loc", ())),
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "validation_error"),
            }
            for error in exc.errors()
        ]
        return error_response(
            422,
            "request_validation_error",
            "The request payload is invalid",
            details,
        )
