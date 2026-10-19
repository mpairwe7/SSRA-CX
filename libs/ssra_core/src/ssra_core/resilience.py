"""Resilience primitives: circuit breakers with HALF_OPEN probe caps, bulkheads, idempotent retries & SLO burn-rate (Section 8.3, 10.1, 13)."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from ssra_core.clock import utc_now
from ssra_core.contracts import ChannelName, RiskTier
from ssra_core.errors import McpErrorCode, SSRAError


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class UpstreamCircuitBreaker:
    """Per-upstream circuit breaker with HALF_OPEN probe concurrency cap preventing stampedes."""

    def __init__(
        self,
        *,
        upstream_name: str,
        failure_threshold: int = 3,
        recovery_timeout_seconds: int = 30,
        max_half_open_probes: int = 1,
    ) -> None:
        self.upstream_name = upstream_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.max_half_open_probes = max(1, max_half_open_probes)
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: datetime | None = None
        self._half_open_in_flight = 0

    @property
    def state(self) -> CircuitState:
        if (
            self._state == CircuitState.OPEN
            and self._opened_at is not None
            and (utc_now() - self._opened_at) >= timedelta(seconds=self.recovery_timeout_seconds)
        ):
            self._state = CircuitState.HALF_OPEN
        return self._state

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        self._opened_at = None
        self._half_open_in_flight = 0

    def record_failure(self, now: datetime | None = None) -> None:
        self._failure_count += 1
        if self._state == CircuitState.HALF_OPEN or self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = now or utc_now()
            self._half_open_in_flight = 0

    def release_half_open_probe(self) -> None:
        self._half_open_in_flight = max(0, self._half_open_in_flight - 1)

    def acquire_call_permission(self) -> bool:
        """Verify circuit is CLOSED or acquire a bounded HALF_OPEN probe slot."""
        current_state = self.state
        if current_state == CircuitState.OPEN:
            raise SSRAError(
                McpErrorCode.UPSTREAM_UNAVAILABLE,
                f"Circuit breaker OPEN for upstream '{self.upstream_name}'",
                status_code=503,
            )
        is_probe = current_state == CircuitState.HALF_OPEN
        if is_probe:
            if self._half_open_in_flight >= self.max_half_open_probes:
                raise SSRAError(
                    McpErrorCode.UPSTREAM_UNAVAILABLE,
                    f"Circuit breaker HALF_OPEN probe limit ({self.max_half_open_probes}) reached for '{self.upstream_name}'",
                    status_code=503,
                )
            self._half_open_in_flight += 1
        return is_probe

    def call[T](self, fn: Callable[[], T]) -> T:
        self.acquire_call_permission()
        try:
            result = fn()
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise


def execute_with_idempotent_retry[T](
    fn: Callable[[], T],
    *,
    is_idempotent: bool,
    max_attempts: int = 3,
) -> tuple[T, int]:
    """Section 8.3, 10.1, 13: Retries are permitted ONLY when `is_idempotent` is True."""
    effective_max = max_attempts if is_idempotent else 1
    attempts = 0
    last_exc: Exception | None = None
    while attempts < effective_max:
        attempts += 1
        try:
            return fn(), attempts
        except Exception as exc:
            last_exc = exc
            if not is_idempotent or attempts >= effective_max:
                raise
    assert last_exc is not None
    raise last_exc


@dataclass
class ChannelBulkhead:
    """Per-channel concurrency bulkhead isolating Web, WhatsApp, SMS, USSD, and Voice pools."""

    max_concurrent_per_channel: int = 50

    def __post_init__(self) -> None:
        self._in_flight: dict[ChannelName, int] = {ch: 0 for ch in ChannelName}

    def acquire(self, channel: ChannelName) -> None:
        current = self._in_flight.get(channel, 0)
        if current >= self.max_concurrent_per_channel:
            raise SSRAError(
                McpErrorCode.RATE_LIMITED,
                f"Channel bulkhead saturated for '{channel.value}' ({current}/{self.max_concurrent_per_channel})",
                status_code=429,
            )
        self._in_flight[channel] = current + 1

    def release(self, channel: ChannelName) -> None:
        current = self._in_flight.get(channel, 0)
        self._in_flight[channel] = max(0, current - 1)


@dataclass(frozen=True)
class ChannelLatencySloEvaluation:
    channel: ChannelName
    tier: RiskTier
    within_slo: bool
    recommended_degradation_level: int
    violations: list[str]


def evaluate_channel_latency_slo(
    *,
    channel: ChannelName,
    tier: RiskTier,
    p95_ttft_ms: float,
    p95_total_ms: float,
    fast_burn_rate_1h: float = 1.0,
    slow_burn_rate_6h: float = 1.0,
) -> ChannelLatencySloEvaluation:
    """Evaluate Section 13 latency SLOs and Google SRE multi-window multi-burn-rate thresholds."""
    violations: list[str] = []
    if not all(
        math.isfinite(v) and v >= 0.0
        for v in (p95_ttft_ms, p95_total_ms, fast_burn_rate_1h, slow_burn_rate_6h)
    ):
        violations.append("Non-finite or negative latency/burn-rate metric")
        return ChannelLatencySloEvaluation(
            channel=channel,
            tier=tier,
            within_slo=False,
            recommended_degradation_level=4,
            violations=violations,
        )

    if channel == ChannelName.USSD:
        if p95_total_ms > 2000.0:
            violations.append(f"USSD p95_total_ms ({p95_total_ms:.1f}ms) > 2000.0ms SLO")
    elif channel == ChannelName.VOICE:
        if p95_total_ms > 1000.0:
            violations.append(f"Voice p95_total_ms ({p95_total_ms:.1f}ms) > 1000.0ms SLO")
    else:
        if p95_ttft_ms > 1500.0:
            violations.append(f"{channel.value} p95_ttft_ms ({p95_ttft_ms:.1f}ms) > 1500.0ms SLO")
        max_total = 5000.0 if tier in {RiskTier.T0, RiskTier.T1} else 8000.0
        if p95_total_ms > max_total:
            violations.append(
                f"{channel.value} {tier.value} p95_total_ms ({p95_total_ms:.1f}ms) > {max_total:.1f}ms SLO"
            )

    recommended_level = 1
    if fast_burn_rate_1h >= 14.4:
        violations.append(f"Fast error-budget burn rate ({fast_burn_rate_1h:.2f}x >= 14.4x)")
        recommended_level = 4
    elif slow_burn_rate_6h >= 6.0 or violations:
        if slow_burn_rate_6h >= 6.0:
            violations.append(f"Slow error-budget burn rate ({slow_burn_rate_6h:.2f}x >= 6.0x)")
        recommended_level = 2

    return ChannelLatencySloEvaluation(
        channel=channel,
        tier=tier,
        within_slo=len(violations) == 0,
        recommended_degradation_level=recommended_level,
        violations=violations,
    )
