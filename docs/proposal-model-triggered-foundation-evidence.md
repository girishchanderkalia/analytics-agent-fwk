# Proposal: model-triggered Foundation evidence in opo-analysis-agent-v4

Status: PROPOSED, NOT IMPLEMENTED

## Current behavior

In `agents/opo-analysis-agent-v4/workflow-definition.md`, `request_trend_evidence`,
`request_tdbb_before` and `request_tdbb_after` are declared as `type: capability`
nodes. `definitions/markdown_translator.py` maps `"capability" -> "tool"`, and
`langgraph_runtime/node_library.py`'s `_create_tool_node` executes them
deterministically: the request is built straight from already-known workflow
state (e.g. `start_date: ${state.trend_filters.start_date}` in
`tools-and-capabilities.md`), the MCP tool is called, and the result is written
into `output_to` (e.g. `trend_series`). The model never runs for these nodes;
they are plain graph steps the runtime walks through automatically, regardless
of what the model would have chosen.

`agents/opo-analysis-agent-v4/agent-definition.md` still contains three
orphaned prompts from an earlier design that are not referenced by any current
workflow node: `trend_evidence`, `tdbb_before_request`, `tdbb_after_request`.
Each instructs a model to call a Foundation tool itself (e.g. "You must call
the provided run_tdbb tool exactly once..."), consistent with a model-triggered
tool-calling design that predates the current deterministic capability nodes.

## Proposed change

Make Foundation evidence fetching model-triggered instead of deterministic, so
the Agent Framework only calls Analytics Foundation when the model decides it
needs more data to answer the analyst, as originally intended by the orphaned
prompts above.

Mechanical steps:

1. Change `request_trend_evidence`, `request_tdbb_before`, `request_tdbb_after`
   node `type` from `capability` to `model` in `workflow-definition.md`.
2. Point each at its existing orphaned prompt (`trend_evidence`,
   `tdbb_before_request`, `tdbb_after_request`).
3. Declare a `tools:` reference on each new model node to the matching
   capability (`data_query.read_trends`, `processing.run_tdbb_before`,
   `processing.run_tdbb_after`) so the model gateway offers that tool via
   function/tool-calling.
4. Verify end-to-end against `node_library.py`'s `_create_model_node`, which
   already has partial support for this pattern (builds a `model_tools` list,
   enforces "model must call its required tool" when declared) — this path is
   not currently exercised by any agent, only the deterministic capability
   path is, so it needs real testing, not just code reading.
5. Update `agents/opo-analysis-agent-v4/workflow-overview.md` to describe the
   new model-triggered flow once implemented.

## Trade-offs

- Turns 3 deterministic steps into 3 additional real LLM round-trips (one to
  fetch trends, one each for before/after TDBB), on top of the 6 model calls
  already in this workflow.
- Per `/memories/repo/perf-notes.md`, LLM inference is already ~98% of this
  workflow's wall-clock time, and some calls have taken minutes; this would
  add further latency.
- There is no branch in the current workflow where the evidence isn't needed:
  the trend series is always required to suggest a change date, and both TDBB
  runs are always required to compare. The model would be dutifully calling a
  tool it has no real choice about, at the cost of extra round-trips and new
  failure modes (model forgets to call the tool, hallucinates instead, etc.).
- Benefit: matches a more "agentic" design where the model explicitly decides
  when it needs data, and could in principle let the model skip or vary
  evidence fetches based on context in a future, less rigid workflow.

## Decision

Not scheduled. Revisit if a future version of this agent needs the model to
conditionally decide whether to fetch evidence (not just always-required
evidence as today).
