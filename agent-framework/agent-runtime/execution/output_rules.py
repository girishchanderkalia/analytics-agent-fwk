"""Evaluate declarative guardrail rules against a model output.

Rules are authored per model node in an agent's workflow definition; this
module only knows generic rule types and nothing about any agent's domain.
Parameters may reference workflow state as `$.path` and the model output
itself as `${output.path}`. A field path segment ending in `[]` applies the
rule to every list item.
"""

from __future__ import annotations

import ast
import json
import operator
import re
from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

RULE_TYPES = frozenset({
    "required",
    "iso_date",
    "date_between",
    "day_span",
    "mentioned_in",
    "contains",
    "one_of",
    "numbers_from",
    "forbidden_phrases",
    "max_length",
    "min_length",
    "formula",
    "greatest_in",
    "matches",
})

_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")
_OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


class OutputRuleError(ValueError):
    """Raised when a rule is authored incorrectly."""


def validate_rule(rule: Mapping[str, Any], context: str) -> None:
    kind = rule.get("rule")
    if kind not in RULE_TYPES:
        raise OutputRuleError(f"{context} uses unsupported rule {kind!r}; supported: {sorted(RULE_TYPES)}")
    if not isinstance(rule.get("field"), str) or not rule["field"].strip():
        raise OutputRuleError(f"{context} rule {kind!r} requires a field")
    required = {
        "mentioned_in": ("source",),
        "numbers_from": ("source",),
        "forbidden_phrases": ("values",),
        "contains": ("values",),
        "day_span": ("from", "min", "max"),
        "max_length": ("max",),
        "min_length": ("min",),
        "formula": ("equals",),
        "greatest_in": ("source", "keys"),
        "matches": ("source",),
    }.get(kind, ())
    missing = [name for name in required if name not in rule]
    if kind == "one_of" and not ({"values", "source"} & set(rule)):
        missing.append("values or source")
    if kind == "date_between" and not ({"after", "until"} & set(rule)):
        missing.append("after or until")
    if missing:
        raise OutputRuleError(f"{context} rule {kind!r} requires {', '.join(missing)}")


def check_output(output: Mapping[str, Any], rules: Iterable[Mapping[str, Any]], state: Mapping[str, Any]) -> list[str]:
    """Return one message per violated rule; an empty list means the output passed."""

    violations: list[str] = []
    for rule in rules:
        params = {key: _param(value, output, state) for key, value in rule.items() if key not in ("field", "rule")}
        for label, value, parent in _field_values(output, rule["field"]):
            message = _CHECKS[rule["rule"]](value, params, parent)
            if message:
                violations.append(f"{label}: {message}")
    return violations


def _param(value: Any, output: Mapping[str, Any], state: Mapping[str, Any]) -> Any:
    if isinstance(value, str) and value.startswith("$."):
        return _read(state, value[2:])
    if isinstance(value, str) and value.startswith("${output.") and value.endswith("}"):
        return _read(output, value[len("${output."):-1])
    return value


def _read(value: Any, path: str) -> Any:
    for segment in path.split("."):
        if isinstance(value, list) and segment.isdigit():
            value = value[int(segment)] if int(segment) < len(value) else None
            continue
        if not isinstance(value, Mapping):
            return None
        value = value.get(segment)
    return value


def _field_values(output: Mapping[str, Any], path: str) -> list[tuple[str, Any, Mapping[str, Any]]]:
    items: list[tuple[str, Any, Mapping[str, Any]]] = [("", output, output)]
    for segment in path.split("."):
        each = segment.endswith("[]")
        name = segment[:-2] if each else segment
        next_items = []
        for label, value, _ in items:
            child = value.get(name) if isinstance(value, Mapping) else None
            child_label = f"{label}.{name}" if label else name
            if each:
                for index, item in enumerate(child if isinstance(child, list) else []):
                    next_items.append((f"{child_label}[{index}]", item, value))
            else:
                next_items.append((child_label, child, value))
        items = next_items
    # A rule on list items judges each item with its siblings in scope.
    return [(label, value, parent if not path.endswith("[]") else value) for label, value, parent in items]


