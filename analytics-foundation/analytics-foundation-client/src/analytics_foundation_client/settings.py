"""Configuration for the shared Analytics Foundation HTTP client."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalyticsFoundationClientSettings:
    base_url: str
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 60.0
    verify_tls: bool | str = True

    def __post_init__(self) -> None:
        if not isinstance(self.base_url, str) or not self.base_url.strip():
            raise ValueError("base_url must be a non-empty string")
        if self.connect_timeout_seconds <= 0:
            raise ValueError("connect_timeout_seconds must be positive")
        if self.read_timeout_seconds <= 0:
            raise ValueError("read_timeout_seconds must be positive")
        object.__setattr__(self, "base_url", self.base_url.rstrip("/"))
