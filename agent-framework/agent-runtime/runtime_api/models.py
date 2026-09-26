"""Pydantic transport models for the persisted Runtime API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictApiModel(BaseModel):
    """Base model that rejects undeclared transport fields."""

    model_config = ConfigDict(extra="forbid")


class ChatRequest(StrictApiModel):
    """Start a new persisted agent conversation."""

    agent_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    user_id: str | None = None
    application_context: dict[str, Any] = Field(default_factory=dict)


class ResumeConversationRequest(StrictApiModel):
    """Resume a persisted conversation waiting for approval."""

    approved: bool
    selected_outlier_id: str | None = None
    comment: str | None = None
    expected_version: int | None = Field(default=None, ge=1)
    values: dict[str, Any] = Field(default_factory=dict)


class RuntimeResponseModel(BaseModel):
    """Application-facing persisted runtime response."""

    conversation_id: str
    agent_id: str
    status: str
    version: int
    result: dict[str, Any]
    approval_request: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    """Liveness response."""

    status: str


class ApiErrorDetail(BaseModel):
    """Machine-readable API error detail."""

    code: str
    message: str
    details: list[dict[str, Any]] | None = None


class ApiErrorResponse(BaseModel):
    """Common error response envelope."""

    error: ApiErrorDetail
