from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from bootstrap.model_gateway_adapter import (
    ModelGatewayResponseError,
)

V3_ROOT = Path(__file__).resolve().parents[1]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"
if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME_ROOT))

from host.provider_mapping import (  # noqa: E402
    build_structured_request,
    parse_structured_response,
)
from host.runtime_context_factory import (  # noqa: E402
    ExecutionSecurityContext,
)
from host.settings import (  # noqa: E402
    RuntimeConfigurationError,
    RuntimeSettings,
)



def valid_environment(tmp_path: Path) -> dict[str, str]:
    repository = tmp_path / "repo"
    (repository / "agents").mkdir(parents=True)
    return {
        "AGENT_RUNTIME_REPOSITORY_ROOT": str(repository),
        "AGENT_RUNTIME_DATABASE_PATH": str(tmp_path / "runtime.sqlite"),
        "MODEL_GATEWAY_ENDPOINT": "https://model.invalid/invoke",
        "MODEL_GATEWAY_MODEL": "test-model",
        "MODEL_GATEWAY_API_KEY": "secret",
        "ANALYTICS_FOUNDATION_BASE_URL": "https://foundation.invalid",
        "AF_READ_TRENDS_PATH": "/query/trends",
        "AF_READ_WAFERS_PATH": "/query/wafers",
        "AF_CREATE_WORKSPACE_PATH": "/workspace/create",
        "AF_APPLY_FILTERS_PATH": "/workspace/filters",
        "AF_REGISTER_DATASET_PATH": "/workspace/register",
        "AF_GET_REGISTRATION_PATH": "/workspace/registration",
    }


def test_settings_load_from_environment(tmp_path: Path) -> None:
    settings = RuntimeSettings.from_environment(valid_environment(tmp_path))
    assert settings.model_name == "test-model"
    assert settings.maximum_steps == 100
    assert settings.analytics_foundation_operation_paths[
        "read_trends"
    ] == "/query/trends"


def test_missing_required_setting_is_rejected(tmp_path: Path) -> None:
    environment = valid_environment(tmp_path)
    del environment["MODEL_GATEWAY_ENDPOINT"]
    with pytest.raises(
        RuntimeConfigurationError,
        match="MODEL_GATEWAY_ENDPOINT",
    ):
        RuntimeSettings.from_environment(environment)


def test_invalid_numeric_setting_is_rejected(tmp_path: Path) -> None:
    environment = valid_environment(tmp_path)
    environment["AGENT_RUNTIME_MAXIMUM_STEPS"] = "zero"
    with pytest.raises(RuntimeConfigurationError, match="integer"):
        RuntimeSettings.from_environment(environment)


def test_structured_request_contains_schema() -> None:
    request = build_structured_request(
        model="test-model",
        system_prompt="system",
        input_text="input",
        output_schema={"type": "object"},
    )
    assert request["response_format"]["json_schema"]["schema"] == {
        "type": "object"
    }


def test_structured_response_supports_direct_output() -> None:
    assert parse_structured_response(
        {"structured_output": {"value": 1}}
    ) == {"value": 1}


def test_structured_response_supports_parsed_choice() -> None:
    response = {
        "choices": [{"message": {"parsed": {"value": 2}}}]
    }
    assert parse_structured_response(response) == {"value": 2}


def test_missing_structured_response_is_rejected() -> None:
    with pytest.raises(ModelGatewayResponseError):
        parse_structured_response({"choices": []})


def test_security_context_defaults_are_empty() -> None:
    security = ExecutionSecurityContext()
    assert security.permissions == frozenset()
    assert security.approved_capabilities == frozenset()
