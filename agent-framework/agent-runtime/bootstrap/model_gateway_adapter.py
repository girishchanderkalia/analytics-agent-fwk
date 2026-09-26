"""Execution-model gateway backed by the platform Model Gateway."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import Any


AgentFactory = Callable[..., Any]


class ModelGatewayError(RuntimeError):
    """Base error raised by the fixed Model Gateway adapter."""


class ModelGatewayBootstrapError(ModelGatewayError):
    """Raised when the platform Model Gateway cannot be loaded."""


class ModelGatewayResponseError(ModelGatewayError):
    """Raised when the hosted model invocation fails."""


class PlatformModelGateway:
    """Adapt the fixed platform model to the Workflow Engine interface."""

    def __init__(
        self,
        model: Any | None = None,
        agent_factory: AgentFactory | None = None,
    ) -> None:
        self.model = (
            model
            if model is not None
            else _load_platform_model()
        )

        self.agent_factory = (
            agent_factory
            if agent_factory is not None
            else _default_agent_factory
        )

    def invoke_structured(
        self,
        system_prompt: str,
        input_text: str,
        output_contract: type[Any],
    ) -> Any:
        """Run one typed request and return its validated output."""

        agent = self.agent_factory(
            model=self.model,
            output_type=output_contract,
            system_prompt=system_prompt,
        )

        try:
            result = agent.run_sync(
                input_text
            )
        except Exception as exc:
            raise ModelGatewayResponseError(
                "The hosted model invocation failed"
            ) from exc

        output = result.output

        if hasattr(output, "model_dump"):
            return output.model_dump(
                mode="python"
            )

        return output


def create_model_gateway() -> PlatformModelGateway:
    """Create the framework-owned Model Gateway adapter."""

    return PlatformModelGateway(
        model=_load_platform_model()
    )


def _load_platform_model() -> Any:
    """Load the existing platform model lazily."""

    try:
        module = import_module(
            "foundation.model_gateway"
        )
    except ModuleNotFoundError as exc:
        raise ModelGatewayBootstrapError(
            "Cannot import foundation.model_gateway. "
            "Ensure the repository root and agent-runtime "
            "are available on PYTHONPATH."
        ) from exc

    get_model = getattr(
        module,
        "get_model",
        None,
    )

    if not callable(get_model):
        raise ModelGatewayBootstrapError(
            "foundation.model_gateway must expose "
            "a callable get_model()"
        )

    try:
        return get_model()
    except Exception as exc:
        raise ModelGatewayBootstrapError(
            "The platform model could not be created"
        ) from exc


def _default_agent_factory(
    **kwargs: Any,
) -> Any:
    """Create a PydanticAI Agent lazily."""

    try:
        module = import_module(
            "pydantic_ai"
        )
    except ModuleNotFoundError as exc:
        raise ModelGatewayBootstrapError(
            "pydantic-ai is required for hosted "
            "Model Gateway execution"
        ) from exc

    agent_class = getattr(
        module,
        "Agent",
        None,
    )

    if agent_class is None:
        raise ModelGatewayBootstrapError(
            "pydantic_ai must expose Agent"
        )

    try:
        return agent_class(**kwargs)
    except Exception as exc:
        raise ModelGatewayBootstrapError(
            "The typed model agent could not be created"
        ) from exc