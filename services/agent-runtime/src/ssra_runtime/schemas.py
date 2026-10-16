"""Typed schemas for tool artifacts, confirmations, and turn budgets (Section 6.2)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from ssra_core import (
    Answer,
    AuthLevel,
    ChannelName,
    Citation,
    HandoffTicket,
    Intent,
    LocaleCode,
    RiskTier,
)


class TurnBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_tokens: int = 2048
    tokens_used: int = 0
    max_tool_calls: int = 16
    tool_calls_used: int = 0
    max_wall_time_ms: int = 8000


class ToolArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    server: str
    tool: str
    tier: RiskTier
    structured_content: dict[str, Any]
    provenance: dict[str, Any]
    data_classification: str


class PendingConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    idempotency_key: str
    server: str
    tool: str
    arguments: dict[str, Any]
    action_digest: str
    summary_text: str


class RuntimeTurnResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_id: str
    channel: ChannelName
    locale: LocaleCode
    auth_level: AuthLevel
    tier: RiskTier
    policy_decision: Literal["ALLOW", "DENY", "STEP_UP", "HANDOFF"]
    intent: Intent | None = None
    answer: Answer
    artifacts: list[ToolArtifact] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    pending_confirmation: PendingConfirmation | None = None
    handoff_ticket: HandoffTicket | None = None
    safety_flags: list[str] = Field(default_factory=list)
    audit_event_hash: str
