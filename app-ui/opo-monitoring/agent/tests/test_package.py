from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))


def test_all_package_files_parse() -> None:
    for name in ("agent-package.yaml", "graph.yaml", "state.yaml", "prompts.yaml", "tools.yaml"):
        assert load(name)["schema_version"] == "1.0"


def test_package_references_exist() -> None:
    package = load("agent-package.yaml")["package"]
    for key in ("graph", "state", "prompts", "tools"):
        assert (ROOT / package[key]).is_file()
    for knowledge in package["knowledge"]:
        assert (ROOT / knowledge).is_file()


def test_graph_references_valid_nodes_prompts_and_tools() -> None:
    graph = load("graph.yaml")["graph"]
    prompts = load("prompts.yaml")["prompts"]
    tools = load("tools.yaml")["tools"]
    nodes = graph["nodes"]
    assert graph["entrypoint"] in nodes
    assert graph["terminal"] in nodes
    for node in nodes.values():
        if node["kind"] == "model":
            assert node["prompt"] in prompts
        if node["kind"] == "tool":
            assert node["tool"] in tools
    for edge in graph["edges"]:
        assert edge["from"] in nodes
        assert edge["to"] in nodes


def test_graph_state_writes_are_declared() -> None:
    state = load("state.yaml")["state"]
    graph = load("graph.yaml")["graph"]
    permitted_external = {"metadata"}
    for node in graph["nodes"].values():
        for field in node.get("writes", []):
            assert field in state or field in permitted_external


def test_graph_contains_four_human_interactions() -> None:
    nodes = load("graph.yaml")["graph"]["nodes"]
    interrupts = {name for name, node in nodes.items() if node["kind"] == "interrupt"}
    assert interrupts == {
        "await_next_command",
        "confirm_absolute_threshold",
        "confirm_investigation",
        "offer_next_actions",
    }


def test_foundation_tool_names_match_slice_13d() -> None:
    tools = load("tools.yaml")["tools"]
    foundation = {name for name, value in tools.items() if value["server"] == "analytics-foundation"}
    assert foundation == {
        "query_trends", "get_distribution_stats", "get_metadata",
        "create_workspace", "add_workspace_filters", "register_dataset",
        "get_registration_status", "query_wafers",
    }


def test_no_platform_implementation_in_agent_package() -> None:
    content = chr(10).join(path.read_text(encoding="utf-8") for path in ROOT.rglob("*") if path.is_file() and path.suffix in {".yaml", ".md"})
    forbidden = ("foundation_api", "httpx", "requests.", "StateGraph(", "build_checkpointer", "postgres")
    assert not any(value in content for value in forbidden)
