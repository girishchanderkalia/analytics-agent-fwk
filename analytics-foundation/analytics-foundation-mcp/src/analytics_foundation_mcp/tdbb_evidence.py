from math import isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from analytics_foundation_client.models import TdbbPeriod


class TdbbEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    before_periods: list[TdbbPeriod]
    after_periods: list[TdbbPeriod]
    section: Literal["overview", "summary", "nce"]


class TdbbEvidenceResult(BaseModel):
    message: str
    largest_change: str = ""
    correlated_evidence: list[str] = Field(default_factory=list)
    recommended_next_actions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


CONTEXTS = (
    ("average", "Average"), ("chuck_to_chuck", "Chuck to chuck"),
    ("lot_to_lot", "Lot to lot"), ("wafer_to_wafer", "Wafer to wafer"),
)


def _period(periods: list[TdbbPeriod], label: str) -> TdbbPeriod:
    matches = [period for period in periods if period.period == label]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {label} period, got {len(matches)}")
    return matches[0]


def _number(value: float | None) -> bool:
    return value is not None and isfinite(value) and value >= 0


def _format(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _percent(old: float | None, new: float | None) -> float | None:
    if not _number(old) or not _number(new) or old == 0:
        return None
    return (new - old) / old * 100


def _values(budget, axis: str) -> float | None:
    return getattr(budget, f"{axis}_m3s", None)


def summarize_tdbb_evidence(request: TdbbEvidenceRequest) -> TdbbEvidenceResult:
    before = _period(request.before_periods, "before")
    after = _period(request.after_periods, "after")
    if before.end_date >= after.start_date:
        raise ValueError("Selected before and after periods must not overlap")
    headline = (f"Before {before.start_date} to {before.end_date}: {before.lot_count} lots / "
                f"{before.wafer_count} wafers; after {after.start_date} to {after.end_date}: "
                f"{after.lot_count} lots / {after.wafer_count} wafers.")
    populated = all(period.lot_count > 0 and period.wafer_count > 0 for period in (before, after))
    old = {budget.budget: budget for budget in before.budgets}
    new = {budget.budget: budget for budget in after.budgets}
    limitations = [] if populated else ["A selected period has no lots or wafers; comparable TDBB evidence is missing."]
    bullets = []
    increases = []
    for context, label in CONTEXTS:
        changes = []
        compared = 0
        zero_unchanged = 0
        if populated:
            for key in sorted(set(old) | set(new)):
                budget = new.get(key) or old[key]
                if budget.context != context:
                    continue
                for axis in ("x", "y"):
                    previous, current = _values(old.get(key), axis), _values(new.get(key), axis)
                    if not _number(previous) or not _number(current):
                        limitations.append(f"{budget.label} {axis.upper()}: comparable budget values are missing.")
                        continue
                    compared += 1
                    if previous == 0:
                        if current == 0:
                            zero_unchanged += 1
                        else:
                            changes.append(f"{budget.metric_label} {axis.upper()} 0 to {_format(current)} nm (percentage change undefined)")
                            limitations.append(f"{budget.label} {axis.upper()}: zero baseline; percentage change is undefined.")
                        continue
                    percentage = _percent(previous, current)
                    detail = (f"{budget.metric_label} {axis.upper()} {_format(previous)} to "
                              f"{_format(current)} nm ({percentage:+.1f}%)")
                    if abs(percentage) > 20:
                        changes.append(detail)
                    if percentage > 0:
                        increases.append((percentage, f"{label}: {detail}"))
        if changes:
            text = "; ".join(changes)
        elif compared and zero_unchanged == compared:
            text = "unchanged zero budgets; percentage change is undefined"
        else:
            text = "no change above 20%" if compared else "no comparable evidence"
        bullets.append(f"- {label}: {text}")
    largest = max(increases, key=lambda item: item[0])[1] if increases else "No supported relative increase."
    if request.section != "nce":
        message = headline + ("\n" + "\n".join(bullets) if request.section == "summary" else " " + largest)
        return TdbbEvidenceResult(message=message, largest_change=largest,
                                  limitations=list(dict.fromkeys(limitations)))

    limitations = [] if populated else limitations[:1]
    evidence = []
    growing = {"nce_wafer": [], "ce_wafer": []}
    for metric in growing:
        key = metric + ".average"
        for axis in ("x", "y"):
            previous, current = _values(old.get(key), axis), _values(new.get(key), axis)
            if not populated or not _number(previous) or not _number(current):
                limitations.append(f"{metric} Average {axis.upper()}: comparable budget evidence is missing.")
                continue
            percentage = _percent(previous, current)
            suffix = f" ({percentage:+.1f}%)" if percentage is not None else " (percentage undefined)"
            evidence.append(f"{metric} Average {axis.upper()}: {_format(previous)} to {_format(current)} nm{suffix}.")
            if current > previous and (percentage is None or percentage > 20):
                growing[metric].append(axis.upper())

    parts = [headline]
    if growing["nce_wafer"]:
        parts.append(f"NCE wafer budgets increased on {'/'.join(growing['nce_wafer'])}.")
    else:
        parts.append("The comparable evidence does not establish NCE wafer growth above 20%.")
    if growing["ce_wafer"]:
        parts.append(f"CE wafer budgets also increased on {'/'.join(growing['ce_wafer'])}; the change is not exclusively non-correctable.")
    else:
        parts.append("No comparable CE wafer increase above 20% is established; missing evidence is not proof of stability.")

    edge_growth = []
    profiles = []
    for period in (before, after):
        profiles.append({band["band"]: band for band in period.radial_profile.get("nce_wafer.average", []) if "band" in band})
    for axis in ("x", "y"):
        changes = {}
        for band in ("center", "edge"):
            previous = profiles[0].get(band, {}).get(f"{axis}_m3s")
            current = profiles[1].get(band, {}).get(f"{axis}_m3s")
            if not populated or not _number(previous) or not _number(current):
                limitations.append(f"NCE radial {band} {axis.upper()}: comparable band evidence is missing.")
                continue
            percentage = _percent(previous, current)
            evidence.append(f"NCE radial {band} {axis.upper()}: {_format(previous)} to {_format(current)} nm.")
            changes[band] = (current - previous, percentage)
        if ("center" in changes and "edge" in changes
                and changes["edge"][1] is not None and changes["center"][1] is not None
                and changes["edge"][1] > 20 and changes["edge"][1] > changes["center"][1]
                and changes["edge"][0] > changes["center"][0]):
            edge_growth.append(axis.upper())
    actions = []
    if edge_growth:
        parts.append(f"NCE growth is disproportionate at the wafer edge on {'/'.join(edge_growth)}. This is temporal correlation, not a confirmed physical cause.")
        actions = [
            "Inspect the edge-weighted fingerprint and exposure process around the change date using the reported band values.",
            "Propose a control model capturing the observed residual pattern.",
            "Propose shadow-mode simulation before production.",
        ]
    else:
        parts.append("The supplied bands do not establish disproportionate edge growth.")
    limitations.append("Budgets and radial profiles do not establish a physical cause or prove unreported process parameters were unchanged.")
    return TdbbEvidenceResult(message=" ".join(parts), correlated_evidence=evidence,
                              recommended_next_actions=actions, limitations=list(dict.fromkeys(limitations)))