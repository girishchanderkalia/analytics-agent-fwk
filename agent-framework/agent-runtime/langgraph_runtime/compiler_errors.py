"""Errors raised while compiling normalized definitions into LangGraph."""


class GraphCompilerError(ValueError):
    """Raised when a normalized graph cannot be compiled safely."""
