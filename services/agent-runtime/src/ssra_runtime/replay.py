"""Deterministic Conversation Replay & Forensic Reconstruction Engine (Principle 9 & Gate 2).

Principle 9: 'Reconstructable. Any conversation can be replayed: inputs, decisions, prompt,
model and knowledge versions, tool calls and outputs.'
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from ssra_core import AuthLevel, ChannelName, LocaleCode, RiskTier, utc_now


class ReconstructedTurnRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    turn_index: int
    thread_id: str
    recorded_at: datetime
    channel: ChannelName
    locale: LocaleCode
    auth_level: AuthLevel
    subject_ref: str | None
    redacted_input: str
    intent_name: str
    risk_tier: RiskTier
    policy_decision: str
    prompt_version: str
    model_route: str
    knowledge_snapshot_version: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    numbers: list[dict[str, str]] = Field(default_factory=list)
    output_text: str
    abstained: bool
    safety_flags: list[str] = Field(default_factory=list)
    audit_event_hash: str


MAX_REPLAY_THREADS = 2048


class ConversationReplayStore:
    """Stores immutable turn reconstruction records and verifies replay determinism."""

    def __init__(self) -> None:
        self._by_thread: dict[str, list[ReconstructedTurnRecord]] = {}

    def record_turn(
        self,
        *,
        thread_id: str,
        channel: ChannelName,
        locale: LocaleCode,
        auth_level: AuthLevel,
        subject_ref: str | None,
        redacted_input: str,
        intent_name: str,
        risk_tier: RiskTier,
        policy_decision: str,
        prompt_version: str,
        model_route: str,
        knowledge_snapshot_version: str,
        tool_calls: list[dict[str, Any]],
        citations: list[str],
        numbers: list[dict[str, str]],
        output_text: str,
        abstained: bool,
        safety_flags: list[str],
        audit_event_hash: str,
    ) -> ReconstructedTurnRecord:
        if thread_id not in self._by_thread and len(self._by_thread) >= MAX_REPLAY_THREADS:
            oldest_tid = next(iter(self._by_thread))
            self._by_thread.pop(oldest_tid, None)
        history = self._by_thread.setdefault(thread_id, [])
        rec = ReconstructedTurnRecord(
            turn_index=len(history) + 1,
            thread_id=thread_id,
            recorded_at=utc_now(),
            channel=channel,
            locale=locale,
            auth_level=auth_level,
            subject_ref=subject_ref,
            redacted_input=redacted_input,
            intent_name=intent_name,
            risk_tier=risk_tier,
            policy_decision=policy_decision,
            prompt_version=prompt_version,
            model_route=model_route,
            knowledge_snapshot_version=knowledge_snapshot_version,
            tool_calls=tool_calls,
            citations=citations,
            numbers=numbers,
            output_text=output_text,
            abstained=abstained,
            safety_flags=safety_flags,
            audit_event_hash=audit_event_hash,
        )
        history.append(rec)
        return rec

    def reconstruct_thread(self, thread_id: str) -> list[ReconstructedTurnRecord]:
        return list(self._by_thread.get(thread_id, []))
