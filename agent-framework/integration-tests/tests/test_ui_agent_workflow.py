"""Browser-level tests for the OPO Monitoring UI.

These drive the real front end served by the BFF, so a passing run proves the
chain browser -> BFF -> Analytics Foundation (deterministic) and
browser -> BFF -> Agent Runtime (model-backed, gated on RUN_AGENT_E2E).
"""

from __future__ import annotations

import re
import csv

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


@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844)])
def test_overlay_layout_chart_and_export(page: Page, settings, tmp_path, width, height):
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.set_viewport_size({"width": width, "height": height})
    with page.expect_response("**/api/trends/overlay/query") as pending:
        page.goto(settings.bff_url + "/overlay")
    response = pending.value.json()
    expect(page.locator("#overlay-status")).to_contain_text("measurements | MEAN")
    expect(page.locator("#overlay-plot .point").first).to_be_visible()
    assert response["points"]
    expect(page.locator("#overlay-rows tr")).to_have_count(len(response["points"]))
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    plot = page.locator("#overlay-plot").bounding_box()
    results = page.locator(".overlay-results").bounding_box()
    assert plot["y"] + plot["height"] <= results["y"] + 1
    workspace = page.locator(".overlay-workspace").bounding_box()
    chat = page.get_by_role("complementary", name="Chat and evidence").bounding_box()
    if width > 760:
        assert chat["x"] >= workspace["x"] + workspace["width"] - 1
        assert abs(chat["y"] - workspace["y"]) <= 1
        composer = page.locator("#composer").bounding_box()
        assert composer["y"] + composer["height"] <= height
    else:
        assert chat["y"] >= workspace["y"] + workspace["height"] - 1
    page.screenshot(path=str(tmp_path / f"overlay-{width}.png"), full_page=True)
    with page.expect_download() as pending_download:
        page.get_by_role("button", name="Export CSV").click()
    destination = tmp_path / "overlay.csv"
    pending_download.value.save_as(destination)
    with destination.open(newline="", encoding="utf-8") as exported:
        rows = list(csv.DictReader(exported))
    assert len(rows) == len(response["points"])
    assert float(rows[0]["kpi_x"]) == response["points"][0]["kpi_x"]
    page.locator("#horizontal-axis").select_option("lot")
    page.wait_for_function("document.querySelector('#overlay-plot').layout.xaxis.type === 'category'")
    assert page.evaluate("document.querySelector('#overlay-plot').data[0].y.length") == len(rows)
    assert errors == []


def test_overlay_metrics_filters_errors_and_navigation(page: Page, settings):
    page.goto(settings.bff_url + "/overlay")
    expect(page.locator("#overlay-status")).to_contain_text("measurements | MEAN")
    for metric in ("MAX", "MIN", "MEAN", "M3S", "MAX_997"):
        page.locator("#metric").select_option(metric)
        with page.expect_response("**/api/trends/overlay/query") as pending:
            page.get_by_role("button", name="Apply", exact=True).click()
        response = pending.value.json()
        assert response["metric"] == metric and response["points"]
        expect(page.locator("#overlay-status")).to_contain_text(f"measurements | {metric}")
        expect(page.locator("#overlay-rows tr").first.locator("td").nth(9)).to_have_text(f'{response["points"][0]["kpi_x"]:.4f}')
    product = page.locator("#product option").nth(1).get_attribute("value")
    page.locator("#product").select_option(product)
    with page.expect_response("**/api/trends/overlay/query") as pending:
        page.get_by_role("button", name="Apply", exact=True).click()
    filtered = pending.value.json()["points"]
    assert filtered and all(point["product_id"] == product for point in filtered)
    page.locator("#start-date").fill("2099-01-01")
    page.get_by_role("button", name="Apply", exact=True).click()
    expect(page.locator("#overlay-status")).to_contain_text("0 measurements")
    expect(page.get_by_role("button", name="Export CSV")).to_be_disabled()
    page.get_by_role("button", name="Reset", exact=True).click()
    expect(page.locator("#overlay-status")).to_have_text(re.compile(r"[1-9]\d* measurements \| MEAN.*"))
    page.route("**/api/trends/overlay/query", lambda route: route.fulfill(status=503, body="Dataset unavailable"))
    page.get_by_role("button", name="Apply", exact=True).click()
    expect(page.locator("#overlay-error")).to_contain_text("Dataset unavailable")
    expect(page.locator("#overlay-rows tr")).to_have_count(0)
    expect(page.get_by_role("button", name="Export CSV")).to_be_disabled()
    page.unroute("**/api/trends/overlay/query")
    page.get_by_role("button", name="Apply", exact=True).click()
    expect(page.locator("#overlay-error")).to_be_hidden()
    expect(page.locator("#overlay-status")).to_contain_text("measurements | MEAN")
    page.locator("#application-page").select_option("/")
    expect(page.locator("header h1")).to_have_text("OPO Monitoring UI")
    page.locator("#application-page").select_option("/overlay")
    expect(page.locator("header h1")).to_have_text("Overlay data analysis")
    expect(page.locator("#overlay-status")).to_contain_text("measurements | MEAN")


