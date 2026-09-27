from __future__ import annotations
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"agent-runtime"))
from langgraph_runtime.checkpointing import (
    CheckpointerBackend, CheckpointerFactory, CheckpointerSettings,
)
from bootstrap.langgraph_checkpointer_bootstrap import create_langgraph_checkpointer

def test_memory_factory():
    handle=CheckpointerFactory().create(CheckpointerSettings())
    assert handle.checkpointer is not None
    handle.close()

def test_non_memory_requires_connection_string():
    with pytest.raises(ValueError,match="connection_string"):
        CheckpointerSettings(backend=CheckpointerBackend.POSTGRES).validate()

def test_environment_bootstrap_defaults_to_memory():
    handle=create_langgraph_checkpointer({})
    assert handle.checkpointer is not None
