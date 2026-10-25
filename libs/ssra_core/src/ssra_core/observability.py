"""Prometheus metrics facade, chat-turn/language recorders, OWASP security events, client RUM telemetry, and turn audit digests (`libs/ssra_core/src/ssra_core/observability.py`).

Transferred and adapted from `FinalYearProject/App/backend/app/{analytics,client_telemetry,security_events,audit/turns}.py`
for SSRA Assist (October 2026 standards).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import math
import os
import re
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("ssra.observability")
security_logger = logging.getLogger("ssra.security")
client_logger = logging.getLogger("ssra.client")

METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
NAMESPACE = "ssra_"

_MAX_SERIES_PER_METRIC = max(10, int(os.getenv("METRICS_MAX_SERIES_PER_METRIC", "500")))
_MAX_LABEL_VALUE_LEN = 120
_OVERFLOW_LABEL = "__other__"
_UNMATCHED_ROUTE = "__unmatched__"
_KNOWN_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})
_NAME_RE = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")
_LABEL_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

_MS_BUCKETS: tuple[float, ...] = (
    5.0,
    10.0,
    25.0,
    50.0,
    100.0,
    250.0,
    500.0,
    1000.0,
    2000.0,
    3000.0,
    5000.0,
    10000.0,
    20000.0,
    30000.0,
    60000.0,
    120000.0,
)
_SECONDS_BUCKETS: tuple[float, ...] = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.0,
    3.0,
    5.0,
    10.0,
    20.0,
    30.0,
    60.0,
    120.0,
)
_RATIO_BUCKETS: tuple[float, ...] = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
_BYTES_BUCKETS: tuple[float, ...] = (
    1024.0,
    4096.0,
    16384.0,
    65536.0,
    262144.0,
    1048576.0,
    4194304.0,
    16777216.0,
    67108864.0,
)
_COUNT_BUCKETS: tuple[float, ...] = (1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1000.0)
_CLS_BUCKETS: tuple[float, ...] = (0.01, 0.025, 0.05, 0.1, 0.15, 0.25, 0.5, 1.0, 2.0)

_QUANTILES = (("p50", 0.5), ("p95", 0.95), ("p99", 0.99))

_LIFECYCLE_HELP: dict[str, str] = {
    "ssra_qdrant_index_fresh": "1 when the serving Qdrant index matches the approved knowledge snapshot",
    "ssra_qdrant_index_drift": "1 when source/index drift or a missing index binding was reported",
    "ssra_qdrant_index_status_timestamp_seconds": "When the freshness status was last checked",
    "ssra_qdrant_rebuild_failed": "1 when the last staged Qdrant rebuild failed before promotion",
    "ssra_qdrant_rebuild_timestamp_seconds": "When the last staged Qdrant rebuild was attempted",
    "ssra_qdrant_backup_required": "1 when this deployment must keep snapshot backups",
    "ssra_qdrant_backup_failed": "1 when the last required snapshot backup failed",
    "ssra_qdrant_backup_timestamp_seconds": "When the last snapshot backup was attempted",
    "ssra_qdrant_restore_drill_failed": "1 when the last restore drill failed",
    "ssra_qdrant_restore_drill_timestamp_seconds": "When the last restore drill ran",
}


def default_buckets(name: str) -> tuple[float, ...]:
    """Histogram buckets for `name`, inferred from its unit suffix."""
    if name.endswith("_ms"):
        return _MS_BUCKETS
    if name.endswith(("_seconds", "_s")):
        return _SECONDS_BUCKETS
    if name.endswith("_bytes"):
        return _BYTES_BUCKETS
    if "score" in name or "faithfulness" in name or name.endswith("_ratio"):
        return _RATIO_BUCKETS
    return _COUNT_BUCKETS


def exported_name(name: str) -> str:
    """Return the single-namespaced (`ssra_`) Prometheus family name."""
    clean = name.strip()
    if not _NAME_RE.match(clean):
        raise ValueError(f"invalid metric name: {name!r}")
    return clean if clean.startswith(NAMESPACE) else f"{NAMESPACE}{clean}"


def _clean_label_value(value: Any) -> str:
    text = "" if value is None else str(value)[:_MAX_LABEL_VALUE_LEN]
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\r", " ").replace("\n", " ")


def _number(value: float) -> int | float:
    return int(value) if float(value).is_integer() else round(value, 4)


def bucket_quantile(q: float, buckets: list[tuple[float, float]], count: float) -> float:
    """Estimate quantile `q` from cumulative `(upper_bound, count)` buckets (mirrors PromQL `histogram_quantile`)."""
    if count <= 0 or not buckets:
        return 0.0
    rank = q * count
    prev_upper, prev_cum = 0.0, 0.0
    for upper, cumulative in buckets:
        if cumulative >= rank:
            if math.isinf(upper):
                return prev_upper
            if cumulative == prev_cum:
                return upper
            return prev_upper + (upper - prev_upper) * (rank - prev_cum) / (cumulative - prev_cum)
        prev_upper, prev_cum = upper, cumulative
    return prev_upper


@dataclass
class _HistogramChild:
    bounds: tuple[float, ...]
    bucket_counts: list[float] = field(default_factory=list)
    count: float = 0.0
    total: float = 0.0

    def __post_init__(self) -> None:
        if not self.bucket_counts:
            self.bucket_counts = [0.0 for _ in range(len(self.bounds) + 1)]

    def observe(self, value: float) -> None:
        if not math.isfinite(value):
            return
        self.count += 1.0
        self.total += value
        for idx, bound in enumerate(self.bounds):
            if value <= bound:
                self.bucket_counts[idx] += 1.0
        self.bucket_counts[-1] += 1.0


@dataclass
class _Family:
    kind: Literal["counter", "histogram", "gauge_latest", "gauge_sum"]
    full_name: str
    label_names: tuple[str, ...]
    bounds: tuple[float, ...] = ()
    seen: set[tuple[str, ...]] = field(default_factory=set)
    scalars: dict[tuple[str, ...], float] = field(default_factory=dict)
    histograms: dict[tuple[str, ...], _HistogramChild] = field(default_factory=dict)


class MetricsStore:
    """Thread-safe Prometheus metrics facade with cumulative histograms and bounded label cardinality."""

    def __init__(self, *, max_series_per_metric: int = _MAX_SERIES_PER_METRIC) -> None:
        self._lock = Lock()
        self._families: dict[str, _Family] = {}
        self._warned: set[str] = set()
        self._start_time = time.time()
        self._max_series = max(10, max_series_per_metric)

    def inc(self, name: str, value: float = 1.0, labels: Mapping[str, Any] | None = None) -> None:
        """Increment a counter family."""
        self._record_scalar("counter", name, value, labels, additive=True)

    def set_gauge(self, name: str, value: float, labels: Mapping[str, Any] | None = None) -> None:
        """Set a gauge to its latest value."""
        self._record_scalar("gauge_latest", name, value, labels, additive=False)

    def add_gauge(self, name: str, delta: float, labels: Mapping[str, Any] | None = None) -> None:
        """Increment or decrement an up/down gauge."""
        self._record_scalar("gauge_sum", name, delta, labels, additive=True)

    def observe(
        self,
        name: str,
        value: float,
        labels: Mapping[str, Any] | None = None,
        *,
        buckets: Iterable[float] | None = None,
    ) -> None:
        """Observe a value in a cumulative histogram family."""
        try:
            label_keys = tuple(sorted((labels or {}).keys()))
            family = self._get_or_create_family("histogram", name, label_keys, buckets)
            if family is None:
                return
            values = self._resolve_label_values(name, family, labels or {})
            with self._lock:
                child = family.histograms.get(values)
                if child is None:
                    child = _HistogramChild(bounds=family.bounds)
                    family.histograms[values] = child
                child.observe(float(value))
        except Exception:
            self._warn_once(f"record:{name}", "Metric %s could not be recorded", name)

    def _record_scalar(
        self,
        kind: Literal["counter", "gauge_latest", "gauge_sum"],
        name: str,
        value: float,
        labels: Mapping[str, Any] | None,
        *,
        additive: bool,
    ) -> None:
        try:
            label_keys = tuple(sorted((labels or {}).keys()))
            family = self._get_or_create_family(kind, name, label_keys, None)
            if family is None:
                return
            values = self._resolve_label_values(name, family, labels or {})
            with self._lock:
                if additive:
                    family.scalars[values] = family.scalars.get(values, 0.0) + float(value)
                else:
                    family.scalars[values] = float(value)
        except Exception:
            self._warn_once(f"record:{name}", "Metric %s could not be recorded", name)

    def _get_or_create_family(
        self,
        kind: Literal["counter", "histogram", "gauge_latest", "gauge_sum"],
        name: str,
        label_names: tuple[str, ...],
        buckets: Iterable[float] | None,
    ) -> _Family | None:
        full = exported_name(name)
        if kind == "counter" and not full.endswith("_total"):
            full = f"{full}_total"
        existing = self._families.get(full)
        if existing is not None:
            if existing.kind != kind:
                self._warn_once(
                    f"kind:{full}",
                    "Metric %s is a %s; ignoring a %s write",
                    full,
                    existing.kind,
                    kind,
                )
                return None
            return existing
        with self._lock:
            existing = self._families.get(full)
            if existing is not None:
                return existing if existing.kind == kind else None
            for label in label_names:
                if not _LABEL_RE.match(label) or label.startswith("__") or label == "le":
                    raise ValueError(f"invalid label name {label!r} on {full}")
            resolved_bounds = (
                tuple(sorted(float(b) for b in buckets))
                if buckets is not None
                else (default_buckets(full) if kind == "histogram" else ())
            )
            fam = _Family(
                kind=kind,
                full_name=full,
                label_names=label_names,
                bounds=resolved_bounds,
            )
            self._families[full] = fam
            return fam

    def _resolve_label_values(
        self, name: str, family: _Family, labels: Mapping[str, Any]
    ) -> tuple[str, ...]:
        if not family.label_names:
            return ()
        unknown = set(labels) - set(family.label_names)
        if unknown:
            self._warn_once(
                f"labels:{name}",
                "Metric %s has labels %s; dropping %s",
                name,
                family.label_names,
                sorted(unknown),
            )
        values = tuple(_clean_label_value(labels.get(k, "")) for k in family.label_names)
        if values in family.seen:
            return values
        with self._lock:
            if values in family.seen:
                return values
            if len(family.seen) >= self._max_series:
                self._warn_once(
                    f"cap:{name}",
                    "Metric %s reached %d label sets; folding new ones into %s",
                    name,
                    self._max_series,
                    _OVERFLOW_LABEL,
                )
                return tuple(_OVERFLOW_LABEL for _ in family.label_names)
            family.seen.add(values)
        return values

    def _warn_once(self, key: str, message: str, *args: Any) -> None:
        if key in self._warned:
            return
        self._warned.add(key)
        logger.warning(message, *args)

    def to_prometheus(self) -> str:
        """Render Prometheus text exposition 0.0.4 across all families plus index lifecycle gauges."""
        lines: list[str] = []
        with self._lock:
            families = list(self._families.values())
            for fam in sorted(families, key=lambda f: f.full_name):
                prom_type = (
                    "counter"
                    if fam.kind == "counter"
                    else ("histogram" if fam.kind == "histogram" else "gauge")
                )
                lines.append(f"# HELP {fam.full_name} SSRA Assist metric {fam.full_name}")
                lines.append(f"# TYPE {fam.full_name} {prom_type}")
                if fam.kind == "histogram":
                    for label_vals, child in sorted(fam.histograms.items()):
                        base_pairs = [
                            f'{k}="{v}"' for k, v in zip(fam.label_names, label_vals, strict=False)
                        ]
                        for bound, cum_cnt in zip(
                            fam.bounds, child.bucket_counts[:-1], strict=False
                        ):
                            b_pairs = [
                                *base_pairs,
                                f'le="{bound:.1f}"' if bound.is_integer() else f'le="{bound}"',
                            ]
                            lines.append(
                                f"{fam.full_name}_bucket{{{','.join(b_pairs)}}} {cum_cnt:.1f}"
                            )
                        inf_pairs = [*base_pairs, 'le="+Inf"']
                        lines.append(
                            f"{fam.full_name}_bucket{{{','.join(inf_pairs)}}} {child.bucket_counts[-1]:.1f}"
                        )
                        suffix = f"{{{','.join(base_pairs)}}}" if base_pairs else ""
                        lines.append(f"{fam.full_name}_count{suffix} {child.count:.1f}")
                        lines.append(f"{fam.full_name}_sum{suffix} {child.total:.4f}")
                else:
                    for label_vals, val in sorted(fam.scalars.items()):
                        pairs = [
                            f'{k}="{v}"' for k, v in zip(fam.label_names, label_vals, strict=False)
                        ]
                        suffix = f"{{{','.join(pairs)}}}" if pairs else ""
                        lines.append(f"{fam.full_name}{suffix} {val:.1f}")
        lines.extend(_index_lifecycle_prometheus_metrics())
        return "\n".join(lines) + "\n"

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON dashboard view (`uptime_seconds`, `counters`, `gauges`, `histograms` with `p50`/`p95`/`p99`)."""
        counters: dict[str, int | float] = {}
        gauges: dict[str, int | float] = {}
        histograms: dict[str, dict[str, int | float]] = {}
        with self._lock:
            for fam in self._families.values():
                if fam.kind == "counter":
                    for label_vals, val in fam.scalars.items():
                        counters[_snapshot_key(fam.full_name, fam.label_names, label_vals)] = (
                            _number(val)
                        )
                elif fam.kind in ("gauge_latest", "gauge_sum"):
                    for label_vals, val in fam.scalars.items():
                        gauges[_snapshot_key(fam.full_name, fam.label_names, label_vals)] = _number(
                            val
                        )
                elif fam.kind == "histogram":
                    for label_vals, child in fam.histograms.items():
                        if child.count <= 0:
                            continue
                        buckets = [
                            *zip(fam.bounds, child.bucket_counts[:-1], strict=False),
                            (float("inf"), child.bucket_counts[-1]),
                        ]
                        summary: dict[str, int | float] = {
                            "count": _number(child.count),
                            "sum": round(child.total, 4),
                            "avg": round(child.total / child.count, 4),
                        }
                        for q_name, q_val in _QUANTILES:
                            summary[q_name] = round(bucket_quantile(q_val, buckets, child.count), 4)
                        histograms[_snapshot_key(fam.full_name, fam.label_names, label_vals)] = (
                            summary
                        )
        return {
            "uptime_seconds": round(time.time() - self._start_time, 1),
            "counters": counters,
            "gauges": gauges,
            "histograms": histograms,
        }


