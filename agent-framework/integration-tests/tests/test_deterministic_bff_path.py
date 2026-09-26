from __future__ import annotations

import pytest


@pytest.mark.deterministic
def test_bff_trend_query_uses_public_contract(
    client,
    settings,
):
    result = client.post_json(
        settings.bff_url + "/api/trends/query",
        {
            "filters": {
                "days": 14,
            },
            "groupBy": [],
        },
    )

    assert result["series"] == []
    assert result["metadata"] == {}


@pytest.mark.deterministic
def test_bff_distribution_uses_public_contract(
    client,
    settings,
):
    result = client.post_json(
        settings.bff_url + "/api/trends/distribution",
        {
            "filters": {
                "days": 14,
            },
            "metric": "opo",
        },
    )

    assert result["count"] == 0
    assert result["minimum"] is None
    assert result["maximum"] is None
    assert result["mean"] is None
    assert result["quantiles"]["p95"] is None
    assert result["quantiles"]["p99"] is None
