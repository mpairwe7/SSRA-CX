"""Domain entities for conversations & Phase 3 Staff Copilot bounded context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OfficerResolutionArtifact:
    officer_id: str
    resolution_summary: str
    approved_next_intent: str = "guided_filing_and_payment"
    return_to_ai_step: int = 1


@dataclass(frozen=True)
class ConversationEntity:
    id: str
    channel: str
    locale: str
    subject_ref: str | None
    auth_level: str
    started_at: datetime
    office_code: str = "JUBA_HQ"
    status: str = "ACTIVE"  # ACTIVE | STAFF_TAKEOVER | HANDED_BACK_TO_AI | CLOSED
    assigned_staff_id: str | None = None
    qa_score: float | None = None
    officer_resolution: OfficerResolutionArtifact | None = None


@dataclass(frozen=True)
class StaffCopilotDraft:
    conversation_id: str
    summary: str
    cited_reply_draft: str
    citations: tuple[str, ...]
    next_best_action: str
    snapshot_version: str = "2026.10.1"
