from __future__ import annotations


BEHAVIOR_ORDER = ("mefirst", "readfile")
SCENARIO_ALIASES = {
    "direct": "mefirst",
    "cross": "readfile",
}
DEFAULT_SCENARIOS = ("mefirst", "readfile", "shadow")


def canonical_scenario_name(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "shadow":
        return "shadow"
    behaviors = scenario_behaviors(normalized)
    return "+".join(behaviors)


def scenario_behaviors(value: str) -> tuple[str, ...]:
    normalized = value.strip().lower()
    if normalized == "shadow":
        return ()
    parts = [SCENARIO_ALIASES.get(part, part) for part in normalized.split("+") if part]
    if not parts:
        raise ValueError("scenario must not be empty")
    unknown = [part for part in parts if part not in BEHAVIOR_ORDER]
    if unknown:
        raise ValueError(f"unknown scenario behavior: {unknown[0]}")
    return tuple(behavior for behavior in BEHAVIOR_ORDER if behavior in parts)


def canonical_behaviors(values: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if not values:
        return ("mefirst",)
    parts = [SCENARIO_ALIASES.get(value.strip().lower(), value.strip().lower()) for value in values]
    unknown = [part for part in parts if part not in BEHAVIOR_ORDER]
    if unknown:
        raise ValueError(f"unknown behavior: {unknown[0]}")
    return tuple(behavior for behavior in BEHAVIOR_ORDER if behavior in parts)
