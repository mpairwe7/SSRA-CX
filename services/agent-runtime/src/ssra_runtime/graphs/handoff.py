"""Specialist subgraph: handoff & T4 human-only routing (Section 4 & 6.1)."""

from __future__ import annotations

from typing import Any

from ssra_core import (
    Answer,
    AnswerSegment,
    ChannelCapabilities,
    GenerativeUIComponent,
    GenerativeUIComponentName,
    HandoffTicket,
    RiskTier,
)

from ssra_runtime.state import ConversationGraphState


def execute_handoff_subgraph(state: ConversationGraphState) -> dict[str, Any]:
    if state.get("answer") is not None:
        return {}

    thread_id = state.get("thread_id", "thr_default")
    tier = state.get("tier", RiskTier.T0)
    decision = state.get("policy_decision", "HANDOFF")
    capabilities = state.get("capabilities", ChannelCapabilities())

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
        text = (
            "Connecting you to an SSRA Contact-Centre Officer. Office hours are Monday–Friday "
            "08:00–17:00 Africa/Juba time (UTC+02:00)."
        )
        ticket = HandoffTicket(
            conversation_id=thread_id,
            reason="USER_REQUEST",
            queue="DOMESTIC_TAX",
            summary="Taxpayer requested human handoff.",
            citations=[],
            priority="NORMAL",
        )

    return {
        "handoff_state": ticket,
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
