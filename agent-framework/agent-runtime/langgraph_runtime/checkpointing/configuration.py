"""Configuration for LangGraph checkpoint backends."""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum

class CheckpointerBackend(StrEnum):
    MEMORY = "memory"
    SQLITE = "sqlite"
    POSTGRES = "postgres"

@dataclass(frozen=True)
class CheckpointerSettings:
    backend: CheckpointerBackend = CheckpointerBackend.MEMORY
    connection_string: str | None = None
    setup_schema: bool = False

    def validate(self) -> None:
        if self.backend is CheckpointerBackend.MEMORY:
            return
        if not isinstance(self.connection_string, str) or not self.connection_string.strip():
            raise ValueError(f"connection_string is required for {self.backend.value}")
