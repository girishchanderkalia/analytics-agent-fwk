"""Environment-specific settings for production runtime persistence."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSettings(BaseSettings):
    """Values that genuinely vary between deployment environments."""

    model_config = SettingsConfigDict(
        env_prefix="AGENT_RUNTIME_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_path: Path = Path("./var/agent-runtime.db")

    def resolved_database_path(self) -> Path:
        """Resolve the database path relative to the installed repository."""

        path = self.database_path.expanduser()

        if not path.is_absolute():
            path = repository_root() / path

        path = path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


def repository_root() -> Path:
    """Derive the repository root from this installed source file."""

    return Path(__file__).resolve().parents[2]
