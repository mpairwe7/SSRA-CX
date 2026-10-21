"""Domain model for reference-mode taxpayer feedback."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UserFeedbackItem:
    """One feedback item held only by the local reference API process."""

    feedback_id: str
    conversation_id: str
    csat: int
    reason: str
    locale: str
