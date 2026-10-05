"""Browser-level tests for the OPO Monitoring UI.

These drive the real front end served by the BFF, so a passing run proves the
chain browser -> BFF -> Analytics Foundation (deterministic) and
browser -> BFF -> Agent Runtime (model-backed, gated on RUN_AGENT_E2E).
"""

from __future__ import annotations

import re

import pytest

pytest.importorskip("playwright.sync_api")

from playwright.sync_api import Page, expect  # noqa: E402

pytestmark = pytest.mark.ui

# The agent calls a model and governed MCP tools per turn, so a UI turn is far
# slower than Playwright's default five second expectation window.
AGENT_TURN_TIMEOUT_MS = 180_000
MAX_GATES = 6


def open_ui(page: Page, settings) -> None:
    page.goto(settings.bff_url + "/")
    expect(page.locator("header h1")).to_have_text("OPO Monitoring UI")


def require_model_backed_run(settings) -> None:
    if not settings.run_agent_e2e:
        pytest.skip("Set RUN_AGENT_E2E=true for model-backed UI flow")


def wait_for_turn(page: Page) -> None:
    expect(page.locator("#send-btn")).to_be_enabled(
        timeout=AGENT_TURN_TIMEOUT_MS
    )
    expect(page.locator("#busy-node")).to_have_count(0)
    # The UI renders downstream failures as a timeline node rather than a page
    # error, so surface that text instead of failing on a later empty locator.
    errors = page.locator("#timeline .msg.agent", has=page.locator(".badge.cancelled"))
    if errors.count():
        pytest.fail(errors.last.inner_text())


def answer_gate(page: Page) -> None:
    """Answer the runtime's approval request."""
    gate = page.locator("#interaction-panel .gate")

    if gate.locator("#outlier-select").count():
        gate.locator("#outlier-select").select_option(index=0)
    if gate.locator("#action-select").count():
        gate.locator("#action-select").select_option(index=1)

    gate.locator('[data-action="approve"]').click()
    wait_for_turn(page)


@pytest.mark.ui
def test_ui_loads_and_renders_deterministic_trend_data(page: Page, settings):
    open_ui(page, settings)

    # Requires non-zero counts: "0 series - 0 points" means the dataset is empty.
    expect(page.locator("#chart-note")).to_have_text(
        re.compile(r"[1-9]\d* series .* [1-9]\d* points"), timeout=30_000
    )
    expect(page.locator("#trend-plot .plotly")).to_be_visible()
    expect(page.locator("#interaction-panel")).to_be_hidden()
    expect(page.locator("#findings-panel")).to_be_hidden()


@pytest.mark.ui
def test_v4_starter_prompt_uses_observed_product_layer_scanner_and_date(page: Page, settings):
    open_ui(page, settings)
    expect(page.locator("#chart-note")).to_have_text(
        re.compile(r"[1-9]\d* series .* [1-9]\d* points"), timeout=30_000
    )
    expect(page.locator("#agent-select")).to_be_enabled(timeout=30_000)
    page.locator("#agent-select").select_option(label="TDBB Analysis Agent (v4.0)")

    prompt = page.locator("#message-input").input_value()
    match = re.fullmatch(
        r"Show OPO performance of product (.+), layer (.+) on scanner (.+) since \d{1,2} \w+ \d{4}",
        prompt,
    )
    assert match is not None
    product, layer, scanner = match.groups()
    series = page.evaluate("availableTrendSeries")
    assert any(
        item["product"] == product
        and item["layer_id"] == layer
        and (item.get("exposure_equipment_id") or item["machine"]) == scanner
        for item in series
    )


@pytest.mark.ui
def test_ui_reports_an_unknown_conversation_instead_of_failing_silently(
    page: Page,
    settings,
):
    open_ui(page, settings)

    page.fill("#conversation-input", "conversation-does-not-exist")
    page.click("#reopen-btn")

    expect(page.locator("#timeline .msg.agent")).to_contain_text(
        "Could not reopen", timeout=30_000
    )


@pytest.mark.ui
def test_evidence_panel_can_be_collapsed_and_restored(page: Page, settings):
    open_ui(page, settings)

    page.click("#toggle-right-panel")
    expect(page.locator("main")).to_have_class(re.compile(r"right-panel-collapsed"))

    page.click("#toggle-right-panel")
    expect(page.locator("main")).not_to_have_class(
        re.compile(r"right-panel-collapsed")
    )


@pytest.mark.ui
def test_agent_workflow_runs_end_to_end_from_the_browser(page: Page, settings):
    require_model_backed_run(settings)
    open_ui(page, settings)

    page.fill("#message-input", "Show me trends and outliers")
    page.click("#send-btn")

    expect(page.locator("#timeline .msg.user")).to_contain_text(
        "Show me trends and outliers"
    )
    wait_for_turn(page)

    # The conversation id proves the browser reached the runtime through the BFF.
    expect(page.locator("#conversation-input")).not_to_have_value("")

    for _ in range(MAX_GATES):
        if page.locator("#interaction-panel").is_hidden():
            break
        answer_gate(page)

    expect(page.locator("#interaction-panel")).to_be_hidden()
    expect(page.locator("#timeline .msg.agent .badge").last).to_have_text(
        re.compile(r"Complete|No outliers|Cancelled")
    )



@pytest.mark.ui
def test_a_started_investigation_can_be_reopened_by_conversation_id(
    page: Page,
    settings,
):
    require_model_backed_run(settings)
    open_ui(page, settings)

    page.fill("#message-input", "Show me trends and outliers")
    page.click("#send-btn")
    wait_for_turn(page)

    conversation_id = page.input_value("#conversation-input")
    assert conversation_id

    page.reload()
    page.fill("#conversation-input", conversation_id)
    page.click("#reopen-btn")

    expect(page.locator("#timeline .msg.status").first).to_contain_text(
        conversation_id, timeout=AGENT_TURN_TIMEOUT_MS
    )
