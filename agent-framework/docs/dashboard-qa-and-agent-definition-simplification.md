# Dashboard Q&A agent + agent-definition simplification — discussion summary

Date: 2026-10-07
Scope discussed: `agents/opo-analysis-agent-v4` (used as the concrete example throughout)

This document summarizes a design discussion covering two related topics: (1) whether/how an
agent could let analysts ask free-form questions about the charts on the OPO Monitoring
dashboard, and (2) whether the current 6-file agent-definition bundle format can be simplified.
No code was changed as part of this discussion; this is a design record and recommendation.

## 1. Can an agent answer questions about dashboard plots?

**Yes — and it should be data-driven, not image-based.**

Every model node in the runtime (`_create_model_node` in
`agent-framework/agent-runtime/langgraph_runtime/node_library.py`) builds a plain-text
`input_text` from LangGraph state; `foundation/model_gateway.py` configures a text-only
`pydantic_ai` model with no `ImageUrl`/`BinaryContent` handling anywhere in the repo. Every plot
in `opo-monitoring-fe` (trend chart, TDBB budget bars, wafer/field maps) is rendered client-side
from JSON the BFF/runtime already produced and that already lives in LangGraph state
(`trend_series`, `tdbb_before_run`/`tdbb_after_run.periods`/`.maps`, etc.).

Sending a screenshot/image to a vision model would require new infrastructure (a vision-capable
`MODEL_GATEWAY_MODEL` deployment, new multimodal request plumbing in `node_library.py`/
`model_gateway.py`) and would be *less* accurate than reasoning over the exact numbers already
backing the chart. Reusing the existing `input_projection` text pipeline (the same mechanism
`analyze_tdbb`/`summarize_tdbb`/`analyze_nce_root_cause` already use) is the right fit.

## 2. Vague, cross-panel questions ("highlight main issues in the dashboard")

A single targeted `input_projection` (one state field) isn't enough once the question can span
multiple panels and multiple points in the conversation. Two real constraints surfaced:

- **State path resolution is strict, not optional.** Both `model` node `input_projection` and
  `transform` node `assignments` resolve through `_resolve_value` → `_read_path`
  (`node_library.py`), and `_read_path` **raises `NodeExecutionError`** the moment a referenced
  segment doesn't exist yet (e.g. referencing `tdbb_before_run` before TDBB has run). There is no
  null-safe `$.` resolution in that path today — unlike `execution/expression_evaluator.py`'s
  `resolve_path`, which already returns `None` gracefully and is used for routing conditions. A
  "scan whatever's currently populated" feature needs the null-safe style, not the strict one.
