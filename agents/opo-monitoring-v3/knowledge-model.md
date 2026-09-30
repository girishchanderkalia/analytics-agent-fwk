---
id: opo-monitoring-knowledge-v3
version: "3.0"
kind: knowledge-model

concepts:
  trend:
    owner: OPO Monitoring application
    description: >
      A time-ordered representation of an application-defined OPO KPI.

  detection_scope:
    owner: OPO Monitoring application
    description: >
      The deterministic rule and threshold used to identify candidate
      outliers.

  outlier:
    owner: OPO Monitoring application
    description: >
      A trend observation that violates the selected deterministic detection
      rule.

  selected_outlier:
    owner: OPO Monitoring application
    description: >
      A candidate outlier selected by the analyst for deeper investigation.

  workspace:
    owner: Analytics Foundation
    description: >
      Governed analytical context created for an approved investigation.

  registration:
    owner: Analytics Foundation
    description: >
      Evidence describing whether requested analytical data is available in
      the investigation workspace.

  wafer_evidence:
    owner: OPO Monitoring application
    description: >
      Wafer-level rows returned through governed Analytics Foundation
      capabilities and interpreted using application semantics.

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

evidence_labels:
  trend_filters:
    description: Filters extracted from the analyst request.

  trend_series:
    description: Per-wafer overlay X and Y KPIs returned by the trend-query capability.

  comparison_scope:
    description: Change date separating the before and after periods.

  tdbb_run:
    description: TDBB run IDs, budgets and wafer/field maps per period.

  tdbb_comparison:
    description: Before/after TDBB budget deltas.

  detection_scope:
    description: Detection mode and threshold used to identify outliers.

  analysis:
    description: Deterministic trend-analysis output.

  outliers:
    description: Candidate outliers produced by deterministic analysis.

  selected_outlier:
    description: Candidate selected by the analyst.

  applied_filters:
    description: Filters applied to the investigation workspace.

  workspace:
    description: Workspace identifier and status.

  registration:
    description: Registration state and registered table information.

  anomalous_wafers:
    description: Wafer records identified as anomalous.

  wafer_rows:
    description: Wafer-level rows used to support findings.
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