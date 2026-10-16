"""Node 11: egress — update running summary and write hash-chained AuditEvent (Section 6.1 & 12.3)."""

from __future__ import annotations

from typing import Any

from ssra_security import HashChainedAuditLedger

from ssra_runtime.state import ConversationGraphState


def egress_node(
    state: ConversationGraphState,
    audit_ledger: HashChainedAuditLedger,
) -> dict[str, Any]:
    answer = state.get("answer")
    thread_id = state.get("thread_id", "thr_default")
    tier = state.get("tier")
    intent = state.get("intent")

    event = audit_ledger.append(
        actor="ssra-agent-runtime",
        on_behalf_of=state.get("subject_ref"),
        action="conversation.turn.egress",
        resource=f"thread://{thread_id}",
        payload={
            "channel": str(state.get("channel")),
            "locale": str(state.get("locale")),
            "intent": intent.intent.value if intent else "deterministic",
            "tier": tier.value if tier else "T0",
            "policy_decision": state.get("policy_decision", "ALLOW"),
            "artifact_ids": [a.id for a in state.get("artifacts", [])],
            "citation_ids": [c.id for c in (answer.citations if answer else [])],
            "abstained": answer.abstained if answer else True,
            "knowledge_snapshot": "2026.10.1",
            "prompt_version": "2026.10.1",
        },
    )

    prev_summary = state.get("running_summary", "")
    turn_note = f"[{intent.intent.value if intent else 'turn'}:{tier.value if tier else 'T0'}]"
    updated_summary = f"{prev_summary} {turn_note}".strip()[-500:]

    return {
        "running_summary": updated_summary,
        "audit_event_hash": event.hash,
    }