def _snapshot_key(full_name: str, label_names: tuple[str, ...], label_vals: tuple[str, ...]) -> str:
    base = full_name[len(NAMESPACE) :] if full_name.startswith(NAMESPACE) else full_name
    if not label_names:
        return base
    inner = ",".join(f'{k}="{v}"' for k, v in zip(label_names, label_vals, strict=False))
    return f"{base}{{{inner}}}"


_qdrant_lifecycle_observation: dict[str, int | float] | None = None


def record_qdrant_lifecycle_observation(
    *,
    index_fresh: bool,
    index_drift: bool,
    observed_at_epoch_seconds: float,
    rebuild_failed: bool = False,
    rebuild_timestamp_seconds: float = 0.0,
    backup_required: bool = False,
    backup_failed: bool = False,
    backup_timestamp_seconds: float = 0.0,
    restore_drill_failed: bool = False,
    restore_drill_timestamp_seconds: float = 0.0,
) -> None:
    """Record a trusted Qdrant / KnowledgeSnapshot lifecycle observation with its observation timestamp."""
    global _qdrant_lifecycle_observation
    _qdrant_lifecycle_observation = {
        "ssra_qdrant_index_fresh": int(bool(index_fresh)),
        "ssra_qdrant_index_drift": int(bool(index_drift)),
        "ssra_qdrant_index_status_timestamp_seconds": round(float(observed_at_epoch_seconds), 1),
        "ssra_qdrant_rebuild_failed": int(bool(rebuild_failed)),
        "ssra_qdrant_rebuild_timestamp_seconds": round(float(rebuild_timestamp_seconds), 1),
        "ssra_qdrant_backup_required": int(bool(backup_required)),
        "ssra_qdrant_backup_failed": int(bool(backup_failed)),
        "ssra_qdrant_backup_timestamp_seconds": round(float(backup_timestamp_seconds), 1),
        "ssra_qdrant_restore_drill_failed": int(bool(restore_drill_failed)),
        "ssra_qdrant_restore_drill_timestamp_seconds": round(
            float(restore_drill_timestamp_seconds), 1
        ),
    }


