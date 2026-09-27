"""Platform model access consumed by the runtime's Model Gateway adapter."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any


class ModelGatewayConfigurationError(RuntimeError):
    """Raised when the model gateway is not configured correctly."""


@lru_cache(maxsize=1)
def get_model() -> Any:
    """Return the configured PydanticAI model for structured generation."""

    endpoint = _required("MODEL_GATEWAY_ENDPOINT")
    model_name = _required("MODEL_GATEWAY_MODEL")
    api_key = os.getenv("MODEL_GATEWAY_API_KEY", "").strip()

    if not api_key:
        raise ModelGatewayConfigurationError(
            "MODEL_GATEWAY_API_KEY is required to call the model gateway"
        )

    model_class = _model_class()
    provider_class = _provider_class()

    return model_class(
        model_name,
        provider=provider_class(
            base_url=_base_url(endpoint),
            api_key=api_key,
        ),
    )


def _base_url(endpoint: str) -> str:
    """Reduce a chat-completions endpoint to the provider base URL."""

    value = endpoint.rstrip("/")
    for suffix in ("/chat/completions", "/completions", "/responses"):
        if value.endswith(suffix):
            return value[: -len(suffix)]
    return value


def _model_class() -> Any:
    try:
        from pydantic_ai.models import openai as openai_models
    except ModuleNotFoundError as exc:
        raise ModelGatewayConfigurationError(
            "pydantic-ai is required for model gateway execution"
        ) from exc

    # The class was renamed in pydantic-ai 1.x; both spellings are accepted.
    for name in ("OpenAIChatModel", "OpenAIModel"):
        model_class = getattr(openai_models, name, None)
        if model_class is not None:
            return model_class

    raise ModelGatewayConfigurationError(
        "pydantic_ai.models.openai exposes no supported model class"
    )


def _provider_class() -> Any:
    try:
        from pydantic_ai.providers.openai import OpenAIProvider
    except ModuleNotFoundError as exc:
        raise ModelGatewayConfigurationError(
            "pydantic-ai is required for model gateway execution"
        ) from exc
    return OpenAIProvider


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ModelGatewayConfigurationError(
            f"Required environment variable is missing: {name}"
        )
    return value