def _present(value: Any) -> bool:
    return value not in (None, "", [], {})


def _as_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _required(value: Any, params: Mapping[str, Any], parent: Any) -> str | None:
    return None if _present(value) else "is required"


def _iso_date(value: Any, params: Mapping[str, Any], parent: Any) -> str | None:
    if not _present(value):
        return None
    return None if _as_date(value) and len(str(value)) == 10 else f"{value!r} is not an ISO date (YYYY-MM-DD)"


def _date_between(value: Any, params: Mapping[str, Any], parent: Any) -> str | None:
    if not _present(value):
        return None
    day = _as_date(value)
    if day is None:
        return f"{value!r} is not a date"
    after, until = _as_date(params.get("after")) if params.get("after") else None, _as_date(params.get("until")) if params.get("until") else None
    if after and day <= after:
        return f"{day} must be after {after}"
    if until and day > until:
        return f"{day} must be on or before {until}"
    return None


def _day_span(value: Any, params: Mapping[str, Any], parent: Any) -> str | None:
    day = _as_date(value) if _present(value) else None
    start = _as_date(params.get("from") or "")
    if day is None or start is None:
        return None
    days = (day - start).days
    if not int(params["min"]) <= days <= int(params["max"]):
        return f"{day} is {days} days after {start}; expected {params['min']} to {params['max']}"
    return None


def _mentions(text: str, value: Any) -> bool:
    lowered = text.lower()
    day = _as_date(value) if isinstance(value, str) and len(value) == 10 else None
    if day:
        return day.isoformat() in lowered or bool(
            re.search(rf"\b{day.day}(st|nd|rd|th)?\s+{day:%b}", lowered, re.IGNORECASE)
            or re.search(rf"{day:%b}\w*\s+{day.day}\b", lowered, re.IGNORECASE)
        )
    return str(value).lower() in lowered


def _mentioned_in(value: Any, params: Mapping[str, Any], parent: Any) -> str | None:
    source = _text(params.get("source"))
    missing = [str(item) for item in _values(value) if not _mentions(source, item)]
    return f"{', '.join(missing)} not mentioned in the source" if missing else None


def _one_of(value: Any, params: Mapping[str, Any], parent: Any) -> str | None:
    allowed = params.get("values") if "values" in params else params.get("source")
    allowed = list(allowed) if isinstance(allowed, (list, tuple)) else [allowed]
    invalid = [str(item) for item in _values(value) if item not in allowed]
    return f"{', '.join(invalid)} not one of the allowed values" if invalid else None


def _numbers_from(value: Any, params: Mapping[str, Any], parent: Any) -> str | None:
    if not _present(value):
        return None
    tolerance = float(params.get("tolerance", 0))
    known = [abs(number) for number in _numbers(params.get("source")) + _numbers(params.get("allowed"))]
    claimed = [abs(float(value))] if isinstance(value, (int, float)) and not isinstance(value, bool) else [abs(float(n)) for n in _NUMBER.findall(_text(value))]
    unknown = [n for n in claimed if not any(abs(n - k) <= tolerance for k in known)]
    return f"numbers {', '.join(f'{n:g}' for n in unknown)} are not in the source" if unknown else None


def _forbidden_phrases(value: Any, params: Mapping[str, Any], parent: Any) -> str | None:
    text = _text(value).lower()
    found = [phrase for phrase in params.get("values") or [] if str(phrase).lower() in text]
    return f"contains forbidden phrases {found}" if found else None


def _contains(value: Any, params: Mapping[str, Any], parent: Any) -> str | None:
    text = _text(value).lower()
    missing = [phrase for phrase in params.get("values") or [] if str(phrase).lower() not in text]
    return f"is missing {missing}" if missing else None


