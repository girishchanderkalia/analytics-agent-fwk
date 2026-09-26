"""Lifecycle wrapper for checkpointers that own resources."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable

@dataclass
class CheckpointerHandle:
    checkpointer: Any
    close_callback: Callable[[], None] | None = None

    def close(self) -> None:
        if self.close_callback is not None:
            callback, self.close_callback = self.close_callback, None
            callback()

    def __enter__(self) -> Any:
        return self.checkpointer

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
