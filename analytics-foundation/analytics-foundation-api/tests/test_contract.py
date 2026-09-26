from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "openapi.yaml"
)


def load_contract():
    return yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))


def resolve(schema, document):
    while "$ref" in schema:
        value = document
        for part in schema["$ref"].removeprefix("#/ ").replace("#/", "").split("/"):
            if part:
                value = value[part]
        schema = value
    return schema


def validate_shape(value, schema, document, path="$"):
    schema = resolve(schema, document)
    if value is None and schema.get("nullable"):
        return
    kind = schema.get("type")
    if kind == "object":
        assert isinstance(value, dict), f"{path} must be object"
        for field in schema.get("required", []):
            assert field in value, f"{path}.{field} is required"
        if schema.get("additionalProperties") is False:
            allowed = set(schema.get("properties", {}))
            assert set(value) <= allowed, f"{path} contains unknown fields"
        for field, item in value.items():
            field_schema = schema.get("properties", {}).get(field)
            if field_schema is not None:
                validate_shape(item, field_schema, document, f"{path}.{field}")
    elif kind == "array":
        assert isinstance(value, list), f"{path} must be array"
        for index, item in enumerate(value):
            validate_shape(item, schema["items"], document, f"{path}[{index}]")
    elif kind == "string":
        assert isinstance(value, str), f"{path} must be string"
        if "enum" in schema:
            assert value in schema["enum"]
    elif kind == "integer":
        assert isinstance(value, int) and not isinstance(value, bool)
    elif kind == "number":
        assert isinstance(value, (int, float)) and not isinstance(value, bool)


def test_openapi_contract_has_required_operations():
    contract = load_contract()
    assert contract["openapi"] == "3.0.3"
    operations = {
        operation["operationId"]
        for path in contract["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    }
    assert operations == {
        "health", "ready", "getDatasetMetadata", "getDisplayTrends",
        "queryTrends", "getTrendDistribution", "createWorkspace",
        "addWorkspaceFilters", "getWorkspaceConnectionInfo",
        "registerDataset", "getRegistrationStatus", "queryWafers",
    }


def test_all_local_references_resolve():
    contract = load_contract()
    refs = []
    def walk(value):
        if isinstance(value, dict):
            if "$ref" in value:
                refs.append(value["$ref"])
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(contract)
    for ref in refs:
        assert ref.startswith("#/")
        target = contract
        for part in ref[2:].split("/"):
            target = target[part]
        assert target


def test_examples_match_response_schemas():
    contract = load_contract()
    examples = {
        "trend-response.json": "TrendResponse",
        "distribution-response.json": "DistributionStats",
        "registration-response.json": "RegistrationStatus",
        "wafer-response.json": "WaferQueryResponse",
    }
    for filename, schema_name in examples.items():
        value = json.loads(
            (ROOT / "agent-framework" / "contracts" / "examples" / filename).read_text(encoding="utf-8")
        )
        validate_shape(
            value,
            contract["components"]["schemas"][schema_name],
            contract,
        )


def test_contract_contains_no_agent_or_model_operations():
    operation_ids = {
        operation["operationId"].lower()
        for path in load_contract()["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    }
    forbidden = {"chat", "resume", "prompt", "agent", "findings", "approval"}
    assert all(not any(word in operation for word in forbidden) for operation in operation_ids)
