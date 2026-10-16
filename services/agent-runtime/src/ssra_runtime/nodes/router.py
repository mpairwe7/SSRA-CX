"""Node 2: deterministic_router — handle non-LLM flows first (OTP, USSD, STOP/HELP/AGENT)."""

from __future__ import annotations

from typing import Any

from ssra_core import (
    Answer,
    AnswerSegment,
    ChannelName,
    Citation,
    HandoffTicket,
    RiskTier,
)

from ssra_runtime.state import ConversationGraphState


def deterministic_router_node(state: ConversationGraphState) -> dict[str, Any]:
    raw = state.get("raw_user_text", "").strip()
    upper = raw.upper()
    thread_id = state.get("thread_id", "thr_default")
    channel = state.get("channel", ChannelName.WEB)

    # 1. Consent STOP keyword (Section 6.1 & 11)
    if upper in ("STOP", "UNSUBSCRIBE"):
        return {
            "deterministic_handled": True,
            "tier": RiskTier.T0,
            "policy_decision": "ALLOW",
            "answer": Answer(
                segments=[
                    AnswerSegment(
                        text=(
                            "Your opt-out (STOP) preference has been recorded by SSRA Assist. "
                            "You will no longer receive outbound notifications. Reply HELP at any time."
                        ),
                        citation_ids=[],
                    )
                ],
                citations=[],
                numbers=[],
                is_estimate=False,
                abstained=True,
            ),
        }

    # 2. Immediate human escalation keyword AGENT (Principle 6 & Section 11)
    if upper in ("AGENT", "HUMAN", "OFFICER"):
        ticket = HandoffTicket(
            conversation_id=thread_id,
            reason="USER_REQUEST",
            queue="DOMESTIC_TAX",
            summary="User requested immediate human agent via deterministic keyword.",
            citations=[],
            priority="NORMAL",
        )
        return {
            "deterministic_handled": True,
            "tier": RiskTier.T0,
            "policy_decision": "HANDOFF",
            "handoff_state": ticket,
            "answer": Answer(
                segments=[
                    AnswerSegment(
                        text=(
                            "Connecting you to an SSRA Contact-Centre Officer (Monday–Friday, "
                            "08:00–17:00 Africa/Juba time, or scheduling a callback outside office hours)."
                        ),
                        citation_ids=[],
                    )
                ],
                citations=[],
                numbers=[],
                is_estimate=False,
                abstained=True,
            ),
        }

    # 3. USSD synchronous deterministic menu path (<2s, no LLM in path — Section 11)
    if channel == ChannelName.USSD:
        cit = Citation(
            id="cit_ussd_etax",
            snapshot_version="2026.10.1",
            doc_title="SSRA e-Tax Portal Guide",
            section_anchor="Part-I-Sec-1-TIN-Registration",
            effective_from="2021-07-01",
            url="https://etax.nra.gov.ss/",
        )
        menu_text = (
            "SSRA Official Menu:\n"
            "1. TIN & eTax (etax.nra.gov.ss)\n"
            "2. Bank-Only Payment Rules\n"
            "3. Verify SSRA Sender\n"
            "0. Request Officer Callback"
        )[:182]
        return {
            "deterministic_handled": True,
            "tier": RiskTier.T0,
            "policy_decision": "ALLOW",
            "citations": [cit],
            "answer": Answer(
                segments=[AnswerSegment(text=menu_text, citation_ids=["cit_ussd_etax"])],
                citations=[cit],
                numbers=[],
                is_estimate=False,
                abstained=False,
            ),
        }

    return {"deterministic_handled": False}
