"""Case & Handoff SLA timer evaluation in Africa/Juba time (Section 10.2 & 17)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ssra_core import juba_now

SLA_HOURS_BY_PRIORITY: dict[str, int] = {
    "CRITICAL": 2,
    "HIGH": 4,
    "NORMAL": 24,
    "LOW": 48,
}


@dataclass(frozen=True)
class CaseSlaEvaluation:
    case_id: str
    priority: str
    sla_due_eat: datetime
    is_breached: bool
    escalate_to_supervisor: bool


def evaluate_case_sla(
    *,
    case_id: str,
    priority: str,
    created_at_utc: datetime,
    now_utc: datetime | None = None,
) -> CaseSlaEvaluation:
    created_eat = juba_now(created_at_utc)
    current_eat = juba_now(now_utc)
    hours = SLA_HOURS_BY_PRIORITY.get(priority.upper(), 24)
    due_eat = created_eat + timedelta(hours=hours)
    breached = current_eat > due_eat
    return CaseSlaEvaluation(
        case_id=case_id,
        priority=priority.upper(),
        sla_due_eat=due_eat,
        is_breached=breached,
        escalate_to_supervisor=breached,
    )
