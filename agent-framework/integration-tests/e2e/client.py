from __future__ import annotations

from typing import Any

import httpx


class E2EClient:
    def __init__(self, *, timeout_seconds: float) -> None:
        self._client = httpx.Client(timeout=timeout_seconds)

    def close(self) -> None:
        self._client.close()

    def get_json(self, url: str) -> dict[str, Any]:
        response = self._client.get(url)
        response.raise_for_status()
        return _object(response)

    def post_json(
        self,
        url: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        response = self._client.post(url, json=body)
        response.raise_for_status()
        return _object(response)


def _object(response: httpx.Response) -> dict[str, Any]:
    value = response.json()
    if not isinstance(value, dict):
        raise AssertionError(
            f"Expected JSON object from {response.request.url}"
        )
    return value
