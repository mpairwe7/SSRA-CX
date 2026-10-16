"""Resilience primitives: per-upstream circuit breakers, per-channel bulkheads, and idempotent-only retries (Section 8.3, 10.1, 13)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from ssra_core.clock import utc_now
from ssra_core.contracts import ChannelName
from ssra_core.errors import McpErrorCode, SSRAError


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class UpstreamCircuitBreaker:
    """Per-upstream circuit breaker preventing cascading failures when e-Tax or e-Customs is degraded."""

    def __init__(
        self,
        *,
        upstream_name: str,
        failure_threshold: int = 3,
        recovery_timeout_seconds: int = 30,
    ) -> None:
        self.upstream_name = upstream_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: datetime | None = None

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

    def record_failure(self, now: datetime | None = None) -> None:
        self._failure_count += 1
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = now or utc_now()

    def call[T](self, fn: Callable[[], T]) -> T:
        if self.state == CircuitState.OPEN:
            raise SSRAError(
                McpErrorCode.UPSTREAM_UNAVAILABLE,
                f"Circuit breaker OPEN for upstream '{self.upstream_name}'",
                status_code=503,
            )
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
