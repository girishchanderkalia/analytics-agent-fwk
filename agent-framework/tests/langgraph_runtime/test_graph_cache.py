from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent-framework" / "agent-runtime"))

from langgraph_runtime.runtime_api import CompiledGraphCache, CompiledGraphKey


def key(**changes):
    values = {
        "application_id": "app",
        "agent_id": "agent",
        "version": "1",
        "definition_fingerprint": "fingerprint-one",
    }
    values.update(changes)
    return CompiledGraphKey(**values)


def test_cache_reuses_same_identity_and_fingerprint() -> None:
    cache = CompiledGraphCache()
    calls = []
    first = cache.get_or_create(key(), lambda: calls.append(1) or object())
    second = cache.get_or_create(key(), lambda: calls.append(2) or object())
    assert first is second
    assert calls == [1]


def test_cache_separates_fingerprints_and_versions() -> None:
    cache = CompiledGraphCache()
    first = cache.get_or_create(key(), object)
    changed = cache.get_or_create(
        key(definition_fingerprint="fingerprint-two"),
        object,
    )
    versioned = cache.get_or_create(key(version="2"), object)
    assert len({id(first), id(changed), id(versioned)}) == 3


def test_failed_factory_is_not_cached() -> None:
    cache = CompiledGraphCache()
    attempts = []
    def failure():
        attempts.append(1)
        raise RuntimeError("compile failed")
    with pytest.raises(RuntimeError):
        cache.get_or_create(key(), failure)
    cache.get_or_create(key(), lambda: attempts.append(2) or object())
    assert attempts == [1, 2]


def test_targeted_agent_invalidation_removes_all_fingerprints() -> None:
    cache = CompiledGraphCache()
    cache.get_or_create(key(), object)
    cache.get_or_create(
        key(definition_fingerprint="fingerprint-two"),
        object,
    )
    cache.get_or_create(key(agent_id="other"), object)
    assert cache.invalidate_agent("app", "agent", "1") == 2
    assert len(cache.snapshot_keys()) == 1
