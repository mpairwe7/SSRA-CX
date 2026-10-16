"""Node 10: confirm — T2/T3 action confirmation interrupt & single-use token binding (Section 6.1 & 8.3)."""

from __future__ import annotations

from typing import Any

from ssra_core import (
    Answer,
    AnswerSegment,
    AuthLevel,
    GenerativeUIComponent,
    GenerativeUIComponentName,
    RiskTier,
)

from ssra_runtime.schemas import PendingConfirmation
from ssra_runtime.state import ConversationGraphState
from ssra_runtime.tools import GovernedMcpGatewayClient


def confirm_or_execute_write_node(
    state: ConversationGraphState,
    gateway: GovernedMcpGatewayClient,
) -> dict[str, Any]:
    """For T2/T3 intents, issue a PendingConfirmation interrupt unless confirmation_token_in is provided."""
    tier = state.get("tier", RiskTier.T0)
    if tier not in (RiskTier.T2, RiskTier.T3):
        return {}

    pending = state.get("pending_confirmation")
    if pending is None:
        return {}

    token_in = state.get("confirmation_token_in")
    idem_in = state.get("idempotency_key_in")
    if not token_in or not idem_in:
        # Pause execution and return ConfirmActionSheet to the user
        confirm_answer = Answer(
            segments=[
                AnswerSegment(
                    text=(
                        f"Confirmation Required ({tier.value}): {pending.summary_text} "
                        f"Please confirm to proceed."
                    ),
                    citation_ids=[],
                )
            ],
            citations=[],
            numbers=[],
            ui_component=GenerativeUIComponent(
                name=GenerativeUIComponentName.CONFIRM_ACTION_SHEET,
                props={
                    "confirmation_token": pending.token,
                    "idempotency_key": pending.idempotency_key,
                    "tool": f"{pending.server}.{pending.tool}",
                    "action_digest": pending.action_digest,
                    "summary": pending.summary_text,
                },
            ),
            is_estimate=False,
            abstained=True,
        )
        return {"answer": confirm_answer}

    # User confirmed: execute the T2/T3 MCP tool with the single-use confirmation token
    art = gateway.invoke_tool(
        server_name=pending.server,
        tool_name=pending.tool,
        arguments={
            **pending.arguments,
            "confirmation_token": token_in,
            "idempotency_key": idem_in,
        },
        auth_level=state.get("auth_level", AuthLevel.ANONYMOUS),
        subject_ref=state.get("subject_ref"),
    )
    artifacts = [*list(state.get("artifacts", [])), art]
    return {
        "artifacts": artifacts,
        "pending_confirmation": None,
    }


__all__ = ["PendingConfirmation", "confirm_or_execute_write_node"]
