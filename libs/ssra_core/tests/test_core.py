"""Unit and Hypothesis property tests for ssra_core."""

from __future__ import annotations

from datetime import UTC, date, datetime

from hypothesis import given
from hypothesis import strategies as st
from ssra_core import (
    ChannelBulkhead,
    ChannelName,
    CircuitState,
    McpErrorCode,
    SSRAError,
    UpstreamCircuitBreaker,
    compute_monthly_filing_deadline,
    execute_with_idempotent_retry,
    expand_ssra_nra_synonyms,
    fiscal_year_for_date,
    is_within_juba_office_hours,
    new_id,
    new_uuid7,
    normalise_authority_mentions,
)


@given(
    ts1=st.integers(min_value=1, max_value=2**47 - 2),
    delta=st.integers(min_value=1, max_value=10_000_000),
)
def test_uuid7_monotonic_timestamp_ordering(ts1: int, delta: int) -> None:
    u1 = new_uuid7(ts1)
    u2 = new_uuid7(ts1 + delta)
    assert u1.version == 7
    assert u2.version == 7
    assert str(u1) < str(u2)


@given(
    year=st.integers(min_value=2022, max_value=2035),
    month=st.integers(min_value=1, max_value=12),
    due_day=st.integers(min_value=1, max_value=28),
)
def test_compute_monthly_filing_deadline_never_lands_on_weekend(
    year: int, month: int, due_day: int
) -> None:
    deadline = compute_monthly_filing_deadline(year, month, due_day)
    assert deadline.tzinfo is not None
    offset = deadline.utcoffset()
    assert offset is not None
    assert offset.total_seconds() == 7200  # Africa/Juba UTC+02:00 (since Feb 2021)
    assert deadline.weekday() < 5  # Monday (0) .. Friday (4)


def test_juba_office_hours_and_fiscal_year() -> None:
    # Monday 2026-10-19 07:00 UTC == 09:00 Africa/Juba (open)
    mon_open = datetime(2026, 10, 19, 7, 0, tzinfo=UTC)
    assert is_within_juba_office_hours(mon_open) is True

    # Saturday 2026-10-17 09:00 UTC (closed)
    sat_closed = datetime(2026, 10, 17, 9, 0, tzinfo=UTC)
    assert is_within_juba_office_hours(sat_closed) is False

    assert fiscal_year_for_date(date(2026, 6, 30)) == "2025/2026"
    assert fiscal_year_for_date(date(2026, 7, 1)) == "2026/2027"


def test_nra_ssra_synonyms_and_errors() -> None:
    expanded = expand_ssra_nra_synonyms("How do I get an NRA TIN certificate?")
    assert "SSRA" in expanded
    preserved = normalise_authority_mentions("Visit https://etax.nra.gov.ss to register with NRA")
    assert "https://etax.nra.gov.ss" in preserved
    assert "SSRA (NRA)" in preserved

    err = SSRAError(McpErrorCode.STEP_UP_REQUIRED, "Fresh OTP required", status_code=403)
    problem = err.to_problem_details(instance="/v1/tcc/request", trace_id="tr_123")
    assert problem.status == 403
    assert problem.code == McpErrorCode.STEP_UP_REQUIRED
    assert new_id("thr").startswith("thr_")


def test_circuit_breaker_idempotent_retries_and_channel_bulkhead() -> None:
    import pytest

    cb = UpstreamCircuitBreaker(upstream_name="etax", failure_threshold=2)
    assert cb.state == CircuitState.CLOSED
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    with pytest.raises(SSRAError) as cb_exc:
        cb.call(lambda: "ok")
    assert cb_exc.value.code == McpErrorCode.UPSTREAM_UNAVAILABLE

    # Idempotent retry retries up to max_attempts; non-idempotent never retries
    calls = 0

    def _flaky() -> str:
        nonlocal calls
        calls += 1
        if calls < 2:
            raise RuntimeError("transient")
        return "recovered"

    val, attempts = execute_with_idempotent_retry(_flaky, is_idempotent=True, max_attempts=3)
    assert val == "recovered"
    assert attempts == 2

    non_idem_calls = 0

    def _fail_non_idem() -> str:
        nonlocal non_idem_calls
        non_idem_calls += 1
        raise RuntimeError("write error")

    with pytest.raises(RuntimeError):
        execute_with_idempotent_retry(_fail_non_idem, is_idempotent=False, max_attempts=3)
    assert non_idem_calls == 1

    bulkhead = ChannelBulkhead(max_concurrent_per_channel=1)
    bulkhead.acquire(ChannelName.WHATSAPP)
    with pytest.raises(SSRAError) as bh_exc:
        bulkhead.acquire(ChannelName.WHATSAPP)
    assert bh_exc.value.code == McpErrorCode.RATE_LIMITED
    bulkhead.release(ChannelName.WHATSAPP)