def test_overlay_chat_runs_with_the_registered_model(page: Page, settings):
    require_model_backed_run(settings)
    page.goto(settings.bff_url + "/overlay")
    expect(page.locator("#overlay-status")).to_contain_text("measurements | MEAN")
    expect(page.locator("#agent-select")).to_be_enabled()
    expect(page.locator("#agent-select")).to_contain_text("Overlay analysis")
    page.locator("#message-input").fill("For the first displayed lot measurement, report its lot ID and X/Y values for the selected metric.")
    with page.expect_response("**/api/investigations/chat", timeout=AGENT_TURN_TIMEOUT_MS) as pending:
        page.locator("#send-btn").click()
    response = pending.value.json()
    assert response["status"] == "completed", response
    assert response["agentId"] == "overlay-analysis-agent"
    assert response["result"]["overlay_analysis"]["answer"]
    expect(page.locator("#timeline .msg.agent")).to_contain_text(response["result"]["overlay_analysis"]["answer"].splitlines()[0].replace("**", ""))
    expect(page.locator("#overlay-plot .point").first).to_be_visible()


def test_overlay_chat_uses_its_application_and_displayed_measurements(page: Page, settings):
    requests = []
    page.route("**/api/applications/overlay-data-analysis/agents", lambda route: route.fulfill(json={
        "applicationId": "overlay-data-analysis",
        "agents": [{"agentId": "overlay-analysis-agent", "version": "1.0", "displayName": "Overlay analysis"}],
    }))
    response = {
        "conversationId": "overlay-conversation", "agentId": "overlay-analysis-agent",
        "version": 1, "status": "completed",
        "result": {"overlay_analysis": {"answer": "The selected metric has separate X and Y measurements.", "limitations": ["Units are unspecified."]}},
    }

    def chat(route):
        requests.append(route.request.post_data_json)
        route.fulfill(json=response)

    page.route("**/api/investigations/chat", chat)
    page.route("**/api/investigations/overlay-conversation", lambda route: route.fulfill(json=response))
    page.goto(settings.bff_url + "/overlay")
    expect(page.locator("#agent-select")).to_be_enabled()
    expect(page.locator("#overlay-status")).to_contain_text("measurements | MEAN")
    page.locator("#metric").select_option("MAX_997")
    page.get_by_role("button", name="Apply", exact=True).click()
    expect(page.locator("#overlay-status")).to_contain_text("measurements | MAX_997")
    points = page.locator("#overlay-plot .point").count()
    page.locator("#message-input").fill("Compare the displayed X and Y measurements")
    page.locator("#send-btn").click()
    expect(page.locator("#timeline")).to_contain_text("separate X and Y measurements")
    expect(page.locator("#timeline")).to_contain_text("Units are unspecified")
    expect(page.locator("#timeline")).not_to_contain_text("No outliers")
    assert requests[0]["applicationId"] == "overlay-data-analysis"
    assert requests[0]["agentId"] == "overlay-analysis-agent"
    overlay = requests[0]["applicationContext"]["overlay"]
    assert overlay["metric"] == "MAX_997" and overlay["points"]
    assert "kpi_x" in overlay["points"][0] and "kpi_y" in overlay["points"][0]
    assert page.locator("#overlay-plot .point").count() == points
    page.locator("#reopen-btn").click()
    expect(page.locator("#timeline")).to_contain_text("Reopened conversation")
    expect(page.locator("#timeline")).to_contain_text("separate X and Y measurements")


@pytest.mark.ui
def test_v2_starter_prompt_uses_observed_product_layer_scanner_and_month(page: Page, settings):
    open_ui(page, settings)
    expect(page.locator("#chart-note")).to_have_text(
        re.compile(r"[1-9]\d* series .* [1-9]\d* points"), timeout=30_000
    )
    expect(page.locator("#agent-select")).to_be_enabled(timeout=30_000)
    page.locator("#agent-select").select_option(label="OPO-monitoring-v2 (v2.0)")

    prompt = page.locator("#message-input").input_value()
    match = re.fullmatch(
        r"Show OPO performance of product (.+), layer (.+) on scanner (.+) since (\d{4}-\d{2})-01",
        prompt,
    )
    assert match is not None
    product, layer, scanner, month = match.groups()
    series = page.evaluate("availableTrendSeries")
    assert any(
        item["product"] == product
        and item["layer_id"] == layer
        and (item.get("exposure_equipment_id") or item["machine"]) == scanner
        and any(point["date"].startswith(month) for point in item["points"])
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
