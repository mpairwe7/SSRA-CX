"""Specialist subgraph: complaint_intake (minimal-data complaint and callback capture — Section 3 & 6.1)."""

from __future__ import annotations

from dataclasses import dataclass

from ssra_core import new_id

from ssra_runtime.guardrails import redact_pii


@dataclass(frozen=True)
class MinimalComplaintTicket:
    ticket_id: str
    category: str
    redacted_summary: str
    pii_tags_masked: list[str]
    office_code: str


def build_minimal_complaint_ticket(
    raw_summary: str,
    *,
    category: str = "COMPLAINT",
    office_code: str = "JUBA_HQ",
) -> MinimalComplaintTicket:
    redacted = redact_pii(raw_summary)
    return MinimalComplaintTicket(
        ticket_id=new_id("cmp"),
        category=category,
        redacted_summary=redacted.redacted_text[:500],
        pii_tags_masked=redacted.pii_tags,
        office_code=office_code,
    )
