"""Specialist subgraph: handoff & T4 human-only routing with HandoffEnvelope v2 (Section 4 & 6.1)."""

from __future__ import annotations

from typing import Any

from ssra_core import (
    AffectiveSnapshot,
    Answer,
    AnswerSegment,
    AuthLevel,
    ChannelCapabilities,
    ChannelName,
    GenerativeUIComponent,
    GenerativeUIComponentName,
    HandoffEnvelope,
    HandoffTicket,
    LocaleCode,
    RiskTier,
)

from ssra_runtime.state import ConversationGraphState


def _build_localized_suggested_opener(locale: LocaleCode) -> str:
    """Return a taxpayer-friendly, localized officer opener without exposing internal queue/reason codes."""
    if locale == LocaleCode.AR:
        return (
            "مرحباً، أنا موظف في هيئة الإيرادات (SSRA) ولدي ملخص المحادثة الكامل من المساعد "
            "الذكي حتى لا تضطر لإعادة شرح طلبك."
        )
    if locale == LocaleCode.PGA:
        return (
            "Salam, ana muwazaf min SSRA wa indi kullu tafasil mawdu taki min SSRA Assist "
            "ashan ma ta'id كلامك من الأول."
        )
    return (
        "Hello, I am an SSRA officer and I already have the context from SSRA Assist so "
        "you do not need to repeat yourself."
    )


def execute_handoff_subgraph(state: ConversationGraphState) -> dict[str, Any]:
    """Build a structured HandoffTicket and HandoffEnvelope v2 for human officer escalation."""
    if state.get("answer") is not None:
        return {}

    thread_id = state.get("thread_id", "thr_default")
    tier = state.get("tier", RiskTier.T0)
    decision = state.get("policy_decision", "HANDOFF")
    capabilities = state.get("capabilities", ChannelCapabilities())
    channel = state.get("channel", ChannelName.WEB)
    locale = state.get("locale", LocaleCode.EN)
    auth_level = state.get("auth_level", AuthLevel.ANONYMOUS)
    affective = state.get("affective_state") or AffectiveSnapshot()
    raw_lang_state = state.get("language_state", "LOCKED")
    lang_state = (
        raw_lang_state
        if raw_lang_state in ("LOCKED", "CODE_SWITCHING", "CANDIDATE_SHIFT", "FALLBACK_EN")
        else "LOCKED"
    )

    if decision == "STEP_UP":
        text = (
            f"Verification Required ({tier.value}): Accessing personal taxpayer records or "
            "performing this action requires OTP verification bound to your TIN. Please complete "
            "OTP verification to continue, or speak with an SSRA officer."
        )
        ticket = HandoffTicket(
            conversation_id=thread_id,
            reason="USER_REQUEST",
            queue="ETAX_TECH",
            summary="Step-up OTP + TIN verification required for T1-T3 request.",
            citations=[],
            priority="NORMAL",
        )
    elif tier == RiskTier.T4:
        text = (
            "Human Officer Required (Tier T4): Penalty waivers, remissions, tax refunds, "
            "assessment disputes, and binding legal interpretations can only be reviewed by "
            "authorised SSRA officers under the Taxation Act 2009 and SSRA Act 2023. The "
            "virtual assistant cannot grant waivers or alter assessments. I am routing your "
            "request to an SSRA Domestic Tax Officer."
        )
        ticket = HandoffTicket(
            conversation_id=thread_id,
            reason="T4_POLICY",
            queue="DOMESTIC_TAX",
            summary="Tier T4 human-only request (waiver/remission/dispute/ruling).",
            citations=[],
            priority="HIGH",
        )
    else:
        is_eq = affective.primary_emotion in ("distressed", "frustrated") and (
            affective.intensity >= 0.80 or affective.frustration_velocity >= 0.45
        )
        text = (
            "Connecting you to an SSRA Contact-Centre Officer. Office hours are Monday–Friday "
            "08:00–17:00 Africa/Juba time (UTC+02:00)."
        )
        ticket = HandoffTicket(
            conversation_id=thread_id,
            reason="EQ_ESCALATION" if is_eq else "USER_REQUEST",
            queue="DOMESTIC_TAX",
            summary=(
                f"Empathetic priority handoff ({affective.primary_emotion})."
                if is_eq
                else "Taxpayer requested human handoff."
            ),
            citations=[],
            priority="HIGH" if is_eq else "NORMAL",
        )

    artifacts = state.get("artifacts", [])
    envelope = HandoffEnvelope(
        envelope_version="2.0",
        ticket=ticket,
        source_channel=channel,
        target_channel=ChannelName.CONSOLE,
        locale=locale,
        language_state=lang_state,
        subject_ref_masked=state.get("subject_ref"),
        auth_level=auth_level,
        affective_state=affective,
        verified_tool_artifacts=[
            {"id": a.id, "server": a.server, "tool": a.tool} for a in artifacts
        ],
        suggested_opener=_build_localized_suggested_opener(locale),
        return_to_ai_eligible=(tier != RiskTier.T4),
    )

    return {
        "handoff_state": ticket,
        "handoff_envelope": envelope,
        "answer": Answer(
            segments=[AnswerSegment(text=text[: capabilities.max_len], citation_ids=[])],
            citations=[],
            numbers=[],
            ui_component=GenerativeUIComponent(
                name=GenerativeUIComponentName.HANDOFF_CARD,
                props={
                    "queue": ticket.queue,
                    "reason": ticket.reason,
                    "priority": ticket.priority,
                },
            )
            if capabilities.rich_ui
            else None,
            is_estimate=False,
            abstained=True,
        ),
    }