def _index_lifecycle_prometheus_metrics() -> list[str]:
    """Render Qdrant / KnowledgeSnapshot lifecycle gauges only when a trusted observation has been recorded."""
    if _qdrant_lifecycle_observation is None:
        return []
    lines: list[str] = []
    for name, value in _qdrant_lifecycle_observation.items():
        lines.append(f"# HELP {name} {_LIFECYCLE_HELP[name]}")
        lines.append(f"# TYPE {name} gauge")
        lines.append(f"{name} {value}")
    return lines


metrics = MetricsStore()

MetricSpec = tuple[str, str, tuple[float, ...] | None]


def record_mapped(
    table: Mapping[str, MetricSpec],
    key: str,
    value: float = 1.0,
    labels: Mapping[str, Any] | None = None,
) -> None:
    """Record `value` against `table[key]`: a counter, up/down gauge, or histogram."""
    spec = table.get(key)
    if spec is None:
        return
    kind, name, buckets = spec
    if kind == "gauge":
        metrics.add_gauge(name, value, labels)
    elif kind == "histogram":
        metrics.observe(name, value, labels, buckets=buckets)
    else:
        metrics.inc(name, value, labels)


_OUTCOME_BY_MODE: dict[str, str] = {
    "blocked": "blocked",
    "out_of_scope": "out_of_scope",
    "out_of_jurisdiction": "out_of_scope",
    "abstained": "abstained",
    "false_premise_rejected": "abstained",
    "clarification": "clarification",
    "escalated": "escalated",
}

