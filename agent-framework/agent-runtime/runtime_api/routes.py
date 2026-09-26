"""HTTP routes for persisted chat, resume, and conversation lookup."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from host.runtime_models import ChatCommand, ResumeCommand

from .dependencies import get_runtime_service
from .models import (
    ChatRequest,
    HealthResponse,
    ResumeConversationRequest,
    RuntimeResponseModel,
)
from .serialization import runtime_response


router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    """Return a minimal liveness response."""

    return HealthResponse(status="ok")


@router.post(
    "/v1/chat",
    response_model=RuntimeResponseModel,
    tags=["conversations"],
)
def start_chat(
    request: ChatRequest,
    service: Any = Depends(get_runtime_service),
) -> RuntimeResponseModel:
    """Start a persisted agent conversation."""

    response = service.start_chat(
        ChatCommand(
            agent_id=request.agent_id,
            message=request.message,
            user_id=request.user_id,
            application_context=request.application_context,
        )
    )

    return runtime_response(response)


@router.post(
    "/v1/conversations/{conversation_id}/resume",
    response_model=RuntimeResponseModel,
    tags=["conversations"],
)
def resume_conversation(
    conversation_id: str,
    request: ResumeConversationRequest,
    service: Any = Depends(get_runtime_service),
) -> RuntimeResponseModel:
    """Resume a persisted conversation without resubmitting workflow state."""

    response = service.resume(
        ResumeCommand(
            conversation_id=conversation_id,
            approved=request.approved,
            selected_outlier_id=request.selected_outlier_id,
            comment=request.comment,
            expected_version=request.expected_version,
            values=request.values,
        )
    )

    return runtime_response(response)


@router.get(
    "/v1/conversations/{conversation_id}",
    response_model=RuntimeResponseModel,
    tags=["conversations"],
)
def get_conversation(
    conversation_id: str,
    service: Any = Depends(get_runtime_service),
) -> RuntimeResponseModel:
    """Retrieve the latest durable conversation checkpoint."""

    return runtime_response(
        service.get_conversation(conversation_id)
    )
