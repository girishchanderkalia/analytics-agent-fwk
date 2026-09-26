"""Per-agent typed contract providers for declarative agent bundles."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Literal

from pydantic import Field, create_model


class ContractProviderError(ValueError):
    """Base error raised while building or resolving agent contracts."""


class UnknownContractError(ContractProviderError):
    """Raised when a workflow requests an undeclared contract."""


class InvalidContractDefinitionError(ContractProviderError):
    """Raised when an agent contract definition is invalid."""


@dataclass(frozen=True)
class AgentContractKey:
    """Stable cache key for one agent version."""

    agent_id: str
    version: str


class BundleContractProvider:
    """Provide Pydantic contracts built from one resolved agent bundle."""

    def __init__(self, bundle: Any) -> None:
        self.bundle = bundle
        self.key = _bundle_key(bundle)
        self._contracts = _build_contracts(bundle)

    def get_contract(self, contract_name: str) -> type[Any]:
        """Return one contract declared by this agent version."""

        if not isinstance(contract_name, str) or not contract_name.strip():
            raise UnknownContractError(
                "Contract name must be a non-empty string"
            )

        normalized_name = contract_name.strip()

        try:
            return self._contracts[normalized_name]
        except KeyError as exc:
            raise UnknownContractError(
                f"Agent {self.key.agent_id!r} version "
                f"{self.key.version!r} does not declare contract "
                f"{normalized_name!r}"
            ) from exc

    def list_contracts(self) -> tuple[str, ...]:
        """Return declared contract names in stable order."""

        return tuple(sorted(self._contracts))


class ContractProviderCache:
    """Cache one contract provider per agent ID and version."""

    def __init__(self) -> None:
        self._providers: dict[AgentContractKey, BundleContractProvider] = {}
        self._lock = RLock()

    def get_or_create(self, bundle: Any) -> BundleContractProvider:
        """Return the cached provider for a resolved bundle."""

        key = _bundle_key(bundle)

        with self._lock:
            provider = self._providers.get(key)

            if provider is None:
                provider = BundleContractProvider(bundle)
                self._providers[key] = provider

            return provider

    def invalidate(
        self,
        agent_id: str | None = None,
        version: str | None = None,
    ) -> None:
        """Invalidate all providers or providers matching the supplied key."""

        with self._lock:
            if agent_id is None and version is None:
                self._providers.clear()
                return

            keys = [
                key
                for key in self._providers
                if (agent_id is None or key.agent_id == agent_id)
                and (version is None or key.version == version)
            ]

            for key in keys:
                self._providers.pop(key, None)


def create_contract_provider(bundle: Any) -> BundleContractProvider:
    """Create an uncached provider for one resolved agent bundle."""

    return BundleContractProvider(bundle)


def _build_contracts(bundle: Any) -> dict[str, type[Any]]:
    models = _agent_metadata(bundle).get("models")

    if not isinstance(models, dict) or not models:
        raise InvalidContractDefinitionError(
            "Agent definition must declare a non-empty models mapping"
        )

    contracts: dict[str, type[Any]] = {}

    for contract_name, definition in models.items():
        if not isinstance(contract_name, str) or not contract_name.strip():
            raise InvalidContractDefinitionError(
                "Contract names must be non-empty strings"
            )

        if not isinstance(definition, dict):
            raise InvalidContractDefinitionError(
                f"Contract {contract_name!r} must be a mapping"
            )

        declared_fields = definition.get("fields")

        if not isinstance(declared_fields, dict):
            raise InvalidContractDefinitionError(
                f"Contract {contract_name!r} fields must be a mapping"
            )

        fields: dict[str, tuple[Any, Any]] = {}

        for field_name, field_definition in declared_fields.items():
            fields[field_name] = _build_field(
                contract_name,
                field_name,
                field_definition,
            )

        contracts[contract_name] = create_model(
            contract_name,
            **fields,
        )

    return contracts


def _build_field(
    contract_name: str,
    field_name: str,
    definition: Any,
) -> tuple[Any, Any]:
    if not isinstance(field_name, str) or not field_name.strip():
        raise InvalidContractDefinitionError(
            f"Contract {contract_name!r} contains an invalid field name"
        )

    if not isinstance(definition, dict):
        raise InvalidContractDefinitionError(
            f"Field {contract_name}.{field_name} must be a mapping"
        )

    annotation = _field_annotation(
        contract_name,
        field_name,
        definition,
    )

    default = definition.get("default", ...)

    if isinstance(default, list):
        default = list(default)

    return (
        annotation,
        Field(
            default=default,
            description=definition.get("description", ""),
        ),
    )


def _field_annotation(
    contract_name: str,
    field_name: str,
    definition: dict[str, Any],
) -> Any:
    field_type = definition.get("type")

    simple_types: dict[str, Any] = {
        "string": str,
        "string_list": list[str],
        "float": float,
        "int": int,
        "boolean": bool,
        "mapping": dict[str, Any],
        "any_list": list[Any],
        "optional_float": float | None,
        "optional_int": int | None,
        "optional_string": str | None,
        "optional_boolean": bool | None,
    }

    if field_type in simple_types:
        return simple_types[field_type]

    if field_type == "literal":
        values = definition.get("values")

        if not isinstance(values, list) or not values:
            raise InvalidContractDefinitionError(
                f"Literal field {contract_name}.{field_name} "
                "must declare values"
            )

        return Literal[tuple(values)]

    raise InvalidContractDefinitionError(
        f"Unsupported contract field type {field_type!r} for "
        f"{contract_name}.{field_name}"
    )


def _bundle_key(bundle: Any) -> AgentContractKey:
    agent_id = getattr(bundle, "agent_id", None)
    version = getattr(bundle, "version", None)

    metadata = _agent_metadata(bundle)
    agent_id = agent_id or metadata.get("id")
    version = version or metadata.get("version")

    if not isinstance(agent_id, str) or not agent_id.strip():
        raise InvalidContractDefinitionError(
            "Resolved agent bundle has no agent ID"
        )

    if not isinstance(version, str) or not version.strip():
        raise InvalidContractDefinitionError(
            "Resolved agent bundle has no version"
        )

    return AgentContractKey(agent_id.strip(), version.strip())


def _agent_metadata(bundle: Any) -> dict[str, Any]:
    agent_definition = getattr(bundle, "agent", None)
    metadata = getattr(agent_definition, "metadata", None)

    if not isinstance(metadata, dict):
        raise InvalidContractDefinitionError(
            "Resolved agent bundle has no agent metadata"
        )

    return metadata
