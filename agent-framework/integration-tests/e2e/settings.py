from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    foundation_url: str
    foundation_mcp_url: str
    runtime_url: str
    bff_url: str
    application_id: str
    agent_id: str
    agent_version: str | None
    request_timeout_seconds: float
    run_agent_e2e: bool

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            foundation_url=_url("FOUNDATION_URL", "http://localhost:8200"),
            foundation_mcp_url=_url(
                "FOUNDATION_MCP_URL",
                "http://localhost:8100",
            ),
            runtime_url=_url("RUNTIME_URL", "http://localhost:8000"),
            bff_url=_url("BFF_URL", "http://localhost:8080"),
            application_id=os.getenv("OPO_APPLICATION_ID", "opo-monitoring"),
            agent_id=os.getenv("OPO_AGENT_ID", "opo-monitoring-agent"),
            agent_version=_optional("OPO_AGENT_VERSION"),
            request_timeout_seconds=float(
                os.getenv("E2E_REQUEST_TIMEOUT_SECONDS", "30")
            ),
            run_agent_e2e=_boolean("RUN_AGENT_E2E", False),
        )


def _url(name: str, default: str) -> str:
    value = os.getenv(name, default).strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        raise ValueError(f"{name} must be an HTTP URL")
    return value


def _optional(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None


def _boolean(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
