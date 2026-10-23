"""Specialist subgraph: self_service (T1 personal reads & T2/T3 confirmed writes — Section 6.1)."""

from __future__ import annotations

from typing import Any

from ssra_core import AuthLevel, IntentName, SSRAError

from ssra_runtime.nodes.verifier import verify_plan_outcomes
from ssra_runtime.schemas import PendingConfirmation, ToolArtifact
from ssra_runtime.state import ConversationGraphState
from ssra_runtime.tools import GovernedMcpGatewayClient


def execute_self_service_subgraph(
    state: ConversationGraphState,
    gateway: GovernedMcpGatewayClient,
) -> dict[str, Any]:
    """Execute authenticated T1 read tools (including multi-step compound plans) or issue T2/T3 confirmation interrupts."""
    intent = state.get("intent")
    intent_name = intent.intent if intent else IntentName.GET_BALANCE
    slots = state.get("slots", {})
    auth_level = state.get("auth_level", AuthLevel.ANONYMOUS)
    subject_ref = state.get("subject_ref")
    thread_id = state.get("thread_id", "thr_default")
    budget = state.get("budget")
    plan = state.get("plan")
    artifacts: list[ToolArtifact] = list(state.get("artifacts", []))

    # Microsoft agent-framework#8132: If resuming a pending confirmation with confirmation_token_in, preserve it for confirm_node
    existing_pending = state.get("pending_confirmation")
    if existing_pending is not None and state.get("confirmation_token_in"):
        return {"pending_confirmation": existing_pending, "artifacts": artifacts, "budget": budget}

    # Multi-step or single-step autonomous execution for T1 read steps
    if intent_name in (
        IntentName.GET_BALANCE,
        IntentName.GET_FILING_STATUS,
        IntentName.GET_TCC_STATUS,
    ):
        planned_steps = list(plan.steps) if plan is not None else []
        t1_read_steps = [
            s
            for s in planned_steps
            if s
            in (
                "ledger.get_balance",
                "ledger.get_filing_status",
                "tcc.get_tcc_status",
                "customs.get_declaration_status",
            )
        ]
        if not t1_read_steps:
            default_map = {
                IntentName.GET_BALANCE: "ledger.get_balance",
                IntentName.GET_FILING_STATUS: (
                    "customs.get_declaration_status"
                    if slots.get("include_customs_declaration")
                    else "ledger.get_filing_status"
                ),
                IntentName.GET_TCC_STATUS: "tcc.get_tcc_status",
            }
            t1_read_steps = [default_map[intent_name]]
        failed_steps: list[str] = []
        for idx, step in enumerate(t1_read_steps):
            srv, tl = step.split(".", 1)
            try:
                art = gateway.invoke_tool(
                    server_name=srv,
                    tool_name=tl,
                    arguments={},
                    auth_level=auth_level,
                    subject_ref=subject_ref,
                    budget=budget,
                )
                artifacts.append(art)
            except SSRAError:
                if idx == 0:
                    raise
                failed_steps.append(step)
        verification = verify_plan_outcomes(plan, artifacts, failed_steps=failed_steps)
        staged_pending: PendingConfirmation | None = None
        if "cases.create_case" in planned_steps:
            case_args = {
                "case_type": str(slots.get("case_type", "INQUIRY")),
                "summary": str(
                    slots.get("summary", "Follow-up reconciliation case from balance check")
                ),
            }
            rec = gateway.confirmation_manager.issue_token(
                conversation_id=thread_id,
                tool_name="create_case",
                arguments=case_args,
                subject_ref=subject_ref,
            )
            staged_pending = PendingConfirmation(
                token=rec.token,
                idempotency_key=rec.idempotency_key,
                server="cases",
                tool="create_case",
                arguments=case_args,
                action_digest=rec.action_digest,
                summary_text=f"Create SSRA taxpayer support case ({case_args['case_type']}).",
            )
        elif "appointments.book_appointment" in planned_steps:
            appt_args = {
                "office_code": str(slots.get("office_code", "JUBA_HQ")),
                "slot_id": str(slots.get("slot_id", "slot_2026_10_20_0900")),
            }
            rec = gateway.confirmation_manager.issue_token(
                conversation_id=thread_id,
                tool_name="book_appointment",
                arguments=appt_args,
                subject_ref=subject_ref,
            )
            staged_pending = PendingConfirmation(
                token=rec.token,
                idempotency_key=rec.idempotency_key,
                server="appointments",
                tool="book_appointment",
                arguments=appt_args,
                action_digest=rec.action_digest,
                summary_text=f"Book in-person appointment at {appt_args['office_code']} (slot {appt_args['slot_id']}).",
            )
        result: dict[str, Any] = {
            "artifacts": artifacts,
            "budget": budget,
            "outcome_verification": verification.model_dump(mode="json"),
        }
        if staged_pending is not None:
            result["pending_confirmation"] = staged_pending
        return result

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

    if intent_name == IntentName.CREATE_CASE:
        args = {
            "case_type": str(slots.get("case_type", "INQUIRY")),
            "summary": str(slots.get("summary", "Taxpayer support case inquiry")),
        }
        rec = gateway.confirmation_manager.issue_token(
            conversation_id=thread_id,
            tool_name="create_case",
            arguments=args,
            subject_ref=subject_ref,
        )
        return {
            "pending_confirmation": PendingConfirmation(
                token=rec.token,
                idempotency_key=rec.idempotency_key,
                server="cases",
                tool="create_case",
                arguments=args,
                action_digest=rec.action_digest,
                summary_text=f"Create SSRA taxpayer support case ({args['case_type']}).",
            )
        }

    return {"artifacts": artifacts}
