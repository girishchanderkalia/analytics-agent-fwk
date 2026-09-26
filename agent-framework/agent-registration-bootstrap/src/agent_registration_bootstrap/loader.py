from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from .errors import RegistrationValidationError
from .models import AgentIdentity, AgentRegistration, ToolRegistration


class AgentPackageLoader:
    """Load and cross-validate one Slice 13G-style package."""

    def load(self, manifest_path: str | Path) -> AgentRegistration:
        manifest_path = Path(manifest_path).resolve()
        manifest = self._yaml(manifest_path)
        self._schema(manifest_path, manifest)
        package = self._mapping(manifest, "package", manifest_path)
        directory = manifest_path.parent

        graph_path = self._file(directory, package, "graph")
        state_path = self._file(directory, package, "state")
        prompts_path = self._file(directory, package, "prompts")
        tools_path = self._file(directory, package, "tools")
        graph_doc = self._yaml(graph_path)
        state_doc = self._yaml(state_path)
        prompts_doc = self._yaml(prompts_path)
        tools_doc = self._yaml(tools_path)
        for path, document in (
            (graph_path, graph_doc), (state_path, state_doc),
            (prompts_path, prompts_doc), (tools_path, tools_doc),
        ):
            self._schema(path, document)

        graph = self._mapping(graph_doc, "graph", graph_path)
        state = self._mapping(state_doc, "state", state_path)
        prompts = self._mapping(prompts_doc, "prompts", prompts_path)
        tool_definitions = self._mapping(tools_doc, "tools", tools_path)
        servers = self._mapping(tools_doc, "servers", tools_path)
        self._validate_graph(graph, state, prompts, tool_definitions)
        tools = self._tools(tool_definitions, servers, tools_path)
        knowledge = tuple(
            self._required_file(directory / value)
            for value in package.get("knowledge", [])
        )
        identity = AgentIdentity(
            str(package.get("application_id", "")),
            str(package.get("agent_id", "")),
            str(package.get("agent_version", "")),
        )
        fingerprint = self._fingerprint(
            manifest_path, graph_path, state_path, prompts_path, tools_path, *knowledge
        )
        return AgentRegistration(
            identity=identity,
            display_name=self._text(package, "display_name", manifest_path),
            description=self._text(package, "description", manifest_path),
            entrypoint=self._text(package, "entrypoint", manifest_path),
            package_directory=directory,
            graph=graph,
            state=state,
            prompts=prompts,
            tools=tools,
            knowledge_files=knowledge,
            fingerprint=fingerprint,
        )

    def _validate_graph(self, graph, state, prompts, tools):
        nodes = self._mapping(graph, "nodes", Path("graph.yaml"))
        entrypoint = graph.get("entrypoint")
        terminal = graph.get("terminal")
        if entrypoint not in nodes or terminal not in nodes:
            raise RegistrationValidationError("Graph entrypoint or terminal is missing")
        for name, node in nodes.items():
            if not isinstance(node, dict):
                raise RegistrationValidationError(f"Node {name} must be an object")
            if node.get("kind") == "model" and node.get("prompt") not in prompts:
                raise RegistrationValidationError(f"Unknown prompt in node {name}")
            if node.get("kind") == "tool" and node.get("tool") not in tools:
                raise RegistrationValidationError(f"Unknown tool in node {name}")
            for write in node.get("writes", []):
                if write not in state and write != "metadata":
                    raise RegistrationValidationError(
                        f"Node {name} writes undeclared state field {write}"
                    )
        for edge in graph.get("edges", []):
            if edge.get("from") not in nodes or edge.get("to") not in nodes:
                raise RegistrationValidationError("Graph edge references unknown node")

    def _tools(self, definitions, servers, path):
        result = []
        for name, value in definitions.items():
            if not isinstance(value, dict):
                raise RegistrationValidationError(f"Tool {name} must be an object")
            server = self._text(value, "server", path)
            if server not in servers:
                raise RegistrationValidationError(f"Tool {name} uses unknown server {server}")
            server_value = servers[server]
            result.append(ToolRegistration(
                name=name,
                server=server,
                version=str(value.get("version", "")).strip(),
                read_only=bool(value.get("read_only", False)),
                availability=server_value.get("availability") if isinstance(server_value, dict) else None,
            ))
        return tuple(sorted(result, key=lambda item: (item.server, item.name, item.version)))

    def _yaml(self, path):
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise RegistrationValidationError(f"Cannot read {path}: {error}") from error
        if not isinstance(value, dict):
            raise RegistrationValidationError(f"{path} must contain a YAML object")
        return value

    def _schema(self, path, value):
        if value.get("schema_version") != "1.0":
            raise RegistrationValidationError(f"Unsupported schema version in {path}")

    def _mapping(self, value, key, path):
        result = value.get(key)
        if not isinstance(result, dict):
            raise RegistrationValidationError(f"{key} must be an object in {path}")
        return result

    def _text(self, value, key, path):
        result = value.get(key)
        if not isinstance(result, str) or not result.strip():
            raise RegistrationValidationError(f"{key} must be non-empty in {path}")
        return result.strip()

    def _file(self, directory, package, key):
        return self._required_file(directory / self._text(package, key, directory))

    def _required_file(self, path):
        path = path.resolve()
        if not path.is_file():
            raise RegistrationValidationError(f"Required file does not exist: {path}")
        return path

    def _fingerprint(self, *paths):
        digest = hashlib.sha256()
        for path in sorted(paths, key=lambda value: str(value)):
            digest.update(str(path.name).encode())
            digest.update(path.read_bytes())
        return digest.hexdigest()
