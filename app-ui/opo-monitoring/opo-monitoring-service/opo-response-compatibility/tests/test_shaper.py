from dataclasses import dataclass

import pytest

from opo_response_compatibility import shape_response, shape_thread_state


@dataclass
class Interrupt:
    value: object


def test_awaiting_human_contract() -> None:
    result = {
        "__interrupt__": [Interrupt({"type": "confirm_investigation"})],
        "outliers": [{"machine": "M1"}],
    }
    response = shape_response(result, "thread-1")
    assert tuple(response) == ("thread_id", "status", "request", "evidence")
    assert response["status"] == "awaiting_human"
    assert response["request"] == {"type": "confirm_investigation"}


def test_mapping_interrupt_from_runtime_envelope() -> None:
    response = shape_response(
        {"interrupt": {"value": {"type": "next_command"}}},
        "thread-1",
    )
    assert response["status"] == "awaiting_human"
    assert response["request"] == {"type": "next_command"}


def test_cancelled_contract_has_precedence_over_no_outliers() -> None:
    response = shape_response(
        {"cancelled_at": "confirm_investigation", "outliers": []},
        "thread-1",
    )
    assert tuple(response) == (
        "thread_id", "status", "cancelled_at", "evidence"
    )
    assert response["status"] == "cancelled"
    assert response["cancelled_at"] == "confirm_investigation"


def test_no_outliers_contract() -> None:
    response = shape_response({"outliers": []}, "thread-1")
    assert tuple(response) == ("thread_id", "status", "evidence")
    assert response["status"] == "no_outliers"


def test_complete_contract() -> None:
    findings = {"finding": "Supported statement"}
    response = shape_response(
        {"outliers": [{"machine": "M1"}], "findings": findings},
        "thread-1",
    )
    assert tuple(response) == ("thread_id", "status", "findings", "evidence")
    assert response["status"] == "complete"
    assert response["findings"] == findings


def test_thread_snapshot_contract() -> None:
    response = shape_thread_state(
        thread_id="thread-1",
        values={"mode": "absolute"},
        pending_interrupts=[Interrupt({"type": "confirm"})],
    )
    assert response == {
        "thread_id": "thread-1",
        "status": "awaiting_human",
        "request": {"type": "confirm"},
        "values": {"mode": "absolute"},
    }


def test_blank_thread_id_is_rejected() -> None:
    with pytest.raises(ValueError):
        shape_response({}, " ")