_DECISION_LOCALES = frozenset({"en", "pga", "ar", "din", "nus", "bfa", "zne", "shk"})
_DECISION_SOURCES = frozenset(
    {
        "explicit_request",
        "client_explicit",
        "continuity",
        "switched",
        "detected",
        "profile",
        "default",
    }
)


def turn_outcome(result: Mapping[str, Any]) -> str:
    """Classify how a chat turn ended for containment, abstention, and escalation SLIs."""
    mode = str(result.get("retrieval_mode") or "")
    outcome = _OUTCOME_BY_MODE.get(mode)
    if outcome and outcome != "escalated":
        return outcome
    if outcome == "escalated" or result.get("escalation_required") or result.get("handoff"):
        return "escalated"
    return "answered"


def record_language_decision(result: Mapping[str, Any], *, channel: str) -> None:
    """Record why a turn was answered in its language (`ssra_language_decisions_total`)."""
    source = str(result.get("locale_source") or "")
    if not source:
        return
    locale = str(result.get("locale") or "")
    metrics.inc(
        "language_decisions_total",
        labels={
            "channel": channel,
            "locale": locale if locale in _DECISION_LOCALES else "other",
            "source": source if source in _DECISION_SOURCES else "other",
        },
    )


def record_chat_turn(
    result: Mapping[str, Any],
    *,
    elapsed_ms: float,
    channel: str,
    error: bool = False,
) -> None:
    """Record one completed chat turn across any transport (`rest`, `sse`, `ws`, `voice`, `call`)."""
    outcome = "error" if error else turn_outcome(result)
    mode = str(result.get("retrieval_mode") or "hybrid")
    metrics.inc("chat_turns_total", labels={"channel": channel, "outcome": outcome})
    metrics.inc("retrieval_mode_total", labels={"mode": mode})
    if elapsed_ms > 0:
        metrics.observe(
            "chat_response_time_ms", elapsed_ms, labels={"channel": channel, "mode": mode}
        )
    faith = result.get("faithfulness_score")
    if faith is not None:
        try:
            metrics.observe("faithfulness_score", float(faith))
        except (TypeError, ValueError):
            pass
    record_language_decision(result, channel=channel)
    if outcome == "escalated" or (
        not error and (result.get("escalation_required") or result.get("handoff"))
    ):
        metrics.inc("escalation_required_total", labels={"channel": channel})