- **The single-page dashboard only ever shows one active agent conversation's evidence at a
  time** (confirmed via `opo-monitoring-fe` — `#tdbb-maps`/`#nce-panel`/`#wafer-plot` all live on
  one page, but are populated by different agents' evidence, never simultaneously). So "the
  dashboard" effectively means "this one conversation's current state" — no cross-agent
  aggregation is needed, only cross-*panel* aggregation within one agent.

### Recommended design

1. **New declarative file per agent, e.g. `dashboard-model.md`**, listing panels: `title`,
   `description` (model-facing semantics), and `sources` (state-model field paths). This is the
   "declarative chart/field definition" requested — authors describe panels once, and the
   framework derives behavior from it instead of hand-written Python per agent.
2. **A new generic node kind** (e.g. `dashboard_context`) that, for each panel, safely resolves
   its `sources` (reusing/adapting the null-safe walk style) and includes the panel only when all
   its sources are already present, inlining the panel's `description` next to the resolved data
   (same "label next to data" pattern as `evidence_labels`). Output goes to one always-present
   field (e.g. `dashboard_context`), so a downstream `model` node can safely declare
   `inputs: [dashboard_context]` with zero custom Python per agent.
3. **Keep per-panel evidence compact** — aggregated budgets/periods/radial_profile, not raw
   per-point wafer maps — same discipline `analyze_tdbb`/`summarize_tdbb` already use.
4. **Give the triage output a `panel` field per finding** (matching real FE panel ids like
   `#tdbb-maps`/`#nce-panel`) so the UI can highlight/scroll to the relevant chart instead of
   returning a disconnected chat bubble.
5. **Reachability**: LangGraph here compiles one fixed `entry_node` + linear `edges`/`routing`
   per agent, and resumability is already fragile around mid-conversation interrupts (checkpoints
   are in-memory only). Rather than bolting conditional re-entry into v4's existing straight-line
   graph, model this as its own small workflow (`build_dashboard_context → triage_issues → END`,
   no approvals) reachable at any time, independent of which step the main wizard is on.

## 3. Simplifying the agent-definition bundle (6 files → fewer)

### Problems found (concrete, not hypothetical)

Inspecting the real v4 bundle surfaced drift that's a direct symptom of the current format:

- `state-model.md` declares ~35 fields; `workflow-definition.md` only references ~17 of them
  (`tdbb_run`, `tdbb_runs`, `tdbb_comparison`, `detection_scope`, `workspace`, `registration`,
  `outliers`, `findings`, `spatial_pattern`, … are all dead leftovers).
- `agent-definition.md`'s `models:` similarly defines `DetectionScope`/`FindingsSummary`, which no
  node in this workflow produces.
- `tools-and-capabilities.md` defines `processing.run_tdbb` (singular), which no node calls — only
  `run_tdbb_before`/`run_tdbb_after` are used, and those two are a near-verbatim copy of each
  other (only `end_date` differs).
- `knowledge-model.md`'s `evidence_labels` is a *second*, separately-authored description of the
  same fields `state-model.md` already documents via its own `description:` — both must stay
  key-identical by hand, and this exact duplication already drifted once in this repo (stale
  `applied_filters`/`workspace`/`registration` instead of the real field names).
- A node's `prompt: trend_filters` / `output: TrendFilters` are lookup keys into
  `agent-definition.md`'s `prompts`/`models` maps — understanding one workflow node requires
  opening a second file.
- `sequence-diagrams.md`'s markdown body is **never read by the translator at all** — only its
  front matter (`id`/`version`/`kind`) is validated (confirmed in
  `definitions/markdown_translator.py` and `execution/definition_loader.py`). It's pure
  documentation with zero functional effect.

None of this is required by the graph compiler or LangGraph — `markdown_translator.py`'s
`translate_bundle` already folds all 6 files into one `NormalizedAgentDefinition`, so the 6-file
split with cross-file string references is purely an authoring-format choice, not a runtime
requirement.

### Quick win (no format change)

Drop `sequence-diagrams.md` from `REQUIRED_DEFINITIONS` (or make it fully optional) — immediately
removes one required file with zero translator logic changes, since its content isn't consumed
today anyway.

### Target design: one required file (`agent.md`), one optional docs file

Collapse `agent-definition.md` + `state-model.md` + `tools-and-capabilities.md` +
`knowledge-model.md` + `workflow-definition.md` into one file by **inlining instead of naming**:
a node's prompt and output schema live on the node; a capability's wiring lives on the node; an
approval's copy lives on the node.

```yaml
---
id: <agent-id>
version: "<X.Y>"
kind: agent

display_name: <Human-readable name>
description: >
  <What this agent does>
ownership:
  owner: <team>
conversation:
  welcome_message: >
    <...>
  suggested_prompts:
    - <...>
context:
  accepted: [<application_context_key>]

# Only fields that need a non-default seed value or aren't produced by any
# node's output - everything else is derived from node output_to/result below.
state:
  conversation_id: {type: optional_string, default: null}
  question: {type: string, default: ""}

entry_node: <first_node_id>

nodes:
  - id: parse_trend_request
    type: model
    output_to: trend_filters
    inputs: [question, conversation_context]
    activity: Interpreting the requested OPO performance window
    prompt: |
      Extract the product, layer, scanner... (same text as today)
    output:                                 # was agent-definition.md `models.TrendFilters.fields`
      start_date:
        type: optional_string
        default: null
        description: Inclusive ISO start date of the requested calendar month.
      # ... remaining fields, same as today's TrendFilters

  - id: request_tdbb_before
    type: capability
    output_to: tdbb_before_run
    inputs: [comparison_scope, trend_filters]
    activity: Asking Foundation for the before-period TDBB result
    capability:                             # was a tools-and-capabilities.md lookup
      operation: run_tdbb
      server: analytics-foundation
      tool: run_tdbb
      approval_required: true
      request:
        start_date: ${state.trend_filters.start_date}
        end_date: ${state.comparison_scope.change_date}
        change_date: ${state.comparison_scope.change_date}

  - id: request_comparison
    type: approval
    decision_field: comparison_requested
    decision_fields:
      comparison_requested: approved
      comparison_request: comparison_request
    activity: Waiting for the analyst to identify the OPO change
    title: Run TDBB before and after a change     # was a separate `approvals:` entry
    description: >
      After reviewing the OPO trend, enter the change date...
    payload:
      question: What changed in OPO?
      details:
        Filters: ${state.trend_filters.interpretation}
      input: {name: comparison_request, label: Your question, type: text}

edges:
  - {from: parse_trend_request, to: request_trend_evidence}
  # ...

routing:
  defaults: {...}
  conditions: [...]
---
# <Agent display name>
<prose>
```

Optional second file (e.g. `docs.md`) holds prose + the mermaid sequence diagram, never parsed by
the runtime — same role `sequence-diagrams.md` already plays today, just explicitly optional.

### What this requires in the translation layer (not yet built)

This is a **parser swap, not a runtime redesign** — `NormalizedAgentDefinition`/`NormalizedGraph`/
the LangGraph compiler/`node_library.py` stay untouched; only `definitions/markdown_translator.py`
+ `execution/definition_loader.py` change:

1. `REQUIRED_DEFINITIONS` drops to `{"agent.md": "agent"}`.
2. State schema is derived by walking every node's `output_to` and its declared output type
   (from the node's inline `output:` for model nodes; default `object`/null for capability nodes
   unless overridden), merged with the explicit `state:` overrides block for seed fields like
   `question`/`conversation_id`.
3. Prompt/model name-lookup goes away — the node *is* the prompt and the output schema. Keep an
   optional top-level `shared:` block for a prompt/model genuinely reused by 2+ nodes.
4. `evidence_labels`/`concepts` go away as separate blocks — the "Data semantics" prompt section
   renders straight from each in-scope field's own inline `description`, via the same
   `knowledge_scope` computation (`_referenced_state_fields`) already in use.
5. The top-level `approvals:` list goes away — each approval's `title`/`description`/`payload`
   moves onto its one workflow node (today's format is already 1:1 node↔approval; no real reuse
   is being served by the separate list).

### Trade-off to weigh before building this

Inlining prompts/output schemas directly into `nodes:` makes `agent.md` *longer per node* even
though the *file count* drops — trading "hunt across 6 files" for "scroll one longer file". For
an agent with many long prompts this is usually still a net comprehension win (everything about
one node is in one place), but it's the opposite of today's instinct to split by "kind of thing"
(prompts vs. state vs. capabilities), and is worth confirming before investing in the new parser.

## 4. Domain-knowledge channels (what the model actually sees)

Three channels reach a model node's prompt today:

1. **`knowledge-model.md` markdown body** (after front matter) — injected as a universal
   "Application knowledge:" section on *every* node. For v4 this is effectively empty today (just
   a bare `## Application-owned knowledge` heading with no content).
2. **`evidence_labels`** (knowledge-model.md front matter) — the channel that *does* reach the
   model, but only scoped to nodes whose `inputs`/`input_projection` actually reference that
   field. For v4, `tdbb_before_run`/`tdbb_after_run`'s `evidence_labels` already states the full
   TDBB semantics (10par model, AVG/W2W context levels, NCE/CE, |mean| + 3 sigma in nm), and it is
   injected into `analyze_tdbb`, `summarize_tdbb`, and `analyze_nce_root_cause` (all three project
   `$.tdbb_before_run`/`$.tdbb_after_run`).
3. **`agent-definition.md` `models.<Name>.fields.<f>.description`** — reaches the model via the
   structured-output JSON schema.

**`concepts:`** (knowledge-model.md front matter) is validated at load time but **never rendered
into any prompt** — it is a human-only glossary for future agent authors, not a model-facing
channel, despite looking like one.

### Recommendation

- Don't pre-emptively add a glossary for well-known generic terms (wafer, lot, chuck, scanner) —
  these are standard semiconductor-fab vocabulary an LLM already has from pretraining, and the
  agent's field descriptions already state the ID *format*, which has been sufficient.
- Do add grounding for this domain's own proprietary abbreviations/conventions (NCE, CE, 10par,
  AVG, W2W, budget semantics) — already done correctly for v4 via `evidence_labels`, scoped to
  exactly the nodes that need it.
- Add new grounding only when a model is observed getting a *specific* decision wrong due to
  missing semantics, via `evidence_labels` scoped to the node that needs it — not via `concepts`,
  which is a dead end for prompt-reaching purposes.

## 5. Suggested next steps (not yet started)

1. Drop `sequence-diagrams.md` from `REQUIRED_DEFINITIONS` (low risk, no format change).
2. Add a "declared but unused" lint to `definition_loader.py`/`markdown_translator.py` that flags
   state fields / models / capabilities not referenced anywhere in `workflow-definition.md` — this
   would have caught every drift example in section 3 automatically.
3. Prototype the consolidated `agent.md` format (section 3) on v4 specifically, as the pilot,
   before rolling out to v1.
4. If/when the dashboard Q&A feature (sections 1–2) is prioritized, start with the
   `dashboard-model.md` + `dashboard_context` node design above.
