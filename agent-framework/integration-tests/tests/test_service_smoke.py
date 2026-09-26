from __future__ import annotations

import pytest


@pytest.mark.smoke
def test_analytics_foundation_health(client, settings):
    result = client.get_json(settings.foundation_url + "/health")
    assert result.get("status") in {"pass", "ok", "healthy"}


@pytest.mark.smoke
def test_analytics_foundation_ready(client, settings):
    result = client.get_json(settings.foundation_url + "/ready")
    assert result.get("status") in {"ready", "pass", "ok"}


@pytest.mark.smoke
def test_opo_capability_ready(client, settings):
    result = client.get_json(settings.opo_capability_url + "/ready")
    assert result == {"status": "ready", "tools": 3}


@pytest.mark.smoke
def test_shared_runtime_health(client, settings):
    result = client.get_json(settings.runtime_url + "/health")
    assert result.get("status") in {"ok", "pass", "healthy"}


@pytest.mark.smoke
def test_bff_health(client, settings):
    result = client.get_json(settings.bff_url + "/actuator/health")
    assert result.get("status") == "UP"
