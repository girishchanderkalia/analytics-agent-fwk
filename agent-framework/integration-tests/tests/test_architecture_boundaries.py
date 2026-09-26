from __future__ import annotations

from pathlib import Path


def test_java_bff_has_separate_downstream_clients():
    root = Path(__file__).resolve().parents[2]
    runtime = root / "app-ui" / "opo-monitoring" / "src" / "main" / "java"
    if not runtime.exists():
        return
    sources = "\n".join(
        item.read_text(encoding="utf-8")
        for item in runtime.rglob("*.java")
    )
    assert "interface RuntimeServiceClient" in sources
    assert "interface AnalyticsFoundationClient" in sources


def test_opo_capability_service_has_no_foundation_http_dependency():
    root = Path(__file__).resolve().parents[2]
    service = root / "app-ui" / "opo-monitoring" / "opo-monitoring-service" / "opo-capability-service" / "src"
    sources = "\n".join(
        item.read_text(encoding="utf-8")
        for item in service.rglob("*.py")
    )
    assert "analytics_foundation_client" not in sources
    assert "ANALYTICS_FOUNDATION_BASE_URL" not in sources