def route_label_from_scope(scope: Mapping[str, Any]) -> str:
    """Return the matched FastAPI/Starlette route template (`/v1/cases/{case_id}`), or `__unmatched__`."""
    route = scope.get("route")
    template = getattr(route, "path", None) or getattr(route, "path_format", None)
    return str(template) if template else _UNMATCHED_ROUTE


# ---------------------------------------------------------------------------
# OWASP ASVS 5.0 V16 Security Events (`FinalYearProject/App/backend/app/security_events.py`)
# ---------------------------------------------------------------------------
EVENT_BY_STATUS: dict[int, str] = {
    401: "authn_login_fail",
    403: "authz_fail",
    413: "input_validation_payload_too_large",
    429: "excess_rate_limit_exceeded",
}

MCP_SECURITY_EVENT_KINDS: frozenset[str] = frozenset(
    {
        "mcp_integrity_fail",
        "mcp_output_blocked",
        "mcp_idempotency_conflict",
        "mcp_request_state_fail",
    }
)


def record_security_event(event: str, *, reason: str = "", **fields: Any) -> None:
    """Log a structured OWASP security event at WARNING and increment `ssra_security_events_total`."""
    metrics.inc("security_events_total", labels={"event": event})
    security_logger.warning(
        "security event %s%s",
        event,
        f" ({reason})" if reason else "",
        extra={"event": event, "security_reason": reason, **fields},
    )