def _max_length(value: Any, params: Mapping[str, Any], parent: Any) -> str | None:
    size = len(value) if isinstance(value, (str, list, dict)) else 0
    return f"length {size} exceeds {params['max']}" if size > int(params["max"]) else None


def _min_length(value: Any, params: Mapping[str, Any], parent: Any) -> str | None:
    # A list minimum means "at least as many items as the reference list".
    minimum = len(params["min"]) if isinstance(params["min"], (list, tuple)) else int(params["min"] or 0)
    size = len(value) if isinstance(value, (str, list, dict)) else 0
    return f"has {size} items; expected at least {minimum}" if size < minimum else None


def _formula(value: Any, params: Mapping[str, Any], parent: Any) -> str | None:
    try:
        expected = _evaluate(str(params["equals"]), parent if isinstance(parent, Mapping) else {})
    except (KeyError, TypeError, ZeroDivisionError):
        expected = None
    if expected is None:
        return None if value is None else f"{value!r} should be null because its inputs are missing"
    tolerance = float(params.get("tolerance", 0))
    if not isinstance(value, (int, float)) or abs(value - expected) > tolerance:
        return f"{value!r} should equal {params['equals']} = {round(expected, 4)}"
    return None


def _evaluate(expression: str, scope: Mapping[str, Any]) -> float | None:
    def walk(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
            return _OPERATORS[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -walk(node.operand)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name):
            value = scope[node.id]
            if value is None:
                raise TypeError(node.id)
            return float(value)
        raise OutputRuleError(f"Unsupported formula: {expression!r}")

    return walk(ast.parse(expression, mode="eval"))


def _greatest_in(value: Any, params: Mapping[str, Any], parent: Any) -> str | None:
    items = params.get("source") if isinstance(params.get("source"), list) else []
    candidates = [
        float(item[key])
        for item in items
        if isinstance(item, Mapping)
        for key in params["keys"]
        if isinstance(item.get(key), (int, float)) and not isinstance(item.get(key), bool)
    ]
    if not candidates:
        return None
    greatest = max(candidates)
    tolerance = float(params.get("tolerance", 0))
    if not isinstance(value, (int, float)) or abs(value - greatest) > tolerance:
        return f"{value!r} is not the greatest value; the greatest is {greatest:g}"
    return None


def _matches(value: Any, params: Mapping[str, Any], parent: Any) -> str | None:
    """Equal the source value; with `key`, the `value` field of the source item sharing the parent's key."""

    expected = params.get("source")
    if "key" in params:
        key = params["key"]
        own = parent.get(key) if isinstance(parent, Mapping) else None
        item = next((i for i in expected or [] if isinstance(i, Mapping) and i.get(key) == own), None)
        if item is None:
            return f"no source item has {key} {own!r}"
        expected = item.get(params.get("value", key))
    numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (value, expected))
    if numeric and abs(value - expected) <= float(params.get("tolerance", 0)):
        return None
    return None if value == expected else f"{value!r} should be {expected!r}"


def _values(value: Any) -> list[Any]:
    if not _present(value):
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, default=str)


def _numbers(value: Any) -> list[float]:
    if isinstance(value, bool) or value is None:
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, str):
        return [float(n) for n in _NUMBER.findall(value)]
    if isinstance(value, Mapping):
        return [n for item in value.values() for n in _numbers(item)]
    if isinstance(value, (list, tuple)):
        return [n for item in value for n in _numbers(item)]
    return []


_CHECKS = {
    "required": _required,
    "iso_date": _iso_date,
    "date_between": _date_between,
    "day_span": _day_span,
    "mentioned_in": _mentioned_in,
    "contains": _contains,
    "one_of": _one_of,
    "numbers_from": _numbers_from,
    "forbidden_phrases": _forbidden_phrases,
    "max_length": _max_length,
    "min_length": _min_length,
    "formula": _formula,
    "greatest_in": _greatest_in,
    "matches": _matches,
}
