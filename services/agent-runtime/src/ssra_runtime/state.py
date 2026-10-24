"""LangGraph conversation state definition (Section 6.2 & October 2026 Agentic CX)."""

from __future__ import annotations

from typing import Any, TypedDict

from ssra_core import (
    AffectiveSnapshot,
    Answer,
    AuthLevel,
    ChannelCapabilities,
    ChannelName,
    Citation,
    EnglishRouterEnvelope,
    HandoffEnvelope,
    HandoffTicket,
    Intent,
    LocaleCode,
    Plan,
    RiskTier,
)

from ssra_runtime.schemas import PendingConfirmation, ToolArtifact, TurnBudget


class ConversationGraphState(TypedDict, total=False):
    thread_id: str
    channel: ChannelName
    locale: LocaleCode
    language_state: str
    language_candidate: LocaleCode | None
    capabilities: ChannelCapabilities
    auth_level: AuthLevel
    subject_ref: str | None
    raw_user_text: str
    redacted_user_text: str
    confirmation_token_in: str | None
    idempotency_key_in: str | None
    deterministic_handled: bool
    affective_state: AffectiveSnapshot | None
    english_router_envelope: EnglishRouterEnvelope | None
    prior_intent: str | None
    prior_slots: dict[str, Any]
    intent: Intent | None
    slots: dict[str, Any]
    tier: RiskTier
    plan: Plan | None
    workflow_stack: list[dict[str, Any]]
    policy_decision: str  # ALLOW | DENY | STEP_UP | HANDOFF
    selected_subgraph: str
    pending_confirmation: PendingConfirmation | None
    artifacts: list[ToolArtifact]
    outcome_verification: dict[str, Any] | None
    citations: list[Citation]
    budget: TurnBudget
    safety_flags: list[str]
    handoff_state: HandoffTicket | None
    handoff_envelope: HandoffEnvelope | None
    answer: Answer | None
    regeneration_count: int
    validator_feedback: str | None
    running_summary: str
    audit_event_hash: str