def record_mcp_security_event(
    kind: str,
    *,
    tool_name: str = "",
    namespace: str = "",
    reason: str = "",
    actor: str = "",
) -> None:
    """Record a bounded MCP boundary security event."""
    safe_kind = kind if kind in MCP_SECURITY_EVENT_KINDS else "mcp_integrity_fail"
    record_security_event(
        safe_kind,
        reason=reason,
        tool_name=tool_name,
        namespace=namespace,
        actor=actor,
    )


def record_http_security_event(
    *,
    method: str,
    status_code: int,
    route: str,
    reason: str = "",
    actor: str = "",
) -> None:
    """Record an OWASP security event for HTTP 401, 403, 413, or 429 responses."""
    event = EVENT_BY_STATUS.get(status_code)
    if event is None:
        return
    record_security_event(
        event,
        reason=reason,
        http_method=method if method in _KNOWN_METHODS else "OTHER",
        http_route=route,
        http_status=status_code,
        actor=actor,
    )


# ---------------------------------------------------------------------------
# Client Real-User Monitoring (RUM) Telemetry (`FinalYearProject/App/backend/app/client_telemetry.py`)
# ---------------------------------------------------------------------------
MAX_TELEMETRY_BODY_BYTES = 16_384
_ID_SEGMENT_RE = re.compile(r"/(?:[0-9a-fA-F-]{8,}|\d+|[A-Za-z0-9_-]{24,})(?=/|$)")


class WebVital(BaseModel):
    """One Core Web Vitals measurement reported by the browser."""

    model_config = ConfigDict(extra="forbid")

    name: Literal["LCP", "INP", "CLS", "FCP", "TTFB"]
    value: float = Field(..., ge=0, le=600_000)
    rating: Literal["good", "needs-improvement", "poor"]
    route: str = Field("", max_length=200)
    navigation_type: str = Field("", max_length=32)


class WebVitalsBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metrics: list[WebVital] = Field(..., min_length=1, max_length=20)


