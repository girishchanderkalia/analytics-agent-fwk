"""Environment-backed settings for production runtime composition."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class RuntimeConfigurationError(ValueError):
    """Raised when required runtime configuration is invalid or missing."""


@dataclass(frozen=True)
class RuntimeSettings:
    """Validated production settings for the Application Agent Runtime."""

    repository_root: Path
    database_path: Path
    model_endpoint: str
    model_name: str
    model_api_key: str | None
    analytics_foundation_base_url: str
    analytics_foundation_operation_paths: Mapping[str, str]
    ca_bundle_path: Path | None
    request_timeout_seconds: float
    maximum_steps: int

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> "RuntimeSettings":
        """Read and validate runtime settings from environment variables."""

        env = dict(os.environ if environment is None else environment)

        repository_root = Path(
            _required(env, "AGENT_RUNTIME_REPOSITORY_ROOT")
        ).resolve()
        database_path = Path(
            _required(env, "AGENT_RUNTIME_DATABASE_PATH")
        ).resolve()

        ca_bundle_raw = env.get("AGENT_RUNTIME_CA_BUNDLE_PATH", "").strip()
        ca_bundle_path = Path(ca_bundle_raw).resolve() if ca_bundle_raw else None

        operation_paths = {
            "read_trends": _required(env, "AF_READ_TRENDS_PATH"),
            "read_wafers": _required(env, "AF_READ_WAFERS_PATH"),
            "create_workspace": _required(env, "AF_CREATE_WORKSPACE_PATH"),
            "apply_filters": _required(env, "AF_APPLY_FILTERS_PATH"),
            "register_dataset": _required(env, "AF_REGISTER_DATASET_PATH"),
            "get_registration": _required(env, "AF_GET_REGISTRATION_PATH"),
        }

        settings = cls(
            repository_root=repository_root,
            database_path=database_path,
            model_endpoint=_required(env, "MODEL_GATEWAY_ENDPOINT"),
            model_name=_required(env, "MODEL_GATEWAY_MODEL"),
            model_api_key=_optional(env, "MODEL_GATEWAY_API_KEY"),
            analytics_foundation_base_url=_required(
                env,
                "ANALYTICS_FOUNDATION_BASE_URL",
            ),
            analytics_foundation_operation_paths=operation_paths,
            ca_bundle_path=ca_bundle_path,
            request_timeout_seconds=_positive_float(
                env,
                "AGENT_RUNTIME_REQUEST_TIMEOUT_SECONDS",
                default=30.0,
            ),
            maximum_steps=_positive_int(
                env,
                "AGENT_RUNTIME_MAXIMUM_STEPS",
                default=100,
            ),
        )
        settings.validate_paths()
        return settings

    def validate_paths(self) -> None:
        """Validate local paths without creating deployment resources."""

        if not self.repository_root.is_dir():
            raise RuntimeConfigurationError(
                "Repository root does not exist: "
                f"{self.repository_root}"
            )

        if not (self.repository_root / "agents").is_dir():
            raise RuntimeConfigurationError(
                "Agent catalog does not exist under repository root"
            )

        if self.ca_bundle_path is not None and not self.ca_bundle_path.is_file():
            raise RuntimeConfigurationError(
                f"CA bundle does not exist: {self.ca_bundle_path}"
            )


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise RuntimeConfigurationError(
            f"Required environment variable is missing: {name}"
        )
    return value


def _optional(environment: Mapping[str, str], name: str) -> str | None:
    value = environment.get(name, "").strip()
    return value or None


def _positive_float(
    environment: Mapping[str, str],
    name: str,
    *,
    default: float,
) -> float:
    raw = environment.get(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeConfigurationError(
            f"{name} must be numeric"
        ) from exc
    if value <= 0:
        raise RuntimeConfigurationError(
            f"{name} must be greater than zero"
        )
    return value


def _positive_int(
    environment: Mapping[str, str],
    name: str,
    *,
    default: int,
) -> int:
    raw = environment.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeConfigurationError(
            f"{name} must be an integer"
        ) from exc
    if value <= 0:
        raise RuntimeConfigurationError(
            f"{name} must be greater than zero"
        )
    return value
