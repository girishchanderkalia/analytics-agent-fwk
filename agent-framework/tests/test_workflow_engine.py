"""Tests for declarative workflow execution."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any


import pytest


V3_ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"
AGENT_REPOSITORY_ROOT = V3_ROOT / "agents"

if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(AGENT_RUNTIME_ROOT),
    )


from execution.definition_loader import (  # noqa: E402
    AgentRepository,
)
from execution.execution_context import (  # noqa: E402
    ExecutionContext,
)
from execution.execution_models import (  # noqa: E402
    ApprovalResumeError,
    ExecutionStatus,
    ResumeInput,
    WorkflowExecutionError,
)
from execution.workflow_engine import (  # noqa: E402
    WorkflowEngine,
)


class FakeContractProvider:
    """Provide lightweight contract classes for tests."""

    def __init__(self) -> None:
        self.requested_contracts: list[str] = []

    def get_contract(
        self,
        contract_name: str,
    ) -> type[Any]:
        self.requested_contracts.append(
            contract_name
        )

        return type(
            contract_name,
            (),
            {},
        )


class FakeModelGateway:
    """Return deterministic structured model responses."""

    def __init__(self) -> None:
        self.invocations: list[
            dict[str, Any]
        ] = []

    def invoke_structured(
        self,
        *,
        system_prompt: str,
        input_text: str,
        output_contract: type[Any],
    ) -> Mapping[str, Any]:
        self.invocations.append(
            {
                "system_prompt": system_prompt,
                "input_text": input_text,
                "output_contract": output_contract,
            }
        )

        contract_name = output_contract.__name__

        if contract_name == "TrendFilters":
            return {
                "lookback_days": 30,
                "start_date": None,
                "end_date": None,
                "lot_ids": [],
                "product_ids": [],
                "layer_ids": [],
                "exposure_equipment_ids": [],
                "interpretation": (
                    "All recent OPO trends"
                ),
            }

        if contract_name == "DetectionScope":
            return {
                "mode": "baseline",
                "limit_value": 3.0,
                "direction": "above",
                "threshold_unit": "percent",
                "baseline_deviation_pct": 3.0,
                "interpretation": (
                    "Baseline comparison"
                ),
                "suggested_limit_value": None,
                "suggested_limit_rationale": None,
            }

        if contract_name == "FindingsSummary":
            return {
                "finding": (
                    "Evidence-based test finding"
                ),
                "evidence_references": [
                    "trend_series",
                    "outliers",
                    "wafer_rows",
                ],
                "confidence": "medium",
                "limitations": [],
                "alternative_explanations": [],
                "recommended_next_actions": [],
            }

        raise AssertionError(
            "Unexpected output contract: "
            f"{contract_name}"
        )


class FakeCapabilityDispatcher:
    """Return deterministic Analytics Foundation results."""

    def __init__(self) -> None:
        self.invocations: list[str] = []

    def invoke(
        self,
        *,
        capability_id: str,
        state: Mapping[str, Any],
        permissions: frozenset[str],
        approved_capabilities: frozenset[str],
    ) -> Mapping[str, Any]:
        self.invocations.append(
            capability_id
        )

        if capability_id == "data_query.read_trends":
            assert (
                "query:trends:read"
                in permissions
            )

            return {
                "trend_series": [
                    {
                        "id": "trend-1",
                        "value": 10.0,
                        "baseline": 6.0,
                    }
                ]
            }

        if capability_id == "workspace.create":
            assert (
                "workspace:create"
                in permissions
            )

            return {
                "workspace": {
                    "id": "workspace-1",
                    "status": "ACTIVE",
                }
            }

        if capability_id == "workspace.add_filters":
            assert (
                "workspace:write"
                in permissions
            )

            return {
                "applied_filters": deepcopy(
                    state.get(
                        "trend_filters",
                        {},
                    )
                )
            }

        if (
            capability_id
            == "workspace.register_dataset"
        ):
            assert (
                "workspace:register"
                in permissions
            )

            assert (
                "workspace.register_dataset"
                in approved_capabilities
            )

            return {
                "registration": {
                    "id": "registration-1",
                    "status": "READY",
                    "workspace_id": (
                        state.get(
                            "workspace",
                            {},
                        ).get("id")
                    ),
                },
                "registration_poll_count": (
                    int(
                        state.get(
                            "registration_poll_count",
                            0,
                        )
                    )
                    + 1
                ),
            }

        if capability_id == "data_query.read_wafers":
            assert (
                "query:wafers:read"
                in permissions
            )

            return {
                "wafer_rows": [
                    {
                        "wafer_id": "wafer-1",
                        "lot_id": "lot-1",
                        "overlay_x": 1.4,
                        "overlay_y": 0.8,
                    }
                ]
            }

        raise AssertionError(
            f"Unexpected capability: {capability_id}"
        )


class FakeOperationRegistry:
    """Execute deterministic OPO trend analysis."""

    def __init__(
        self,
        *,
        include_outlier: bool,
    ) -> None:
        self.include_outlier = include_outlier
        self.invocations: list[str] = []

    def invoke(
        self,
        name: str,
        state: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        self.invocations.append(name)

        if name != "analyse_trends":
            raise AssertionError(
                f"Unexpected operation: {name}"
            )

        if not self.include_outlier:
            return {
                "analysis": [],
                "outliers": [],
            }

        return {
            "analysis": [
                {
                    "trend_id": "trend-1",
                    "deviation": 4.0,
                }
            ],
            "outliers": [
                {
                    "id": "outlier-1",
                    "trend_id": "trend-1",
                    "value": 10.0,
                    "baseline": 6.0,
                    "deviation": 4.0,
                }
            ],
        }


def create_engine(
    *,
    include_outlier: bool,
    maximum_steps: int = 100,
) -> tuple[
    WorkflowEngine,
    FakeModelGateway,
    FakeCapabilityDispatcher,
    FakeOperationRegistry,
    FakeContractProvider,
]:
    """Create a Workflow Engine with deterministic test doubles."""

    repository = AgentRepository(
        AGENT_REPOSITORY_ROOT
    )

    bundle = repository.load(
        "opo-monitoring"
    )

    model_gateway = FakeModelGateway()
    capability_dispatcher = (
        FakeCapabilityDispatcher()
    )

    operation_registry = FakeOperationRegistry(
        include_outlier=include_outlier
    )

    contract_provider = FakeContractProvider()

    context = ExecutionContext(
        model_gateway=model_gateway,
        contract_provider=contract_provider,
        capability_dispatcher=(
            capability_dispatcher
        ),
        operation_registry=operation_registry,
        permissions=frozenset(
            {
                "query:trends:read",
                "query:wafers:read",
                "workspace:create",
                "workspace:write",
                "workspace:register",
            }
        ),
        approved_capabilities=frozenset(
            {
                "workspace.create",
                "workspace.add_filters",
                "workspace.register_dataset",
            }
        ),
    )

    engine = WorkflowEngine(
        bundle=bundle,
        context=context,
        maximum_steps=maximum_steps,
    )

    return (
        engine,
        model_gateway,
        capability_dispatcher,
        operation_registry,
        contract_provider,
    )


def run_until_approval(
    *,
    maximum_steps: int = 100,
) -> tuple[
    WorkflowEngine,
    Any,
    FakeCapabilityDispatcher,
]:
    """Create and run an outlier workflow until approval."""

    (
        engine,
        _,
        capability_dispatcher,
        _,
        _,
    ) = create_engine(
        include_outlier=True,
        maximum_steps=maximum_steps,
    )

    result = engine.run(
        {
            "conversation_id": (
                "conversation-1"
            ),
            "question": (
                "Show trends and outliers"
            ),
        }
    )

    return (
        engine,
        result,
        capability_dispatcher,
    )


def test_initial_state_uses_declared_defaults() -> None:
    (
        engine,
        _,
        _,
        _,
        _,
    ) = create_engine(
        include_outlier=False
    )

    state = engine.create_initial_state(
        {
            "conversation_id": (
                "conversation-1"
            ),
            "question": (
                "Show recent OPO trends"
            ),
        }
    )

    assert (
        state["conversation_id"]
        == "conversation-1"
    )

    assert (
        state["question"]
        == "Show recent OPO trends"
    )

    assert state["status"] == "running"
    assert state["outliers"] == []
    assert state["detected_outliers"] == []
    assert state["registration_poll_count"] == 0


def test_unknown_initial_state_field_is_rejected() -> None:
    (
        engine,
        _,
        _,
        _,
        _,
    ) = create_engine(
        include_outlier=False
    )

    with pytest.raises(
        WorkflowExecutionError,
        match="unknown",
    ):
        engine.create_initial_state(
            {
                "unknown_field": "value",
            }
        )


def test_workflow_completes_when_no_outliers_exist() -> None:
    (
        engine,
        model_gateway,
        capability_dispatcher,
        operation_registry,
        contract_provider,
    ) = create_engine(
        include_outlier=False
    )

    result = engine.run(
        {
            "conversation_id": (
                "conversation-1"
            ),
            "question": (
                "Show trends and outliers"
            ),
        }
    )

    assert (
        result.status
        is ExecutionStatus.COMPLETED
    )

    assert result.current_node is None
    assert result.approval_request is None
    assert result.state["status"] == "completed"
    assert result.state["outliers"] == []
    assert result.state["findings"] is not None

    assert capability_dispatcher.invocations == [
        "data_query.read_trends",
    ]

    assert operation_registry.invocations == [
        "analyse_trends"
    ]

    assert contract_provider.requested_contracts == [
        "TrendFilters",
        "DetectionScope",
        "FindingsSummary",
    ]

    assert len(model_gateway.invocations) == 3


def test_workflow_pauses_for_approval_when_outlier_exists() -> None:
    (
        engine,
        _,
        capability_dispatcher,
        operation_registry,
        _,
    ) = create_engine(
        include_outlier=True
    )

    result = engine.run(
        {
            "conversation_id": (
                "conversation-1"
            ),
            "question": (
                "Show trends and outliers"
            ),
        }
    )

    assert (
        result.status
        is ExecutionStatus.WAITING_FOR_APPROVAL
    )

    assert (
        result.current_node
        == "approve_investigation"
    )

    assert result.approval_request is not None

    assert (
        result.approval_request.approval_id
        == "investigate_outlier"
    )

    assert (
        result.approval_request.node_id
        == "approve_investigation"
    )

    assert (
        result.approval_request.public_type
        == "approval_required"
    )

    assert (
        result.state["status"]
        == "waiting_for_approval"
    )

    assert (
        result.state.get("pending_approval")
        is not None
        or result.state.get("pending_action")
        is not None
    )

    assert capability_dispatcher.invocations == [
        "data_query.read_trends",
    ]

    assert operation_registry.invocations == [
        "analyse_trends",
    ]


def test_approved_workflow_resumes_and_completes() -> None:
    (
        engine,
        paused,
        capability_dispatcher,
    ) = run_until_approval()

    assert paused.current_node is not None

    resumed = engine.resume(
        state=paused.state,
        current_node=paused.current_node,
        resume_input=ResumeInput(
            approved=True,
            selected_outlier_id="outlier-1",
            comment=(
                "Investigate this candidate"
            ),
        ),
    )

    assert (
        resumed.status
        is ExecutionStatus.COMPLETED
    )

    assert resumed.current_node is None
    assert resumed.state["status"] == "completed"

    assert (
        resumed.state["selected_outlier"]["id"]
        == "outlier-1"
    )

    assert (
        resumed.state.get("approval_comment")
        == "Investigate this candidate"
    )

    assert (
        resumed.state["workspace"]["id"]
        == "workspace-1"
    )

    assert (
        resumed.state["registration"]["status"]
        == "READY"
    )

    assert resumed.state["wafer_rows"] == [
        {
            "wafer_id": "wafer-1",
            "lot_id": "lot-1",
            "overlay_x": 1.4,
            "overlay_y": 0.8,
        }
    ]

    assert resumed.state["findings"] is not None

    assert capability_dispatcher.invocations == [
        "data_query.read_trends",
        "workspace.create",
        "workspace.add_filters",
        "workspace.register_dataset",
        "data_query.read_wafers",
    ]


def test_rejected_workflow_is_cancelled() -> None:
    (
        engine,
        paused,
        capability_dispatcher,
    ) = run_until_approval()

    assert paused.current_node is not None

    resumed = engine.resume(
        state=paused.state,
        current_node=paused.current_node,
        resume_input=ResumeInput(
            approved=False,
            comment="Do not investigate",
        ),
    )

    assert (
        resumed.status
        is ExecutionStatus.CANCELLED
    )

    assert resumed.current_node is None
    assert resumed.state["status"] == "cancelled"

    assert (
        resumed.state["investigation_approved"]
        is False
    )

    assert capability_dispatcher.invocations == [
        "data_query.read_trends",
    ]


def test_unknown_selected_outlier_is_rejected() -> None:
    (
        engine,
        paused,
        _,
    ) = run_until_approval()

    assert paused.current_node is not None

    with pytest.raises(
        ApprovalResumeError,
        match="was not found",
    ):
        engine.resume(
            state=paused.state,
            current_node=paused.current_node,
            resume_input=ResumeInput(
                approved=True,
                selected_outlier_id=(
                    "unknown-outlier"
                ),
            ),
        )


def test_non_approval_node_cannot_be_resumed() -> None:
    (
        engine,
        _,
        _,
        _,
        _,
    ) = create_engine(
        include_outlier=True
    )

    state = engine.create_initial_state(
        {
            "conversation_id": (
                "conversation-1"
            ),
            "question": "Show trends",
        }
    )

    with pytest.raises(
        ApprovalResumeError,
        match="is not an approval node",
    ):
        engine.resume(
            state=state,
            current_node="read_trends",
            resume_input=ResumeInput(
                approved=True,
            ),
        )


def test_unknown_resume_node_is_rejected() -> None:
    (
        engine,
        _,
        _,
        _,
        _,
    ) = create_engine(
        include_outlier=True
    )

    state = engine.create_initial_state(
        {
            "conversation_id": (
                "conversation-1"
            ),
            "question": "Show trends",
        }
    )

    with pytest.raises(
        ApprovalResumeError,
        match="Unknown resume node",
    ):
        engine.resume(
            state=state,
            current_node="unknown-node",
            resume_input=ResumeInput(
                approved=True,
            ),
        )


def test_unknown_resume_state_field_is_rejected() -> None:
    (
        engine,
        paused,
        _,
    ) = run_until_approval()

    assert paused.current_node is not None

    with pytest.raises(
        ApprovalResumeError,
        match="unknown state field",
    ):
        engine.resume(
            state=paused.state,
            current_node=paused.current_node,
            resume_input=ResumeInput(
                approved=True,
                selected_outlier_id="outlier-1",
                values={
                    "unknown_state_field": (
                        "value"
                    ),
                },
            ),
        )


def test_model_gateway_receives_application_knowledge() -> None:
    (
        engine,
        model_gateway,
        _,
        _,
        _,
    ) = create_engine(
        include_outlier=False
    )

    result = engine.run(
        {
            "conversation_id": (
                "conversation-1"
            ),
            "question": (
                "Show recent trends"
            ),
        }
    )

    assert (
        result.status
        is ExecutionStatus.COMPLETED
    )

    assert model_gateway.invocations

    for invocation in model_gateway.invocations:
        assert (
            "Application knowledge:"
            in invocation["system_prompt"]
        )


def test_model_gateway_receives_question_in_input() -> None:
    (
        engine,
        model_gateway,
        _,
        _,
        _,
    ) = create_engine(
        include_outlier=False
    )

    question = (
        "Show the latest OPO trends"
    )

    result = engine.run(
        {
            "conversation_id": (
                "conversation-1"
            ),
            "question": question,
        }
    )

    assert (
        result.status
        is ExecutionStatus.COMPLETED
    )

    assert any(
        question in invocation["input_text"]
        for invocation
        in model_gateway.invocations
    )


def test_workflow_stops_at_maximum_steps() -> None:
    (
        engine,
        paused,
        capability_dispatcher,
    ) = run_until_approval(
        maximum_steps=15
    )

    assert paused.current_node is not None

    # Introduce a deliberate cycle for this isolated test.
    # The production workflow remains unchanged.
    engine.edges["read_wafers"] = (
        "read_wafers"
    )

    resumed = engine.resume(
        state=paused.state,
        current_node=paused.current_node,
        resume_input=ResumeInput(
            approved=True,
            selected_outlier_id="outlier-1",
        ),
    )

    assert (
        resumed.status
        is ExecutionStatus.FAILED
    )

    assert resumed.state["status"] == "failed"
    assert resumed.error is not None

    assert (
        "maximum"
        in resumed.error.lower()
    )

    assert (
        capability_dispatcher.invocations.count(
            "data_query.read_wafers"
        )
        > 1 )