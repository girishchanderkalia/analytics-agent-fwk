---
id: opo-analysis-agent-v4-sequences
version: "4.0"
kind: sequence-diagrams
---

# OPO performance and TDBB follow-up

```mermaid
sequenceDiagram
    actor Analyst
    participant UI as OPO Monitoring UI
    participant Runtime as Agent Runtime
    participant OPO as OPO Capability
    participant Foundation as Analytics Foundation

    Analyst->>UI: Ask for product/layer/scanner performance since a date
    UI->>Runtime: Start v4 conversation
    Runtime->>Runtime: Parse filters (product, layer, scanner, lot, chuck)
    Runtime->>OPO: Normalize window (current year, one month)
    Runtime->>Foundation: Read filtered OPO trends
    Foundation-->>Runtime: Per-wafer overlay X/Y KPIs (nm)
    Runtime-->>UI: Trend evidence and follow-up prompt
    UI-->>Analyst: Plot X and Y and ask when the jump occurred
    Analyst->>UI: Ask what changed from a date
    UI->>Runtime: Resume with comparison question (approves TDBB)
    Runtime->>Runtime: Interpret change date within the window
    Runtime->>Foundation: Run TDBB (10par, AVG/W2W) before and after
    Foundation-->>Runtime: Run IDs, budgets and wafer/field maps per period
    Runtime->>OPO: Compare budgets
    OPO-->>Runtime: Deltas and largest increase
    Runtime-->>UI: TDBB evidence (budgets, wafer/field maps)
    UI-->>Analyst: Budget bars, wafer/field maps, and fingerprint, EExy and
       fingerprint-residual wafer maps (same TDBB run data) - asks the
       analyst to review and describe an NCE observation

    Analyst->>UI: Describe an NCE observation (e.g. bigger edge residual after the change)
    UI->>Runtime: Resume (approves explaining TDBB and the observation together)
    Runtime->>Runtime: Summarize TDBB comparison
    Runtime->>Runtime: Compare nce_wafer vs ce_wafer budgets and the residual's center/edge radial bands
    Runtime-->>UI: TDBB summary, correlation message and recommended next actions
    UI-->>Analyst: TDBB summary, then root-cause correlation and next steps
       (inspect edge fingerprint, new control model, shadow-mode simulation)
```

The comparison localises the change to TDBB budgets; it does not establish a
cause. The root-cause step is a temporal correlation between the TDBB change
and the NCE residual's radial pattern, not a confirmed cause.
