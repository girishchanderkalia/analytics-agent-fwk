"""Tests for per-agent typed Contract Providers."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError


V3_ROOT = Path(__file__).resolve().parents[1]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"

if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME_ROOT))


from bootstrap.contract_provider import (  # noqa: E402
    ContractProviderCache,
    InvalidContractDefinitionError,
    UnknownContractError,
    create_contract_provider,
)


def bundle(
    agent_id: str = "opo-monitoring-agent",
    version: str = "1.0",
    models: dict | None = None,
):
    declared_models = models or {
        "TrendFilters": {
            "fields": {
                "lookback_days": {
                    "type": "optional_int",
                    "default": 30,
                },
                "lot_ids": {
                    "type": "string_list",
                    "default": [],
                },
            }
        },
        "DetectionScope": {
            "fields": {
                "mode": {
                    "type": "literal",
                    "values": ["baseline", "absolute"],
                    "default": "baseline",
                }
            }
        },
    }

    return SimpleNamespace(
        agent_id=agent_id,
        version=version,
        agent=SimpleNamespace(
            metadata={
                "id": agent_id,
                "version": version,
                "models": declared_models,
            }
        ),
    )


def test_provider_builds_contracts_from_resolved_bundle() -> None:
    provider = create_contract_provider(bundle())

    trend_filters = provider.get_contract("TrendFilters")
    value = trend_filters()

    assert value.lookback_days == 30
    assert value.lot_ids == []
    assert provider.list_contracts() == (
        "DetectionScope",
        "TrendFilters",
    )


def test_contract_validation_is_enforced() -> None:
    provider = create_contract_provider(bundle())
    detection_scope = provider.get_contract("DetectionScope")

    with pytest.raises(ValidationError):
        detection_scope(mode="unsupported")


def test_unknown_contract_is_rejected() -> None:
    provider = create_contract_provider(bundle())

    with pytest.raises(UnknownContractError, match="MissingContract"):
        provider.get_contract("MissingContract")


def test_cache_reuses_provider_for_same_agent_version() -> None:
    cache = ContractProviderCache()
    first_bundle = bundle()
    second_bundle = bundle()

    first = cache.get_or_create(first_bundle)
    second = cache.get_or_create(second_bundle)

    assert first is second


def test_cache_isolates_agent_versions() -> None:
    cache = ContractProviderCache()

    first = cache.get_or_create(bundle(version="1.0"))
    second = cache.get_or_create(bundle(version="2.0"))

    assert first is not second
    assert first.key.version == "1.0"
    assert second.key.version == "2.0"


def test_cache_invalidation_rebuilds_provider() -> None:
    cache = ContractProviderCache()
    resolved_bundle = bundle()

    first = cache.get_or_create(resolved_bundle)
    cache.invalidate(
        agent_id="opo-monitoring-agent",
        version="1.0",
    )
    second = cache.get_or_create(resolved_bundle)

    assert first is not second


def test_invalid_agent_models_are_rejected() -> None:
    invalid_bundle = bundle(models={"Broken": {"fields": []}})

    with pytest.raises(
        InvalidContractDefinitionError,
        match="fields must be a mapping",
    ):
        create_contract_provider(invalid_bundle)
