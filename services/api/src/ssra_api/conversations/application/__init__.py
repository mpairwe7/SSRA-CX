"""Application use cases for conversations & Phase 3 Staff Copilot bounded context."""

from __future__ import annotations

from dataclasses import replace

from ssra_core import new_id, utc_now
from ssra_security import redact_pii

from ssra_api.conversations.domain import ConversationEntity, StaffCopilotDraft
from ssra_api.outbox import get_outbox_store


def create_conversation_use_case(
    *,
    channel: str,
    locale: str,
    subject_ref: str | None = None,
    auth_level: str = "ANONYMOUS",
    office_code: str = "JUBA_HQ",
) -> ConversationEntity:
    entity = ConversationEntity(
        id=new_id("conv"),
        channel=channel,
        locale=locale,
        subject_ref=subject_ref,
        auth_level=auth_level,
        office_code=office_code,
        started_at=utc_now(),
    )
    get_outbox_store().stage_domain_event(
        context_name="conversations",
        event_type="ssra.conversation.created.v1",
        subject=entity.id,
        data={"channel": channel, "locale": locale, "office_code": office_code},
    )
    return entity


def staff_takeover_use_case(entity: ConversationEntity, *, staff_id: str) -> ConversationEntity:
    updated = replace(entity, status="STAFF_TAKEOVER", assigned_staff_id=staff_id)
    get_outbox_store().stage_domain_event(
        context_name="conversations",
        event_type="ssra.conversation.staff_takeover.v1",
        subject=entity.id,
        data={"staff_id": staff_id, "office_code": entity.office_code},
    )
    return updated


def staff_handback_to_ai_use_case(entity: ConversationEntity) -> ConversationEntity:
    updated = replace(entity, status="HANDED_BACK_TO_AI", assigned_staff_id=None)
    get_outbox_store().stage_domain_event(
        context_name="conversations",
        event_type="ssra.conversation.handback.v1",
        subject=entity.id,
        data={"office_code": entity.office_code},
    )
    return updated


def generate_copilot_draft_use_case(
    *, conversation_id: str, taxpayer_question: str
) -> StaffCopilotDraft:
    redacted_q = redact_pii(taxpayer_question).redacted_text
    return StaffCopilotDraft(
        conversation_id=conversation_id,
        summary=f"Taxpayer inquiry regarding: {redacted_q[:120]}",
        cited_reply_draft=(
            "Per the SSRA e-Tax Portal Guide (Part-I-Sec-1-TIN-Registration) and March 2026 "
            "Cash-Free Directive (Sec-1-Cash-Free-Collection), all registration, filing, and "
            "bank payment remittance run exclusively through https://etax.nra.gov.ss/."
        ),
        citations=("Part-I-Sec-1-TIN-Registration", "Sec-1-Cash-Free-Collection"),
        next_best_action="Send cited guidance and verify whether taxpayer needs TIN OTP binding.",
    )


def score_conversation_qa_use_case(
    entity: ConversationEntity,
    *,
    accuracy: float,
    citations_complete: float,
    neutrality: float,
    language_quality: float,
) -> ConversationEntity:
    overall = round((accuracy + citations_complete + neutrality + language_quality) / 4.0, 4)
    return replace(entity, qa_score=overall)
