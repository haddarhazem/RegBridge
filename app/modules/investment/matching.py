from __future__ import annotations

from decimal import Decimal

DIMENSIONS = ("sector", "stage", "geography", "technology", "ticket")


def _tokens(value) -> set[str]:
    if value is None:
        return set()
    values = value if isinstance(value, list) else str(value).replace(";", ",").split(",")
    return {str(item).strip().casefold() for item in values if str(item).strip()}


def _dimension(investor: dict, startup: dict, key: str) -> str:
    if key == "ticket":
        need = startup.get("funding_need")
        low, high = investor.get("ticket_min"), investor.get("ticket_max")
        if need is None or (low is None and high is None):
            return "UNKNOWN"
        need = Decimal(str(need))
        return "MATCH" if (low is None or need >= Decimal(str(low))) and (high is None or need <= Decimal(str(high))) else "MISMATCH"
    investor_key = {"sector": "sectors", "stage": "stages", "geography": "geographies", "technology": "technologies"}[key]
    left, right = _tokens(investor.get(investor_key)), _tokens(startup.get(key))
    if not left or not right:
        return "UNKNOWN"
    return "MATCH" if left & right else "MISMATCH"


def deterministic_match(investor: dict, startup: dict) -> dict:
    dimensions = {key: _dimension(investor, startup, key) for key in DIMENSIONS}
    comparable = [value for value in dimensions.values() if value != "UNKNOWN"]
    matches = sum(value == "MATCH" for value in comparable)
    return {
        "matching_method": "structured_v1",
        "matching_method_version": "1",
        "dimensions": dimensions,
        "evaluated_dimensions": [key for key, value in dimensions.items() if value != "UNKNOWN"],
        "unknown_dimensions": [key for key, value in dimensions.items() if value == "UNKNOWN"],
        "matches": matches,
        "mismatches": len(comparable) - matches,
        "score": matches / len(comparable) if comparable else None,
        "score_formula": "matches / comparable_dimensions; UNKNOWN excluded",
    }
