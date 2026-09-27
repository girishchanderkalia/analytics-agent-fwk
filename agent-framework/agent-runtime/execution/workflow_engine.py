"""Framework-neutral declarative workflow execution engine."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any
import ast
import logging


from .execution_context import ExecutionContext
from .execution_models import (
    ApprovalResumeError,
    ExecutionStatus,
    ResumeInput,
    RoutingError,
    WorkflowExecutionError,
    WorkflowExecutionResult,
)
from .expression_evaluator import (
    apply_state_update,
    evaluate_condition,
)
from .node_executors import NodeExecutor


log = logging.getLogger(__name__)


class WorkflowEngine:
    """Interpret and execute one validated agent workflow."""

    def __init__(
        self,
        *,
        bundle: Any,
        context: ExecutionContext,
        node_executor: NodeExecutor | None = None,
        maximum_steps: int = 100,
    ) -> None:
        """Create a workflow engine for one loaded agent bundle."""

        if maximum_steps <= 0:
            raise ValueError(
                "maximum_steps must be greater than zero"
            )

        self.bundle = bundle
        self.context = context
        self.node_executor = node_executor or NodeExecutor()
        self.maximum_steps = maximum_steps

        self.agent_metadata = bundle.agent.metadata
        self.workflow = bundle.workflow.metadata
        self.state_metadata = bundle.state.metadata
        self.knowledge_markdown = bundle.knowledge.markdown

        raw_nodes = self.workflow.get("nodes", [])

        if not isinstance(raw_nodes, list):
            raise WorkflowExecutionError(
                "Workflow nodes must be a list"
            )

        self.nodes: dict[str, dict[str, Any]] = {}

        for index, node in enumerate(raw_nodes):
            if not isinstance(node, Mapping):
                raise WorkflowExecutionError(
                    f"Workflow node at index {index} "
                    "must be a mapping"
                )

            node_id = node.get("id")

            if (
                not isinstance(node_id, str)
                or not node_id.strip()
            ):
                raise WorkflowExecutionError(
                    f"Workflow node at index {index} "
                    "must declare a non-empty ID"
                )

            normalized_node_id = node_id.strip()

            if normalized_node_id in self.nodes:
                raise WorkflowExecutionError(
                    f"Duplicate workflow node ID "
                    f"{normalized_node_id!r}"
                )

            self.nodes[normalized_node_id] = dict(node)

        raw_edges = self.workflow.get("edges", [])
        self.edges = self._index_edges(raw_edges)

        raw_routing = self.workflow.get("routing", {})

        if raw_routing is None:
            raw_routing = {}

        if not isinstance(raw_routing, Mapping):
            raise WorkflowExecutionError(
                "Workflow routing must be a mapping"
            )

        self.routing = dict(raw_routing)

        entry_node = self.workflow.get("entry_node")

        if (
            not isinstance(entry_node, str)
            or not entry_node.strip()
        ):
            raise WorkflowExecutionError(
                "Workflow must declare a non-empty entry_node"
            )

        self.entry_node = entry_node.strip()

        if self.entry_node not in self.nodes:
            raise WorkflowExecutionError(
                f"Workflow entry node "
                f"{self.entry_node!r} is not declared"
            )

    def create_initial_state(
        self,
        supplied_state: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create workflow state from declared defaults."""

        declared_fields = self.state_metadata.get(
            "fields",
            {},
        )

        if not isinstance(declared_fields, Mapping):
            raise WorkflowExecutionError(
                "State-model fields must be a mapping"
            )

        state: dict[str, Any] = {}

        for field_name, field_definition in (
            declared_fields.items()
        ):
            if not isinstance(field_definition, Mapping):
                raise WorkflowExecutionError(
                    f"State field {field_name!r} "
                    "must be a mapping"
                )

            state[field_name] = deepcopy(
                field_definition.get("default")
            )

        if supplied_state:
            for field_name, value in supplied_state.items():
                if field_name not in state:
                    raise WorkflowExecutionError(
                        f"Unknown initial state field "
                        f"{field_name!r}"
                    )

                state[field_name] = deepcopy(value)

        self._normalize_state_aliases(state)

        state["status"] = ExecutionStatus.RUNNING.value

        return state

    def run(
        self,
        initial_state: Mapping[str, Any] | None = None,
    ) -> WorkflowExecutionResult:
        """Start a new workflow execution."""

        state = self.create_initial_state(
            initial_state
        )

        return self._run_from(
            state=state,
            current_node=self.entry_node,
        )

    def resume(
        self,
        *,
        state: Mapping[str, Any],
        current_node: str,
        resume_input: ResumeInput,
    ) -> WorkflowExecutionResult:
        """Resume execution after an approval interruption."""

        if current_node not in self.nodes:
            raise ApprovalResumeError(
                f"Unknown resume node {current_node!r}"
            )

        node = self.nodes[current_node]

        if node.get("type") != "approval":
            raise ApprovalResumeError(
                f"Node {current_node!r} is not an "
                "approval node"
            )

        mutable_state = deepcopy(dict(state))

        self._normalize_state_aliases(
            mutable_state
        )

        decision_field = node.get(
            "decision_field",
            "investigation_approved",
        )

        selection_field = node.get(
            "selection_field",
            "selected_outlier",
        )

        comment_field = node.get(
            "comment_field",
            "approval_comment",
        )

        for field_name, value in (
            (
                decision_field,
                resume_input.approved,
            ),
            (
                comment_field,
                resume_input.comment,
            ),
        ):
            if not isinstance(field_name, str):
                raise ApprovalResumeError(
                    "Approval state-field references "
                    "must be strings"
                )

            mutable_state[field_name] = deepcopy(value)

        mutable_state["pending_approval"] = None
        mutable_state["pending_action"] = None
        mutable_state["status"] = (
            ExecutionStatus.RUNNING.value
        )

        if resume_input.selected_outlier_id is not None:
            if not isinstance(selection_field, str):
                raise ApprovalResumeError(
                    "Approval selection field must be "
                    "a string"
                )

            mutable_state[selection_field] = (
                self._select_outlier(
                    state=mutable_state,
                    selected_outlier_id=(
                        resume_input.selected_outlier_id
                    ),
                )
            )

        for field_name, value in (
            resume_input.values.items()
        ):
            if field_name not in mutable_state:
                raise ApprovalResumeError(
                    f"Resume input contains unknown state field "
                    f"{field_name!r}"
                )

            mutable_state[field_name] = deepcopy(value)

        self._normalize_state_aliases(
            mutable_state
        )

        next_node = self._determine_next_node(
            current_node=current_node,
            state=mutable_state,
        )

        if next_node == "END":
            if not resume_input.approved:
                mutable_state["status"] = (
                    ExecutionStatus.CANCELLED.value
                )

                return WorkflowExecutionResult(
                    status=ExecutionStatus.CANCELLED,
                    state=mutable_state,
                    current_node=None,
                )

            return self._completed_result(
                mutable_state
            )

        return self._run_from(
            state=mutable_state,
            current_node=next_node,
        )

    def _run_from(
        self,
        *,
        state: dict[str, Any],
        current_node: str,
    ) -> WorkflowExecutionResult:
        """Execute nodes until completion or an interruption."""

        steps = 0

        try:
            while current_node != "END":
                steps += 1

                if steps > self.maximum_steps:
                    raise WorkflowExecutionError(
                        "Workflow exceeded maximum execution "
                        f"steps ({self.maximum_steps})"
                    )

                node = self.nodes.get(current_node)

                if node is None:
                    raise WorkflowExecutionError(
                        f"Workflow references unknown node "
                        f"{current_node!r}"
                    )

                state["current_activity"] = current_node

                result = self.node_executor.execute(
                    node=node,
                    state=state,
                    agent_metadata=self.agent_metadata,
                    knowledge_markdown=(
                        self.knowledge_markdown
                    ),
                    context=self.context,
                )

                self._apply_state_update(
                    state=state,
                    update=result.state_update,
                )

                if result.approval_request is not None:
                    state["status"] = (
                        ExecutionStatus
                        .WAITING_FOR_APPROVAL
                        .value
                    )

                    return WorkflowExecutionResult(
                        status=(
                            ExecutionStatus
                            .WAITING_FOR_APPROVAL
                        ),
                        state=state,
                        current_node=current_node,
                        approval_request=(
                            result.approval_request
                        ),
                    )

                current_node = (
                    self._determine_next_node(
                        current_node=current_node,
                        state=state,
                    )
                )

            return self._completed_result(state)

        except Exception as exc:
            log.exception(
                "Workflow failed at node %r",
                current_node,
            )
            state["status"] = ExecutionStatus.FAILED.value
            state["failure_reason"] = type(exc).__name__
            state["error"] = {
                "message": str(exc),
                "type": type(exc).__name__,
            }

            return WorkflowExecutionResult(
                status=ExecutionStatus.FAILED,
                state=state,
                current_node=current_node,
                error=str(exc),
            )

    @classmethod
    def _evaluate_text_condition(
        cls,
        expression: str,
        state: Mapping[str, Any],
    ) -> bool:
        """Evaluate a simple declarative text condition."""

        if (
            not isinstance(expression, str)
            or not expression.strip()
        ):
            raise RoutingError(
                "Routing condition must be a non-empty string"
            )

        supported_operators = (
            "==",
            "!=",
            ">=",
            "<=",
            ">",
            "<",
        )

        normalized_expression = expression.strip()

        selected_operator = None
        left_text = ""
        right_text = ""

        for operator in supported_operators:
            if operator not in normalized_expression:
                continue

            parts = normalized_expression.split(
                operator,
                1,
            )

            if len(parts) != 2:
                continue

            left_text = parts[0].strip()
            right_text = parts[1].strip()
            selected_operator = operator
            break

        if selected_operator is None:
            raise RoutingError(
                f"Unsupported routing expression: "
                f"{expression!r}"
            )

        if not left_text:
            raise RoutingError(
                f"Routing expression has no state field: "
                f"{expression!r}"
            )

        left_value = cls._resolve_state_value(
            state,
            left_text,
        )

        right_value = cls._parse_condition_value(
            right_text
        )

        if selected_operator == "==":
            return left_value == right_value

        if selected_operator == "!=":
            return left_value != right_value

        try:
            if selected_operator == ">=":
                return left_value >= right_value

            if selected_operator == "<=":
                return left_value <= right_value

            if selected_operator == ">":
                return left_value > right_value

            if selected_operator == "<":
                return left_value < right_value
        except TypeError as exc:
            raise RoutingError(
                f"Cannot compare values in routing "
                f"expression {expression!r}"
            ) from exc

        raise RoutingError(
            f"Unsupported routing operator: "
            f"{selected_operator}"
        )

    @staticmethod
    def _resolve_state_value(
        state: Mapping[str, Any],
        path: str,
    ) -> Any:
        """Resolve a dot-separated value from workflow state."""

        current: Any = state

        for part in path.split("."):
            normalized_part = part.strip()

            if not normalized_part:
                raise RoutingError(
                    f"Invalid state path: {path!r}"
                )

            if not isinstance(current, Mapping):
                raise RoutingError(
                    f"Cannot resolve state path "
                    f"{path!r}"
                )

            if normalized_part not in current:
                return None

            current = current[normalized_part]

        return current

    @staticmethod
    def _parse_condition_value(
        value_text: str,
    ) -> Any:
        """Convert routing text into a Python value."""

        normalized_value = value_text.strip()

        lowercase_value = normalized_value.lower()

        if lowercase_value in {
            "null",
            "none",
        }:
            return None

        if lowercase_value == "true":
            return True

        if lowercase_value == "false":
            return False

        try:
            return ast.literal_eval(
                normalized_value
            )
        except (
            ValueError,
            SyntaxError,
        ):
            return normalized_value

    def _determine_next_node(
        self,
        current_node: str,
        state: dict[str, Any],
    ) -> str:
            """Determine the next node using conditional and default routes."""

            routing = self.routing

            conditions = routing.get(
                "conditions",
                [],
            )

            defaults = routing.get(
                "defaults",
                {},
            )

            if not isinstance(conditions, list):
                raise RoutingError(
                    "Workflow routing conditions must be a list"
                )

            if not isinstance(defaults, Mapping):
                raise RoutingError(
                    "Workflow routing defaults must be a mapping"
                )

            agent_defaults = self.agent_metadata.get(
                "defaults",
                {},
            )

            for route in conditions:
                if not isinstance(route, Mapping):
                    raise RoutingError(
                        "Each workflow route must be a mapping"
                    )

                if route.get("from") != current_node:
                    continue

                condition = route.get("when")

                if isinstance(condition, str):
                    matched = self._evaluate_text_condition(
                        condition,
                        state,
                    )
                elif isinstance(condition, Mapping):
                    matched = evaluate_condition(
                        condition,
                        state,
                        agent_defaults,
                    )
                else:
                    raise RoutingError(
                        f"Route from {current_node!r} has an "
                        "invalid condition"
                    )

                if matched:
                    state_update = route.get(
                        "state_update"
                    )

                    if state_update is not None:
                        apply_state_update(
                            state,
                            state_update,
                        )

                    target = route.get("to")

                    if (
                        not isinstance(target, str)
                        or not target.strip()
                    ):
                        raise RoutingError(
                            f"Conditional route from "
                            f"{current_node!r} must declare "
                            "a non-empty target"
                        )

                    return target.strip()

            default_target = defaults.get(
                current_node
            )

            if default_target is not None:
                if (
                    not isinstance(default_target, str)
                    or not default_target.strip()
                ):
                    raise RoutingError(
                        f"Default route from "
                        f"{current_node!r} must be "
                        "a non-empty string"
                    )

                return default_target.strip()

            edge_target = self.edges.get(
                current_node
            )

            if edge_target is not None:
                return edge_target

            raise RoutingError(
                f"Workflow node {current_node!r} "
                "has no outgoing route"
            )

    def _validate_destination(
        self,
        *,
        current_node: str,
        destination: Any,
    ) -> str:
        """Validate and normalize a routing destination."""

        if (
            not isinstance(destination, str)
            or not destination.strip()
        ):
            raise RoutingError(
                f"Routing from {current_node!r} returned "
                "an invalid destination"
            )

        normalized = destination.strip()

        if (
            normalized != "END"
            and normalized not in self.nodes
        ):
            raise RoutingError(
                f"Routing from {current_node!r} "
                f"resolved to unknown node {normalized!r}"
            )

        return normalized

    @staticmethod
    def _normalize_state_aliases(
        state: dict[str, Any],
    ) -> None:
        """Synchronize old and new workflow-state names."""

        if "detected_outliers" not in state:
            state["detected_outliers"] = deepcopy(
                state.get("outliers", [])
            )

        if "outliers" not in state:
            state["outliers"] = deepcopy(
                state.get("detected_outliers", [])
            )

        if "dataset_registration" not in state:
            state["dataset_registration"] = deepcopy(
                state.get("registration")
            )

        if "registration" not in state:
            state["registration"] = deepcopy(
                state.get("dataset_registration")
            )

        if "application_context" not in state:
            state["application_context"] = deepcopy(
                state.get("conversation_context", {})
            )

        if "conversation_context" not in state:
            state["conversation_context"] = deepcopy(
                state.get("application_context", {})
            )

        # wafer_rows and anomalous_wafers are not aliases: the first is the
        # evidence, the second the identifiers flagged within it.
        if "wafer_rows" not in state:
            state["wafer_rows"] = []

        if "anomalous_wafers" not in state:
            state["anomalous_wafers"] = []

        if "pending_approval" not in state:
            state["pending_approval"] = deepcopy(
                state.get("pending_action")
            )

        if "registration_poll_count" not in state:
            state["registration_poll_count"] = 0

    @classmethod
    def _apply_state_update(
        cls,
        *,
        state: dict[str, Any],
        update: Mapping[str, Any],
    ) -> None:
        """Apply a node result and synchronize aliases."""

        copied_update = deepcopy(dict(update))
        state.update(copied_update)

        alias_pairs = (
            (
                "detected_outliers",
                "outliers",
            ),
            (
                "dataset_registration",
                "registration",
            ),
            (
                "application_context",
                "conversation_context",
            ),
            (
                "pending_approval",
                "pending_action",
            ),
        )

        for canonical, legacy in alias_pairs:
            if canonical in copied_update:
                state[legacy] = deepcopy(
                    copied_update[canonical]
                )

            elif legacy in copied_update:
                state[canonical] = deepcopy(
                    copied_update[legacy]
                )

        cls._normalize_state_aliases(state)

    @staticmethod
    def _select_outlier(
        *,
        state: Mapping[str, Any],
        selected_outlier_id: str,
    ) -> dict[str, Any]:
        """Resolve an analyst-selected outlier."""

        if (
            not isinstance(selected_outlier_id, str)
            or not selected_outlier_id.strip()
        ):
            raise ApprovalResumeError(
                "Selected outlier ID must be "
                "a non-empty string"
            )

        normalized_id = (
            selected_outlier_id.strip()
        )

        outliers = state.get(
            "detected_outliers",
            state.get("outliers", []),
        )

        if not isinstance(outliers, list):
            raise ApprovalResumeError(
                "Workflow outliers must be a list"
            )

        for outlier in outliers:
            if not isinstance(outlier, Mapping):
                continue

            candidate_id = (
                outlier.get("id")
                or outlier.get("outlier_id")
            )

            if candidate_id == normalized_id:
                return deepcopy(dict(outlier))

        raise ApprovalResumeError(
            f"Selected outlier "
            f"{normalized_id!r} was not found"
        )

    @staticmethod
    def _index_edges(
        edges: Any,
    ) -> dict[str, str]:
        """Index one default edge per source node."""

        if not isinstance(edges, list):
            raise WorkflowExecutionError(
                "Workflow edges must be a list"
            )

        indexed_edges: dict[str, str] = {}

        for index, edge in enumerate(edges):
            if not isinstance(edge, Mapping):
                raise WorkflowExecutionError(
                    f"Workflow edge at index {index} "
                    "must be a mapping"
                )

            source = edge.get("from")
            destination = edge.get("to")

            if (
                not isinstance(source, str)
                or not source.strip()
            ):
                raise WorkflowExecutionError(
                    f"Workflow edge at index {index} "
                    "must declare a non-empty source"
                )

            if (
                not isinstance(destination, str)
                or not destination.strip()
            ):
                raise WorkflowExecutionError(
                    f"Workflow edge at index {index} "
                    "must declare a non-empty destination"
                )

            normalized_source = source.strip()
            normalized_destination = (
                destination.strip()
            )

            if normalized_source in indexed_edges:
                raise WorkflowExecutionError(
                    "Workflow contains multiple default "
                    f"edges from {normalized_source!r}"
                )

            indexed_edges[normalized_source] = (
                normalized_destination
            )

        return indexed_edges

    @staticmethod
    def _completed_result(
        state: dict[str, Any],
    ) -> WorkflowExecutionResult:
        """Return a completed workflow result."""

        state["status"] = ExecutionStatus.COMPLETED.value
        state["current_activity"] = None
        state["pending_approval"] = None
        state["pending_action"] = None

        return WorkflowExecutionResult(
            status=ExecutionStatus.COMPLETED,
            state=state,
            current_node=None,
            approval_request=None,
        )