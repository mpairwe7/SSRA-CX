"""Application use cases for conversations & Phase 3 Staff Copilot bounded context."""

from __future__ import annotations

from ssra_core import new_id, utc_now

from ssra_api.conversations.domain import ConversationEntity
from ssra_api.outbox import get_outbox_store


def create_conversation_use_case(
    *,
    channel: str,
    locale: str,
    subject_ref: str | None = None,
    auth_level: str = "ANONYMOUS",
    office_code: str = "JUBA_HQ",
) -> ConversationEntity:
    """Create a new `ConversationEntity` and stage a creation domain event."""
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
