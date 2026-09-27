from __future__ import annotations

import pytest

from e2e.client import E2EClient
from e2e.settings import Settings


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings.from_environment()


@pytest.fixture(scope="session")
def client(settings: Settings):
    value = E2EClient(
        timeout_seconds=settings.request_timeout_seconds
    )
    yield value
    value.close()


@pytest.fixture(scope="session")
def base_url(settings: Settings) -> str:
    """Serves the Playwright fixtures: the UI shares the BFF origin."""
    return settings.bff_url
