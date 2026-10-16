"""Specialist subgraph: knowledge_qa, calculator, guided_journey, and verify_official (Section 6.1)."""

from __future__ import annotations

from typing import Any

from ssra_core import AuthLevel, IntentName, LocaleCode

from ssra_runtime.schemas import ToolArtifact
from ssra_runtime.state import ConversationGraphState
from ssra_runtime.tools import GovernedMcpGatewayClient


def execute_knowledge_qa_subgraph(
    state: ConversationGraphState,
    gateway: GovernedMcpGatewayClient,
) -> dict[str, Any]:
    intent = state.get("intent")
    intent_name = intent.intent if intent else IntentName.KNOWLEDGE_QA
    slots = state.get("slots", {})
    locale = state.get("locale", LocaleCode.EN)
    auth_level = state.get("auth_level", AuthLevel.ANONYMOUS)
    subject_ref = state.get("subject_ref")
    artifacts: list[ToolArtifact] = list(state.get("artifacts", []))

    if intent_name == IntentName.OUT_OF_SCOPE:
        return {"artifacts": artifacts}

    if intent_name == IntentName.CALCULATE_PAYE:
        gross = str(slots.get("amount_ssp", "250000"))
        art = gateway.invoke_tool(
            server_name="tax-facts",
            tool_name="calculate_paye_estimate",
            arguments={"gross_monthly_ssp": gross},
            auth_level=auth_level,
            subject_ref=subject_ref,
        )
        artifacts.append(art)
        return {"artifacts": artifacts}

    if intent_name == IntentName.CALCULATE_WITHHOLDING:
        gross = str(slots.get("amount_ssp", "1000000"))
        art = gateway.invoke_tool(
            server_name="tax-facts",
            tool_name="calculate_withholding_estimate",
            arguments={"gross_amount_ssp": gross, "category": "goods_and_services"},
            auth_level=auth_level,
            subject_ref=subject_ref,
        )
        artifacts.append(art)
        return {"artifacts": artifacts}

    if intent_name == IntentName.VERIFY_OFFICIAL_CHANNEL:
        candidate = str(slots.get("candidate_channel", "https://etax.nra.gov.ss/"))
        art = gateway.invoke_tool(
            server_name="official-channels",
            tool_name="verify_payment_account",
            arguments={"account_or_portal": candidate},
            auth_level=auth_level,
            subject_ref=subject_ref,
        )
        artifacts.append(art)
        return {"artifacts": artifacts}

    # Default: search published knowledge corpus
    query = state.get("redacted_user_text") or state.get("raw_user_text", "SSRA eTax")
    kn_art = gateway.invoke_tool(
        server_name="knowledge",
        tool_name="search_knowledge",
        arguments={"query": query, "language": locale.value, "top_k": 3},
        auth_level=auth_level,
        subject_ref=subject_ref,
    )
    artifacts.append(kn_art)

    # Also attach paye.filing.deadline_day TaxFact if the retrieved chunk states day 15
    top_results = kn_art.structured_content.get("results", [])
    if top_results and "15" in str(top_results[0].get("content", "")):
        tf_art = gateway.invoke_tool(
            server_name="tax-facts",
            tool_name="get_tax_fact",
            arguments={"key": "paye.filing.deadline_day"},
            auth_level=auth_level,
            subject_ref=subject_ref,
        )
        artifacts.append(tf_art)

    return {"artifacts": artifacts}
