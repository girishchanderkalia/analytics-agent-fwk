---
id: opo-analysis-agent-v4-knowledge
version: "4.0"
kind: knowledge-model

# `concepts` is a glossary for the agent development team; it is validated but
# not injected into prompts. `evidence_labels` is the single source of truth

# for data semantics: each key MUST match a declared state-model.md field, and
# the runtime injects an entry into a model node's prompt only when that node
# actually reads or writes the field (see workflow-definition.md inputs /
# input_projection / output_to). Keep both sections limited to what this
# agent's workflow actually produces or consumes - a stale entry here is
# either silently wasted (concepts) or rejected at load time (evidence_labels,
# since the field-match is validated).

concepts:
  trend:
    owner: OPO Monitoring application
    description: >
      A time-ordered representation of an application-defined OPO KPI.

  tdbb_run:
    owner: Analytics Foundation
    description: >
      Completed TDBB processing (10par model, AVG per lot and W2W per wafer)
      reported as an overview of NCE and CE wafer, field and translation
      budgets per context level (average, chuck to chuck, lot to lot, wafer
      to wafer), each |mean| + 3 sigma in nm.

  tdbb_comparison:
    owner: OPO Monitoring application
    description: >
      Before/after change in each TDBB budget and the largest increase.

  nce_root_cause:
    owner: OPO Monitoring application
    description: >
      A temporal correlation between a TDBB budget change and the NCE
      fingerprint-residual's center-versus-edge wafer radial profile. Localises
      where the residual change is concentrated; does not establish causation.

evidence_labels:
  trend_filters:
    description: Filters extracted from the analyst request.

  trend_series:
    description: Per-wafer overlay X and Y KPIs returned by the trend-query capability.

  change_suggestion:
    description: >
      Suggested change date and prefilled follow-up question derived from a
      step in the daily X/Y means.

  comparison_scope:
    description: Change date separating the before and after periods.

  tdbb_before_run:
    description: >
      Foundation TDBB result for the before period: run IDs, budgets (NCE and
      CE wafer, field and translation per context level, each |mean| + 3
      sigma in nm) and wafer/field maps, from the 10par model with AVG and
      W2W context levels.

  tdbb_after_run:
    description: >
      Foundation TDBB result for the after period, with the same semantics as
      tdbb_before_run.

  tdbb_model_analysis:
    description: >
      Model interpretation of where the before/after TDBB budget change is
      concentrated, grounded only in tdbb_before_run and tdbb_after_run.

  tdbb_summary:
    description: >
      Analyst-facing summary of the TDBB comparison, including the largest
      relative budget increase.

  nce_root_cause_analysis:
    description: >
      Model correlation between the TDBB budget change and the
      fingerprint-residual (nce_wafer) radial profile (center versus edge
      wafer bands), grounded only in tdbb_before_run and tdbb_after_run, with
      evidence-grounded next actions. A correlation, not a confirmed cause.
---

# OPO Monitoring Knowledge Model

## Application-owned knowledge

The OPO Monitoring application owns:

- KPI definitions
- trend semantics
- outlier meaning
- relevant filters
- relevant analytical data
- investigation logic
- evidence interpretation

## Analytics Foundation-owned knowledge

Analytics Foundation owns:

- workspace identity and status
- registration state
- governed service contracts
- asset metadata
- processing state

## Runtime-owned knowledge

The Application Agent Runtime owns:

- conversation identifiers
- LangGraph checkpoint identifiers
- node execution status
- pending approval actions
- capability registration
- capability request mapping
- capability result mapping
- runtime telemetry

Runtime information is operational context and must not be presented as domain
evidence.

## Evidence interpretation

A finding may describe:

- an observed trend
- a threshold violation
- a comparison between supplied observations
- a grouping pattern present in supplied evidence
- a spatial pattern present in supplied wafer evidence
- a change in a TDBB budget between two periods
- a limitation of the available evidence

A finding must not describe:

- an unobserved measurement
- an undeclared KPI
- an unavailable time range
- an invented dataset
- an unsupported root cause
- an invented relationship between process variables

A plausible explanation remains an alternative explanation until additional
evidence confirms the explanation.

## Confidence interpretation

`low` confidence means that the available evidence is limited or supports
multiple explanations.

`medium` confidence means that a consistent pattern is present, but causality
has not been established.

`high` confidence may only be used when the supplied evidence directly and
consistently supports the finding. High confidence does not automatically mean
that a root cause has been confirmed.