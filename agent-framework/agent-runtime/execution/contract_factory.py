"""Generate Pydantic models from declarative agent contracts."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    create_model,
)
from pydantic.fields import FieldInfo

from .definition_loader import (
    AgentDefinitionBundle,
    AgentDefinitionError,
    load_agent_definition,
)


class ContractFactoryError(ValueError):
    """Raised when a declarative model contract is invalid."""


NONE_TYPE = type(None)


@dataclass(frozen=True)
class GeneratedContract:
    """Generated Pydantic contract and its source declaration."""

    name: str
    model: type[BaseModel]
    definition: dict[str, Any]

    def json_schema(self) -> dict[str, Any]:
        """Return the JSON Schema for the generated model."""

        return self.model.model_json_schema()


class ContractFactory:
    """Create typed Pydantic contracts from an agent definition."""

    def __init__(
        self,
        bundle: AgentDefinitionBundle,
    ) -> None:
        self.bundle = bundle
        self._contracts: dict[str, GeneratedContract] = {}

    @property
    def model_definitions(self) -> dict[str, Any]:
        """Return model declarations from agent-definition.md."""

        models = self.bundle.agent.metadata.get("models")

        if not isinstance(models, dict) or not models:
            raise ContractFactoryError(
                "Agent definition must declare at least one model"
            )

        return models

    def build_all(self) -> dict[str, type[BaseModel]]:
        """Generate all contracts declared by the agent."""

        generated: dict[str, type[BaseModel]] = {}

        for contract_name in self.model_definitions:
            generated[contract_name] = self.build(
                contract_name
            )

        return generated

    def build(
        self,
        contract_name: str,
    ) -> type[BaseModel]:
        """Generate one named contract."""

        existing = self._contracts.get(contract_name)

        if existing is not None:
            return existing.model

        model_definition = self.model_definitions.get(
            contract_name
        )

        if model_definition is None:
            raise ContractFactoryError(
                f"Unknown contract: {contract_name}"
            )

        if not isinstance(model_definition, dict):
            raise ContractFactoryError(
                f"Contract {contract_name!r} must be a mapping"
            )

        fields = model_definition.get("fields")

        if not isinstance(fields, dict) or not fields:
            raise ContractFactoryError(
                f"Contract {contract_name!r} must declare fields"
            )

        pydantic_fields: dict[
            str,
            tuple[Any, Any],
        ] = {}

        for field_name, field_definition in fields.items():
            pydantic_fields[field_name] = (
                self._build_field(
                    contract_name=contract_name,
                    field_name=field_name,
                    field_definition=field_definition,
                )
            )

        model_class = create_model(
            contract_name,
            __config__=ConfigDict(
                extra="forbid",
                validate_default=True,
            ),
            __module__=__name__,
            **pydantic_fields,
        )

        try:
            model_class()
        except ValidationError as exc:
            raise ContractFactoryError(
                f"Contract {contract_name!r} has invalid "
                f"default values: {exc}"
            ) from exc

        self._contracts[contract_name] = GeneratedContract(
            name=contract_name,
            model=model_class,
            definition=deepcopy(model_definition),
        )

        return model_class

    def get(
        self,
        contract_name: str,
    ) -> type[BaseModel]:
        """Return a generated contract, creating it if needed."""

        return self.build(contract_name)

    def describe(
        self,
        contract_name: str,
    ) -> GeneratedContract:
        """Return generated contract metadata."""

        self.build(contract_name)
        return self._contracts[contract_name]

    def schemas(self) -> dict[str, dict[str, Any]]:
        """Generate JSON Schema for every declared contract."""

        self.build_all()

        return {
            contract_name: generated.json_schema()
            for contract_name, generated
            in self._contracts.items()
        }

    def validate(
        self,
        contract_name: str,
        value: Any,
    ) -> BaseModel:
        """Validate a value using a generated contract."""

        model_class = self.get(contract_name)
        return model_class.model_validate(value)

    def _build_field(
        self,
        contract_name: str,
        field_name: str,
        field_definition: Any,
    ) -> tuple[Any, Any]:
        """Convert one field declaration into a Pydantic field."""

        location = (
            f"field {field_name!r} in contract "
            f"{contract_name!r}"
        )

        if not isinstance(field_definition, dict):
            raise ContractFactoryError(
                f"{location} must be a mapping"
            )

        field_type_name = field_definition.get("type")

        if not isinstance(field_type_name, str):
            raise ContractFactoryError(
                f"{location} must declare a string type"
            )

        annotation = self._resolve_annotation(
            field_type_name=field_type_name,
            field_definition=field_definition,
            location=location,
        )

        description = field_definition.get("description")

        if description is not None and not isinstance(
            description,
            str,
        ):
            raise ContractFactoryError(
                f"{location} description must be a string"
            )

        has_default = "default" in field_definition

        if not has_default:
            field_info = Field(
                default=...,
                description=description,
            )
            return annotation, field_info

        default = deepcopy(field_definition["default"])

        field_info = self._create_field_info(
            annotation=annotation,
            default=default,
            description=description,
        )

        return annotation, field_info

    def _resolve_annotation(
        self,
        field_type_name: str,
        field_definition: dict[str, Any],
        location: str,
    ) -> Any:
        """Map a declarative type name to a Python annotation."""

        simple_types: dict[str, Any] = {
            "string": str,
            "boolean": bool,
            "integer": int,
            "float": float,
            "object": dict[str, Any],
            "string_list": list[str],
            "object_list": list[dict[str, Any]],
            "optional_string": Union[str, NONE_TYPE],
            "optional_int": Union[int, NONE_TYPE],
            "optional_float": Union[float, NONE_TYPE],
        }

        if field_type_name in simple_types:
            return simple_types[field_type_name]

        if field_type_name == "literal":
            values = field_definition.get("values")

            if not isinstance(values, list) or not values:
                raise ContractFactoryError(
                    f"{location} must declare a non-empty "
                    "values list"
                )

            if any(
                isinstance(value, (dict, list, set))
                for value in values
            ):
                raise ContractFactoryError(
                    f"{location} literal values must be "
                    "scalar values"
                )

            return Literal.__getitem__(tuple(values))

        raise ContractFactoryError(
            f"{location} uses unsupported type "
            f"{field_type_name!r}"
        )

    def _create_field_info(
        self,
        annotation: Any,
        default: Any,
        description: str | None,
    ) -> FieldInfo:
        """Create a safe Pydantic field definition."""

        if isinstance(default, list):
            template = deepcopy(default)

            return Field(
                default_factory=lambda value=template: deepcopy(
                    value
                ),
                description=description,
            )

        if isinstance(default, dict):
            template = deepcopy(default)

            return Field(
                default_factory=lambda value=template: deepcopy(
                    value
                ),
                description=description,
            )

        return Field(
            default=default,
            description=description,
        )


def build_contract_factory(
    bundle: AgentDefinitionBundle,
) -> ContractFactory:
    """Create a ContractFactory for a loaded agent bundle."""

    return ContractFactory(bundle)


def load_contract_factory(
    agent_directory: Path | str,
) -> ContractFactory:
    """Load an agent bundle and create its ContractFactory."""

    try:
        bundle = load_agent_definition(agent_directory)
    except AgentDefinitionError as exc:
        raise ContractFactoryError(
            f"Could not load agent definitions: {exc}"
        ) from exc

    return ContractFactory(bundle)


def generate_contracts(
    bundle: AgentDefinitionBundle,
) -> dict[str, type[BaseModel]]:
    """Generate all contracts for a loaded agent bundle."""

    return ContractFactory(bundle).build_all()


def generate_schemas(
    bundle: AgentDefinitionBundle,
) -> dict[str, dict[str, Any]]:
    """Generate JSON Schema for all contracts."""

    return ContractFactory(bundle).schemas()