class ClientError(BaseModel):
    """Uncaught client error or error-boundary report (deliberately forbids `message` to prevent PII leakage)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["error", "unhandledrejection", "boundary", "global-boundary"]
    name: str = Field("", max_length=80)
    digest: str = Field("", max_length=64)
    source: str = Field("", max_length=200)
    route: str = Field("", max_length=200)


def normalise_route(path: str) -> str:
    """Normalize a client pathname into a bounded metric label (`:id` folded, <= 3 segments, no query/hash)."""
    clean = (path or "/").split("?", 1)[0].split("#", 1)[0] or "/"
    if not clean.startswith("/"):
        clean = "/" + clean
    clean = _ID_SEGMENT_RE.sub("/:id", clean)
    parts = [part for part in clean.split("/") if part][:3]
    return "/" + "/".join(parts)


def record_web_vitals(batch: WebVitalsBatch) -> int:
    """Record every measurement in `batch` into `ssra_web_vitals_ms` or `ssra_web_vitals_cls`."""
    for vital in batch.metrics:
        route = normalise_route(vital.route)
        if vital.name == "CLS":
            metrics.observe(
                "web_vitals_cls",
                vital.value,
                labels={"rating": vital.rating, "route": route},
                buckets=_CLS_BUCKETS,
            )
        else:
            metrics.observe(
                "web_vitals_ms",
                vital.value,
                labels={"metric": vital.name, "rating": vital.rating, "route": route},
            )
    return len(batch.metrics)


def record_client_error(report: ClientError) -> None:
    """Record a client error metric and structured WARNING log without any user message text."""
    route = normalise_route(report.route)
    metrics.inc("client_errors_total", labels={"kind": report.kind, "route": route})
    client_logger.warning(
        "client error %s on %s",
        report.kind,
        route,
        extra={
            "event": "client.error",
            "client_error_kind": report.kind,
            "client_error_name": report.name,
            "client_error_digest": report.digest,
            "client_error_source": report.source.split("?", 1)[0],
            "http_route": route,
        },
    )


# ---------------------------------------------------------------------------
# Turn Provenance & Digest Builder (`FinalYearProject/App/backend/app/audit/turns.py`)
# ---------------------------------------------------------------------------
TURN_PAYLOAD_SCHEMA = 2
_MAX_LISTED_ARTIFACTS = 10


def _hmac_sha256_hex(text: str, key: bytes) -> str:
    return hmac.new(key, (text or "").encode("utf-8"), hashlib.sha256).hexdigest()


def _resolve_audit_hmac_key(explicit_key: str | bytes | None = None) -> bytes:
    if isinstance(explicit_key, bytes) and explicit_key:
        return explicit_key
    if isinstance(explicit_key, str) and explicit_key.strip():
        return explicit_key.strip().encode("utf-8")
    env_key = os.getenv("SSRA_AUDIT_HMAC_KEY", "").strip()
    if env_key:
        return env_key.encode("utf-8")
    raise ValueError(
        "SSRA_AUDIT_HMAC_KEY or explicit audit_hmac_key is required for turn audit digests"
    )


def build_turn_audit_record(
    *,
    message: str,
    reply: str,
    channel: str,
    locale: str,
    locale_source: str = "default",
    retrieval_mode: str = "hybrid",
    tool_calls: Iterable[Mapping[str, Any]] = (),
    citations: Iterable[Mapping[str, Any] | Any] = (),
    input_tokens: int = 0,
    output_tokens: int = 0,
    knowledge_snapshot: str = "2026.10.1",
    audit_hmac_key: str | bytes | None = None,
) -> dict[str, Any]:
    """Construct a keyed HMAC-SHA256 digest audit payload for a completed turn (`TURN_PAYLOAD_SCHEMA = 2`)."""
    key_bytes = _resolve_audit_hmac_key(audit_hmac_key)
    tool_digests: list[dict[str, Any]] = []
    for call in list(tool_calls)[:_MAX_LISTED_ARTIFACTS]:
        args = call.get("arguments")
        tool_digests.append(
            {
                "name": str(call.get("name") or "")[:80],
                "iteration": int(call.get("iteration") or 0),
                "arguments_sha256": _hmac_sha256_hex(
                    json.dumps(args, sort_keys=True, default=str), key_bytes
                )
                if args
                else "",
            }
        )
    citation_digests: list[str] = []
    for cit in list(citations)[:_MAX_LISTED_ARTIFACTS]:
        dump_fn = getattr(cit, "model_dump", None)
        dumped = dump_fn() if callable(dump_fn) else cit
        cit_dict: dict[str, Any] = (
            dict(dumped) if isinstance(dumped, Mapping) else {"passage": str(cit)}
        )
        key = "|".join(
            str(cit_dict.get(field, "") or "")
            for field in ("doc_id", "section", "title", "snippet")
        )
        citation_digests.append(_hmac_sha256_hex(key, key_bytes))
    return {
        "schema": TURN_PAYLOAD_SCHEMA,
        "channel": channel,
        "locale": locale,
        "locale_source": locale_source,
        "retrieval_mode": retrieval_mode,
        "question_sha256": _hmac_sha256_hex(message, key_bytes),
        "reply_sha256": _hmac_sha256_hex(reply, key_bytes),
        "tool_calls": tool_digests,
        "citation_digests": citation_digests,
        "usage": {
            "input_tokens": max(0, int(input_tokens)),
            "output_tokens": max(0, int(output_tokens)),
        },
        "provenance": {
            "app_version": os.getenv("APP_VERSION", "2026.10.1"),
            "knowledge_snapshot": knowledge_snapshot,
        },
    }
