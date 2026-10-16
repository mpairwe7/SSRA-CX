"""Phase 4 Consent-Checked Reminder Campaigns & Upstream Reconciliation Polling (`services/workers/src/ssra_workers/campaigns.py` — Sections 3, 10.2, 11)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ssra_core import compute_monthly_filing_deadline


@dataclass(frozen=True)
class ReminderCandidate:
    subject_ref: str
    channel: str
    locale: str
    opt_in_granted: bool
    stop_revoked: bool


@dataclass(frozen=True)
class CampaignDispatchSummary:
    tax_period: str
    deadline_eat_iso: str
    template_id: str
    dispatched_subjects: tuple[str, ...]
    skipped_no_consent_subjects: tuple[str, ...]


def run_consent_checked_filing_reminder_campaign(
    *,
    tax_period_year: int,
    tax_period_month: int,
    candidates: list[ReminderCandidate],
    template_id: str = "ssra_filing_reminder_v1",
) -> CampaignDispatchSummary:
    """Hard Non-Goal enforcement: Never send an outbound message without active opt-in consent."""
    deadline: datetime = compute_monthly_filing_deadline(tax_period_year, tax_period_month, 15)
    dispatched: list[str] = []
    skipped: list[str] = []

    for c in candidates:
        if c.opt_in_granted and not c.stop_revoked:
            dispatched.append(c.subject_ref)
        else:
            skipped.append(c.subject_ref)

    return CampaignDispatchSummary(
        tax_period=f"{tax_period_year:04d}-{tax_period_month:02d}",
        deadline_eat_iso=deadline.isoformat(),
        template_id=template_id,
        dispatched_subjects=tuple(dispatched),
        skipped_no_consent_subjects=tuple(skipped),
    )
