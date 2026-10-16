"""Specialist subgraph: self_service (T1 personal reads & T2/T3 confirmed writes — Section 6.1)."""

from __future__ import annotations

from typing import Any

from ssra_core import AuthLevel, IntentName

from ssra_runtime.schemas import PendingConfirmation, ToolArtifact
from ssra_runtime.state import ConversationGraphState
from ssra_runtime.tools import GovernedMcpGatewayClient


def execute_self_service_subgraph(
    state: ConversationGraphState,
    gateway: GovernedMcpGatewayClient,
) -> dict[str, Any]:
    intent = state.get("intent")
    intent_name = intent.intent if intent else IntentName.GET_BALANCE
    slots = state.get("slots", {})
    auth_level = state.get("auth_level", AuthLevel.ANONYMOUS)
    subject_ref = state.get("subject_ref")
    thread_id = state.get("thread_id", "thr_default")
    artifacts: list[ToolArtifact] = list(state.get("artifacts", []))

    # Microsoft agent-framework#8132: If resuming a pending confirmation with confirmation_token_in, preserve it for confirm_node
    existing_pending = state.get("pending_confirmation")
    if existing_pending is not None and state.get("confirmation_token_in"):
        return {"pending_confirmation": existing_pending, "artifacts": artifacts}

    if intent_name == IntentName.GET_BALANCE:
        art = gateway.invoke_tool(
            server_name="ledger",
            tool_name="get_balance",
            arguments={},
            auth_level=auth_level,
            subject_ref=subject_ref,
        )
        artifacts.append(art)
        return {"artifacts": artifacts}

    if intent_name == IntentName.GET_FILING_STATUS:
        art = gateway.invoke_tool(
            server_name="ledger",
            tool_name="get_filing_status",
            arguments={},
            auth_level=auth_level,
            subject_ref=subject_ref,
        )
        artifacts.append(art)
        return {"artifacts": artifacts}

    if intent_name == IntentName.GET_TCC_STATUS:
        art = gateway.invoke_tool(
            server_name="tcc",
            tool_name="get_tcc_status",
            arguments={},
            auth_level=auth_level,
            subject_ref=subject_ref,
        )
        artifacts.append(art)
        return {"artifacts": artifacts}

    if intent_name == IntentName.REPORT_SCAM:
        args = {
            "suspected_identifier": str(
                slots.get("suspected_identifier", "+211-UNVERIFIED-COLLECTOR")
            ),
            "summary": str(slots.get("summary", "Suspected collector scam report")),
        }
        rec = gateway.confirmation_manager.issue_token(
            conversation_id=thread_id,
            tool_name="report_scam",
            arguments=args,
            subject_ref=subject_ref,
        )
        return {
            "pending_confirmation": PendingConfirmation(
                token=rec.token,
                idempotency_key=rec.idempotency_key,
                server="official-channels",
                tool="report_scam",
                arguments=args,
                action_digest=rec.action_digest,
                summary_text=f"Submit official scam report for identifier '{args['suspected_identifier']}' to SSRA SecOps.",
            )
        }

    if intent_name == IntentName.BOOK_APPOINTMENT:
        args = {
            "office_code": str(slots.get("office_code", "JUBA_HQ")),
            "slot_id": str(slots.get("slot_id", "slot_2026_10_20_0900")),
        }
        rec = gateway.confirmation_manager.issue_token(
            conversation_id=thread_id,
            tool_name="book_appointment",
            arguments=args,
            subject_ref=subject_ref,
        )
        return {
            "pending_confirmation": PendingConfirmation(
                token=rec.token,
                idempotency_key=rec.idempotency_key,
                server="appointments",
                tool="book_appointment",
                arguments=args,
                action_digest=rec.action_digest,
                summary_text=f"Book in-person appointment at {args['office_code']} (slot {args['slot_id']}).",
            )
        }

    return {"artifacts": artifacts}
