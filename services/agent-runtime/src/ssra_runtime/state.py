"""LangGraph conversation state definition (Section 6.2)."""

from __future__ import annotations

from typing import Any, TypedDict

from ssra_core import (
    Answer,
    AuthLevel,
    ChannelCapabilities,
    ChannelName,
    Citation,
    HandoffTicket,
    Intent,
    LocaleCode,
    RiskTier,
)

from ssra_runtime.schemas import PendingConfirmation, ToolArtifact, TurnBudget


class ConversationGraphState(TypedDict, total=False):
    thread_id: str
    channel: ChannelName
    locale: LocaleCode
    capabilities: ChannelCapabilities
    auth_level: AuthLevel
    subject_ref: str | None
    raw_user_text: str
    redacted_user_text: str
    confirmation_token_in: str | None
    idempotency_key_in: str | None
    deterministic_handled: bool
    intent: Intent | None
    slots: dict[str, Any]
    tier: RiskTier
    policy_decision: str  # ALLOW | DENY | STEP_UP | HANDOFF
    selected_subgraph: str
    pending_confirmation: PendingConfirmation | None
    artifacts: list[ToolArtifact]
    citations: list[Citation]
    budget: TurnBudget
    safety_flags: list[str]
    handoff_state: HandoffTicket | None
    answer: Answer | None
    regeneration_count: int
    validator_feedback: str | None
    running_summary: str
    audit_event_hash: str
