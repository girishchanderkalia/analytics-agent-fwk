# Single-file agent authoring

Use `agent.md` as the starting point for a new agent package. Copy the directory
to `agents/<your-agent-id>/`, replace the example identity and ownership, and
write authoritative domain knowledge before deployment. The directory named
`template` is excluded from repository discovery; explicitly configured package
roots are still loaded, so do not add the template to deployment configuration.

## Model-facing knowledge

- `knowledge.always`: rules included in every model step.
- `knowledge.topics`: named domain definitions and interpretation rules.
- Each model step's `knowledge`: explicit list of topics included in that step.
- State and step output `description`: evidence semantics automatically included
  when a model step reads or writes that state field.
- `instructions`: the task for that model step.
- `output` field descriptions: structured-response contract supplied to the model.

The Markdown body and this README are developer documentation, not prompt content.
An empty topic list includes only universal rules and relevant data semantics.
Unknown topic references fail validation. Each step gets its own generated prompt
identifier, avoiding knowledge leakage through shared prompt IDs.

Define proprietary terminology, units, aggregation, scope, provenance, missing-data
meaning, valid comparisons and causal limitations. Do not rely on pretrained
knowledge for application-specific conventions. Keep raw evidence separate from
model interpretations and analyst observations.

## Workflow

Step order supplies the normal execution path and first-step entry point.
Use `routing.conditions` for early exits or branches. Advanced packages may
override `entry_node` and `edges` explicitly; declared node IDs and targets are validated.

Model steps declare inline `instructions`, `output` fields and `output_to`.
Use `inputs` for whole state fields or `input_projection` for compact evidence.
Projection paths remain required: a missing nested path is a runtime error,
not optional evidence. Place steps after the operations that supply their evidence.

Capability steps contain an inline `capability` with operation, server, tool,
request mapping and result mapping. Keep Foundation access governed through MCP.
The template does not invent a tool or server; add real registered tools only.
Approval requirements and side-effect metadata do not create an approval gate:
declare an approval step and route rejection away from side-effect operations.

Approval steps declare inline `approval`, application-facing `payload`, and
typed `responses`. Each response key is a state field; `from` names the resume
decision key, such as `approved`. These response schemas seed state, but do not
add new runtime validation of resume values. Preserve existing application
approval IDs when migrating application-integrated workflows.

`question` and `conversation_context` are seeded automatically. Model/capability
`output_to` fields are derived as objects and approval state from response schemas.
Use `state` for external fields, custom defaults or type overrides. Model output
contracts are validated separately; capability results are opaque unless a state
override describes their top-level type. Tool-schema inference, optional projections
and external includes are not implemented by this initial format.

## Validate and inspect

From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = "$PWD;$PWD/agent-framework/agent-runtime"
python -m execution.definition_loader agents/template
python -m execution.definition_loader agents/template --preview-step answer_question
python -m execution.definition_loader agents/opo-analysis-agent-v4 --preview-step analyze_nce_root_cause
```

The preview shows the composed prompt, evidence bindings and authored output fields.
Runtime evidence values and gateway-generated output-schema instructions are not
rendered in the preview. Review them with execution traces when validating behavior.

Legacy six-file packages remain supported. A package with `agent.md` uses the
single-file format even if legacy files are also present. Register the finished
package through `AGENT_MARKDOWN_PACKAGES`; local startup includes OPO v1 and v4.
Adding a package does not change the application's currently selected agent.

Both OPO packages use this single-file format. V1 retains explicit edges for its
alternate threshold and follow-up paths; V4 derives its main path from step order.