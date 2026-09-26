from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

V3_ROOT = Path(__file__).resolve().parents[1]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"
if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME_ROOT))

from bootstrap.model_gateway_adapter import (  # noqa: E402
    ModelGatewayBootstrapError,
    ModelGatewayResponseError,
    PlatformModelGateway,
    create_model_gateway,
)
from host.provider_mapping import (  # noqa: E402
    ModelGatewayResponseError as MappingGatewayError,
)


class FakeTransport:
    def request(self, **kwargs: Any) -> dict[str, Any]:
        return {"structured_output": {"value": 1}}


def test_error_identity_is_shared() -> None:
    assert MappingGatewayError is ModelGatewayResponseError

