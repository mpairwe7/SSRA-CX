"""Reference-mode feedback capture for the analytics bounded context."""

from __future__ import annotations

from ssra_core import new_id

from ssra_api.analytics_api.domain import UserFeedbackItem

_feedback_store: list[UserFeedbackItem] = []


def record_user_feedback_use_case(
    *, conversation_id: str, csat: int, reason: str, locale: str
) -> UserFeedbackItem:
    """Capture feedback in process-local reference mode; production routes are gated off."""
    item = UserFeedbackItem(
        feedback_id=new_id("fbk"),
        conversation_id=conversation_id,
        csat=csat,
        reason=reason,
        locale=locale,
    )
    _feedback_store.append(item)
    return item
