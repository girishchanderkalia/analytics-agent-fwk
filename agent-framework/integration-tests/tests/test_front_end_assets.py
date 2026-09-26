"""The BFF serves the opo-monitoring-fe assets on its own origin."""

from __future__ import annotations

import pytest


@pytest.mark.deterministic
def test_bff_serves_the_front_end_entry_point(client, settings):
    response = client.get(settings.bff_url + "/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "OPO Monitoring UI" in response.text
    assert "/static/bff-client.js" in response.text
    assert "/static/app.js" in response.text


@pytest.mark.deterministic
@pytest.mark.parametrize(
    "asset",
    ["/static/app.js", "/static/bff-client.js", "/static/styles.css"],
)
def test_bff_serves_front_end_assets(client, settings, asset):
    response = client.get(settings.bff_url + asset)

    assert response.status_code == 200
    assert response.text.strip()


@pytest.mark.deterministic
def test_front_end_calls_only_current_bff_routes(client, settings):
    adapter = client.get(settings.bff_url + "/static/bff-client.js").text
    renderer = client.get(settings.bff_url + "/static/app.js").text

    assert "/api/trends/query" in adapter
    assert "/api/investigations/" in adapter
    assert "fetch(" not in renderer
