"""Small vendor-neutral operational signals with strict privacy defaults."""

from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict
from contextvars import ContextVar
from typing import Any


logger = logging.getLogger("regbridge.observability")
_request_id: ContextVar[str | None] = ContextVar("observability_request_id", default=None)
_SENSITIVE = re.compile(
    r"(?ix)(?:authorization|access[_-]?token|refresh[_-]?token|api[_-]?key|password|secret|bearer|token)"
    r"\s*[:=]\s*[^,}\s]+|sk-[A-Za-z0-9_-]+"
)
_PRIVATE_KEYS = {"prompt", "completion", "content", "body", "document_text", "full_text", "context"}
_SECRET_KEYS = {"authorization", "authorization_header", "access_token", "refresh_token", "api_key", "password", "secret", "bearer", "token"}


def set_request_id(value: str | None) -> None:
    _request_id.set(value)


def current_request_id() -> str | None:
    return _request_id.get()


def _redact(value: Any, *, key: str = "") -> Any:
    lowered = key.casefold()
    if lowered in _PRIVATE_KEYS or lowered in _SECRET_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _redact(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item, key=key) for item in value]
    if isinstance(value, str):
        return _SENSITIVE.sub("[REDACTED]", value)[:500]
    return value


def emit_event(event: str, *, level: int = logging.INFO, **fields: Any) -> None:
    payload = {"event": event, **fields}
    request_id = current_request_id()
    if request_id is not None:
        payload.setdefault("request_id", request_id)
    logger.log(level, json.dumps(_redact(payload), sort_keys=True, default=str))


class MetricsRegistry:
    """In-process counters/histograms; labels are deliberately bounded."""

    def __init__(self) -> None:
        self._counters: defaultdict[tuple[str, tuple[tuple[str, str], ...]], int] = defaultdict(int)
        self._durations: defaultdict[tuple[str, tuple[tuple[str, str], ...]], list[float]] = defaultdict(list)

    @staticmethod
    def _labels(labels: dict[str, Any]) -> tuple[tuple[str, str], ...]:
        allowed = {"component", "operation", "status", "dependency", "error_category", "route_template"}
        return tuple(sorted((key, str(value)) for key, value in labels.items() if key in allowed))

    def increment(self, name: str, **labels: Any) -> None:
        self._counters[(name, self._labels(labels))] += 1

    def observe(self, name: str, duration_ms: float, **labels: Any) -> None:
        key = (name, self._labels(labels))
        values = self._durations[key]
        values.append(round(float(duration_ms), 3))
        if len(values) > 1000:
            del values[:-1000]

    def snapshot(self) -> dict[str, Any]:
        counters = [{"name": name, "labels": dict(labels), "value": value} for (name, labels), value in sorted(self._counters.items())]
        durations = []
        for (name, labels), values in sorted(self._durations.items()):
            ordered = sorted(values)
            durations.append({"name": name, "labels": dict(labels), "count": len(values), "last_ms": values[-1], "p95_ms": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]})
        return {"counters": counters, "durations": durations}

    def reset(self) -> None:
        self._counters.clear()
        self._durations.clear()


metrics = MetricsRegistry()


def dependency_result(*, dependency: str, operation: str, status: str, duration_ms: float, error_category: str | None = None) -> None:
    labels = {"dependency": dependency, "operation": operation, "status": status}
    if error_category:
        labels["error_category"] = error_category
    metrics.increment("regbridge_dependency_calls_total", **labels)
    metrics.observe("regbridge_dependency_duration_ms", duration_ms, **labels)
    emit_event("dependency.operation", component="dependency", dependency=dependency, operation=operation, status=status, duration_ms=round(duration_ms, 3), error_category=error_category)


def elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000
