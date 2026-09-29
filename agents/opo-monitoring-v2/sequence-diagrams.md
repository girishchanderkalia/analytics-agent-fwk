---
id: opo-monitoring-sequences-v2
version: "2.0"
kind: sequence-diagrams
---

# OPO performance and TDBB follow-up

```mermaid
sequenceDiagram
    actor Analyst
    participant UI as OPO Monitoring UI
    participant Runtime as Agent Runtime
    participant Foundation as Analytics Foundation

    Analyst->>UI: Ask for product/layer/scanner performance since a date
    UI->>Foundation: Load available trend dates through BFF
    Foundation-->>UI: Observed trend months (for resolving a missing year)
    UI->>Runtime: Start v2 conversation
    Runtime->>Runtime: Parse filters using observed trend months
    Runtime->>Runtime: Normalize inclusive one-month window via OPO capability
    Runtime->>Foundation: Read filtered OPO KPI trends
    Foundation-->>Runtime: Scalar OPO KPI trend series
    Runtime-->>UI: Trend evidence and follow-up prompt
    UI-->>Analyst: Plot KPI and ask when the jump occurred
    Analyst->>UI: Ask what changed before/after a date
    UI->>Runtime: Resume with comparison question
    Runtime->>Runtime: Interpret change date within trend window
    Runtime-->>UI: Comparison scope (no TDBB measurements)
    UI-->>Analyst: Two unavailable TDBB views (budgets; wafer/field)
```

TDBB bars and wafer/field points are not generated until Analytics Foundation
provides TDBB processing and data. OPO KPI measurements are not TDBB budgets.