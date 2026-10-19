"""Node 5: policy_gate — OPA policy evaluation from auth_level, tier, channel, and safety flags (Section 6.1)."""

from __future__ import annotations

from typing import Any, Literal

from ssra_core import AuthLevel, IntentName, RiskTier

from ssra_runtime.state import ConversationGraphState

PolicyDecision = Literal["ALLOW", "DENY", "STEP_UP", "HANDOFF"]


def evaluate_opa_policy(
    *,
    tier: RiskTier,
    auth_level: AuthLevel,
    subject_ref: str | None,
    intent_name: IntentName | None,
    rate_limited: bool = False,
) -> PolicyDecision:
    """Deterministic Python evaluation matching ai/policies/policy_gate.rego."""
    if rate_limited:
        return "DENY"

    if tier == RiskTier.T4 or intent_name == IntentName.HUMAN_HANDOFF:
        return "HANDOFF"

    if tier == RiskTier.T0:
        return "ALLOW"

    if tier in (RiskTier.T1, RiskTier.T2):
        if (
            auth_level in (AuthLevel.T1_TIN_BOUND, AuthLevel.T3_STEP_UP, AuthLevel.STAFF_PASSKEY)
            and subject_ref is not None
        ):
            return "ALLOW"
        return "STEP_UP"

    if tier == RiskTier.T3:
        if auth_level == AuthLevel.T3_STEP_UP and subject_ref is not None:
            return "ALLOW"
        return "STEP_UP"

    return "DENY"


def policy_gate_node(state: ConversationGraphState) -> dict[str, Any]:
    """Evaluate OPA risk-tier policy and select the specialist subgraph."""
    if state.get("policy_decision") == "DENY":
        return {"policy_decision": "DENY", "selected_subgraph": "handoff"}

    tier = state.get("tier", RiskTier.T0)
    auth_level = state.get("auth_level", AuthLevel.ANONYMOUS)
    subject_ref = state.get("subject_ref")
    intent = state.get("intent")
    intent_name = intent.intent if intent else None

    decision = evaluate_opa_policy(
        tier=tier,
        auth_level=auth_level,
        subject_ref=subject_ref,
        intent_name=intent_name,
    )

    if decision in ("HANDOFF", "DENY", "STEP_UP"):
        subgraph = "handoff"
    elif intent_name in (
        IntentName.GET_BALANCE,
        IntentName.GET_FILING_STATUS,
        IntentName.GET_TCC_STATUS,
        IntentName.BOOK_APPOINTMENT,
        IntentName.CREATE_CASE,
        IntentName.REPORT_SCAM,
    ):
        subgraph = "self_service"
    else:
        subgraph = "knowledge_qa"

    return {
        "policy_decision": decision,
        "selected_subgraph": subgraph,
    }
