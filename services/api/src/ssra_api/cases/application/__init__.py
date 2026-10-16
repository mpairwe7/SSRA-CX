"""Application layer for cases bounded context."""

from __future__ import annotations

from ssra_core import new_id, utc_now

from ssra_api.cases.domain import CaseEntity


def open_case_use_case(
    *, case_type: str, priority: str = "NORMAL", subject_ref: str | None = None
) -> CaseEntity:
    return CaseEntity(
        id=new_id("case"),
        subject_ref=subject_ref,
        case_type=case_type,
        status="OPEN",
        priority=priority,
        created_at=utc_now(),
    )
