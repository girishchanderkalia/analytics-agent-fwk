"""Lazy creation of supported LangGraph checkpointers."""
from __future__ import annotations
from importlib import import_module
from typing import Any
from .configuration import CheckpointerBackend, CheckpointerSettings
from .lifecycle import CheckpointerHandle

class CheckpointerFactoryError(RuntimeError):
    pass

class CheckpointerFactory:
    def create(self, settings: CheckpointerSettings) -> CheckpointerHandle:
        settings.validate()
        if settings.backend is CheckpointerBackend.MEMORY:
            return CheckpointerHandle(self._memory())
        if settings.backend is CheckpointerBackend.SQLITE:
            return self._from_connection_context(
                module_name="langgraph.checkpoint.sqlite",
                class_name="SqliteSaver",
                connection_string=settings.connection_string or "",
                setup_schema=settings.setup_schema,
            )
        if settings.backend is CheckpointerBackend.POSTGRES:
            return self._from_connection_context(
                module_name="langgraph.checkpoint.postgres",
                class_name="PostgresSaver",
                connection_string=settings.connection_string or "",
                setup_schema=settings.setup_schema,
            )
        raise CheckpointerFactoryError(f"Unsupported checkpointer backend: {settings.backend}")

    @staticmethod
    def _memory() -> Any:
        try:
            module=import_module("langgraph.checkpoint.memory")
            saver=getattr(module,"InMemorySaver",None) or getattr(module,"MemorySaver")
            return saver()
        except Exception as exc:
            raise CheckpointerFactoryError("Cannot create LangGraph memory checkpointer") from exc

    @staticmethod
    def _from_connection_context(*, module_name: str, class_name: str, connection_string: str, setup_schema: bool) -> CheckpointerHandle:
        try:
            saver_class=getattr(import_module(module_name),class_name)
            context=saver_class.from_conn_string(connection_string)
            saver=context.__enter__()
            if setup_schema:
                setup=getattr(saver,"setup",None)
                if not callable(setup):
                    context.__exit__(None,None,None)
                    raise CheckpointerFactoryError(f"{class_name} does not expose setup()")
                setup()
            return CheckpointerHandle(saver, lambda: context.__exit__(None,None,None))
        except CheckpointerFactoryError:
            raise
        except ModuleNotFoundError as exc:
            raise CheckpointerFactoryError(
                f"Optional dependency for {class_name} is not installed"
            ) from exc
        except Exception as exc:
            raise CheckpointerFactoryError(f"Cannot create {class_name}") from exc
