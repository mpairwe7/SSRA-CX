"""Time and fiscal calendar utilities for South Sudan (Africa/Juba, UTC+02:00)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

JUBA_TZ = ZoneInfo("Africa/Juba")


def utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(tz=UTC)


def juba_now(now_utc: datetime | None = None) -> datetime:
    """Convert a UTC datetime (or current time) to Africa/Juba (UTC+02:00)."""
    ref = now_utc or utc_now()
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=UTC)
    return ref.astimezone(JUBA_TZ)


def juba_today(now_utc: datetime | None = None) -> date:
    """Return current calendar date in Africa/Juba."""
    return juba_now(now_utc).date()


def compute_monthly_filing_deadline(
    tax_period_year: int,
    tax_period_month: int,
    deadline_day_of_following_month: int = 15,
) -> datetime:
    """Compute the statutory deadline in Africa/Juba (23:59:59 UTC+02:00) for a monthly tax period.

    If the statutory day falls on a Saturday (5) or Sunday (6), rolls forward to the next Monday.
    """
    if not (1 <= tax_period_month <= 12):
        raise ValueError("tax_period_month must be in 1..12")
    if not (1 <= deadline_day_of_following_month <= 28):
        raise ValueError("deadline_day_of_following_month must be in 1..28")

    if tax_period_month == 12:
        due_year = tax_period_year + 1
        due_month = 1
    else:
        due_year = tax_period_year
        due_month = tax_period_month + 1

    due_date = date(due_year, due_month, deadline_day_of_following_month)
    while due_date.weekday() in (5, 6):
        due_date += timedelta(days=1)

    return datetime.combine(due_date, time(23, 59, 59), tzinfo=JUBA_TZ)


def is_within_juba_office_hours(
    moment_utc: datetime | None = None,
    open_hour: int = 8,
    close_hour: int = 17,
) -> bool:
    """Check whether a timestamp falls within SSRA Juba office hours (Mon-Fri, 08:00-17:00 EAT)."""
    local_dt = juba_now(moment_utc)
    if local_dt.weekday() >= 5:
        return False
    return time(open_hour, 0) <= local_dt.time() < time(close_hour, 0)


def fiscal_year_for_date(target_date: date) -> str:
    """Return South Sudan fiscal year label (1 July to 30 June, e.g., '2026/2027')."""
    if target_date.month >= 7:
        return f"{target_date.year}/{target_date.year + 1}"
    return f"{target_date.year - 1}/{target_date.year}"
