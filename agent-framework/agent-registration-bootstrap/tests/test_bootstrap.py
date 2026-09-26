from pathlib import Path

import pytest
import yaml

from agent_registration_bootstrap import (
    InMemoryAgentRegistry,
    RegistrationBootstrap,
    RegistrationValidationError,
    bootstrap_from_environment,
)
import shutil


def copy_agent(tmp_path: Path) -> Path:
    root = Path(__file__).resolve().parents[1]
    source = root.parent / "app-ui" / "opo-monitoring" / "agent"
    target = tmp_path / "agent"
    shutil.copytree(source, target)
    return target / "agent-package.yaml"


class Tools:
    def __init__(self, missing=()):
        self.missing = set(missing)

    def contains(self, *, name, version, server):
        return f"{server}:{name}:{version}" not in self.missing


def test_registers_13g_package(tmp_path) -> None:
    manifest = copy_agent(tmp_path)
    registry = InMemoryAgentRegistry()
    result = RegistrationBootstrap(registry, tool_availability=Tools()).register_all([manifest])
    assert len(result) == 1
    assert result[0].identity.application_id == "opo-monitoring"
    assert result[0].identity.agent_id == "opo-investigation"
    assert len(registry.snapshot()) == 1


def test_registration_is_idempotent(tmp_path) -> None:
    manifest = copy_agent(tmp_path)
    registry = InMemoryAgentRegistry()
    bootstrap = RegistrationBootstrap(registry, tool_availability=Tools())
    first = bootstrap.register_all([manifest])[0]
    second = bootstrap.register_all([manifest])[0]
    assert first.fingerprint == second.fingerprint
    assert len(registry.snapshot()) == 1


def test_missing_active_tool_prevents_registration(tmp_path) -> None:
    manifest = copy_agent(tmp_path)
    registry = InMemoryAgentRegistry()
    tools = Tools({"analytics-foundation:query_trends:1"})
    with pytest.raises(RegistrationValidationError, match="query_trends"):
        RegistrationBootstrap(registry, tool_availability=tools).register_all([manifest])
    assert registry.snapshot() == ()


def test_planned_13h_tools_can_be_deferred(tmp_path) -> None:
    manifest = copy_agent(tmp_path)
    registry = InMemoryAgentRegistry()
    tools = Tools({"opo-capability:analyze_trends:1"})
    RegistrationBootstrap(registry, tool_availability=tools).register_all([manifest])
    assert len(registry.snapshot()) == 1


def test_strict_mode_requires_13h_tools(tmp_path) -> None:
    manifest = copy_agent(tmp_path)
    with pytest.raises(RegistrationValidationError, match="analyze_trends"):
        RegistrationBootstrap(
            InMemoryAgentRegistry(),
            tool_availability=Tools({"opo-capability:analyze_trends:1"}),
            allow_planned_tools=False,
        ).register_all([manifest])


def test_invalid_graph_reference_is_rejected(tmp_path) -> None:
    manifest = copy_agent(tmp_path)
    graph_path = manifest.parent / "graph.yaml"
    graph = yaml.safe_load(graph_path.read_text(encoding="utf-8"))
    graph["graph"]["nodes"]["query_trends"]["tool"] = "missing"
    graph_path.write_text(yaml.safe_dump(graph, sort_keys=False), encoding="utf-8")
    with pytest.raises(RegistrationValidationError, match="Unknown tool"):
        RegistrationBootstrap(InMemoryAgentRegistry()).register_all([manifest])


def test_environment_bootstrap_uses_semicolon_separator(tmp_path, monkeypatch) -> None:
    manifest = copy_agent(tmp_path)
    monkeypatch.setenv("AGENT_PACKAGE_MANIFESTS", str(manifest))
    registry = InMemoryAgentRegistry()
    result = bootstrap_from_environment(registry)
    assert len(result) == 1
    assert len(registry.snapshot()) == 1


def test_no_environment_configuration_is_noop(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_PACKAGE_MANIFESTS", raising=False)
    registry = InMemoryAgentRegistry()
    assert bootstrap_from_environment(registry) == ()
    assert registry.snapshot() == ()
