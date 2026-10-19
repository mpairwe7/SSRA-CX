"""Application layer for cases bounded context."""

from __future__ import annotations

from ssra_core import McpErrorCode, SSRAError, new_id, utc_now

from ssra_api.cases.domain import CaseEntity
from ssra_api.outbox import get_outbox_store

_case_store: dict[str, CaseEntity] = {
    "case_01": CaseEntity(
        id="case_01",
        subject_ref="sub_taxpayer_amina_01",
        case_type="INQUIRY",
        status="OPEN",
        priority="NORMAL",
        created_at=utc_now(),
    ),
    "case_seed_001": CaseEntity(
        id="case_seed_001",
        subject_ref="sub_taxpayer_amina_01",
        case_type="INQUIRY",
        status="IN_PROGRESS",
        priority="NORMAL",
        created_at=utc_now(),
    ),
}


def open_case_use_case(
    *, case_type: str, priority: str = "NORMAL", subject_ref: str | None = None
) -> CaseEntity:
    """Create a new taxpayer support case, persist it in the case repository, and stage a CloudEvent."""
    entity = CaseEntity(
        id=new_id("case"),
        subject_ref=subject_ref,
        case_type=case_type,
        status="OPEN",
        priority=priority,
        created_at=utc_now(),
    )
    _case_store[entity.id] = entity
    get_outbox_store().stage_domain_event(
        context_name="cases",
        event_type="ssra.case.opened.v1",
        subject=entity.id,
        data={"case_type": case_type, "priority": priority},
    )
    return entity


def record_maker_checker_approval_use_case(
    *,
    case_id: str,
    maker_staff_id: str,
    checker_staff_id: str,
    action_type: str,
    rationale: str,
) -> CaseEntity:
    """Verify the case exists and stage a two-officer Tier T3 maker-checker approval CloudEvent."""
    existing = _case_store.get(case_id)
    if existing is None:
        raise SSRAError(
            McpErrorCode.NOT_FOUND,
            f"Case '{case_id}' not found for maker-checker approval",
            status_code=404,
        )
    get_outbox_store().stage_domain_event(
        context_name="cases",
        event_type="ssra.case.maker_checker.approved.v1",
        subject=existing.id,
        data={
            "maker_staff_id": maker_staff_id,
            "checker_staff_id": checker_staff_id,
            "action_type": action_type,
            "rationale": rationale,
        },
    )
    return existing
