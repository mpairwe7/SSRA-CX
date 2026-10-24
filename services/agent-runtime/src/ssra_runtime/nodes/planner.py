"""Stage 5: Bounded Autonomous Goal Planner & Subgraph Delegation Stack (October 2026 Agentic CX).

Constructs a bounded `Plan` (`max_plan_steps=4` within `TurnBudget.max_tool_calls=16`) from the
taxpayer's canonical English-Router query and current `Intent`, supporting:
1. Compound multi-step T1 read / T0 verification plans (e.g., `get_balance` + `get_filing_status` + `get_tcc_status`).
2. Cross-tier Read -> Verify -> Stage-Write plans (e.g., `ledger.get_balance` -> `cases.create_case` or `appointments.book_appointment`).
3. Mid-journey specialist delegation (`workflow_stack`) so a taxpayer in a guided journey can ask a
   statutory/calculator question and resume their exact step without losing progress.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from ssra_core import Intent, IntentName, Plan, RiskTier

MAX_PLAN_STEPS: int = 4
MAX_WORKFLOW_STACK_DEPTH: int = 2


class ActiveWorkflowCursor(BaseModel):
    """Serializable cursor tracking a taxpayer's position in a multi-step guided journey."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    workflow_id: str
    journey_intent: IntentName
    current_step: int = Field(ge=1, default=1)
    total_steps: int = Field(ge=1, default=2)
    status: Literal["ACTIVE", "PAUSED_FOR_DELEGATION", "COMPLETED"] = "ACTIVE"
    officer_note: str = ""


def detect_compound_self_service_steps(text: str, primary_intent: IntentName) -> list[str]:
    """Detect whether a taxpayer utterance requests multiple governed T1/T2/T0 actions in one turn."""
    lower = text.lower()
    steps: list[str] = []

    wants_balance = primary_intent == IntentName.GET_BALANCE or any(
        k in lower for k in ("balance", "how much do i owe", "outstanding", "gurush kam", "medyun")
    )
    wants_filing = primary_intent == IntentName.GET_FILING_STATUS or any(
        k in lower for k in ("filing status", "did my return", "return status", "last filed")
    )
    wants_tcc = primary_intent == IntentName.GET_TCC_STATUS or any(
        k in lower for k in ("tcc status", "check my tcc", "compliance certificate status")
    )
    wants_customs_dec = any(k in lower for k in ("customs declaration", "nimule declaration"))
    wants_case = any(
        k in lower
        for k in ("open a case", "create a case", "open a support case", "reconciliation case")
    )
    wants_appointment = any(
        k in lower for k in ("book an appointment", "book appointment", "schedule appointment")
    )

    if primary_intent in (
        IntentName.GET_BALANCE,
        IntentName.GET_FILING_STATUS,
        IntentName.GET_TCC_STATUS,
    ):
        if wants_balance:
            steps.append("ledger.get_balance")
        if wants_filing:
            steps.append("ledger.get_filing_status")
        if wants_customs_dec:
            steps.append("customs.get_declaration_status")
        if wants_tcc:
            steps.append("tcc.get_tcc_status")
        if wants_case:
            steps.append("cases.create_case")
        elif wants_appointment:
            steps.append("appointments.book_appointment")

    if not steps:
        if primary_intent == IntentName.GET_BALANCE:
            steps.append("ledger.get_balance")
        elif primary_intent == IntentName.GET_FILING_STATUS:
            steps.append("ledger.get_filing_status")
        elif primary_intent == IntentName.GET_TCC_STATUS:
            steps.append("tcc.get_tcc_status")
        elif primary_intent == IntentName.CALCULATE_PAYE:
            steps.append("tax-facts.calculate_paye_estimate")
        elif primary_intent == IntentName.CALCULATE_WITHHOLDING:
            steps.append("tax-facts.calculate_withholding_estimate")
        elif primary_intent == IntentName.VERIFY_OFFICIAL_CHANNEL:
            steps.append("official-channels.verify_payment_account")
        elif primary_intent == IntentName.REPORT_SCAM:
            steps.append("official-channels.report_scam")
        elif primary_intent == IntentName.BOOK_APPOINTMENT:
            steps.append("appointments.book_appointment")
        elif primary_intent == IntentName.CREATE_CASE:
            steps.append("cases.create_case")
        elif primary_intent in (
            IntentName.GUIDED_TIN_REGISTRATION,
            IntentName.GUIDED_FILING_AND_PAYMENT,
            IntentName.GUIDED_TCC,
        ):
            steps.append(f"guided_journey.{primary_intent.value}")
            steps.append("knowledge.search_corpus")
        elif primary_intent == IntentName.KNOWLEDGE_QA:
            steps.append("knowledge.search_corpus")
            steps.append("tax-facts.get_tax_fact")
        else:
            steps.append(f"route.{primary_intent.value}")

    return steps[:MAX_PLAN_STEPS]


def build_execution_plan(
    *,
    intent: Intent,
    canonical_query: str,
    tier: RiskTier,
    selected_subgraph: str = "knowledge_qa",
    planner_enabled: bool = True,
) -> Plan:
    """Construct a bounded `Plan` for Stage 5 execution."""
    if not planner_enabled:
        return Plan(
            subgraph=selected_subgraph,
            steps=[f"single.{intent.intent.value}"],
            tier=tier,
        )
    if intent.intent == IntentName.VERIFY_OFFICIAL_CHANNEL:
        verif_step = (
            "official-channels.verify_sender"
            if intent.slots.get("verification_mode") == "sender"
            else "official-channels.verify_payment_account"
        )
        return Plan(subgraph=selected_subgraph, steps=[verif_step], tier=tier)
    if intent.intent == IntentName.KNOWLEDGE_QA and intent.slots.get("hs_code"):
        cust_step = (
            "customs.estimate_duties"
            if intent.slots.get("cif_value_usd")
            else "customs.lookup_tariff"
        )
        return Plan(subgraph=selected_subgraph, steps=[cust_step], tier=tier)
    steps = detect_compound_self_service_steps(canonical_query, intent.intent)
    if intent.intent == IntentName.CALCULATE_PAYE:
        if intent.slots.get("compound_wht"):
            steps.append("tax-facts.calculate_withholding_estimate")
        if intent.slots.get("hs_code"):
            cust_step = (
                "customs.estimate_duties"
                if intent.slots.get("cif_value_usd")
                else "customs.lookup_tariff"
            )
            steps.append(cust_step)
    if intent.intent == IntentName.GET_FILING_STATUS and intent.slots.get(
        "include_customs_declaration"
    ):
        lower_q = canonical_query.lower()
        also_wants_filing = any(
            k in lower_q for k in ("filing status", "did my return", "return status", "last filed")
        )
        if also_wants_filing:
            if "customs.get_declaration_status" not in steps:
                steps.insert(0, "customs.get_declaration_status")
        else:
            steps = [
                "customs.get_declaration_status" if s == "ledger.get_filing_status" else s
                for s in steps
            ]
            if "customs.get_declaration_status" not in steps:
                steps.insert(0, "customs.get_declaration_status")
    steps = list(dict.fromkeys(steps))
    return Plan(
        subgraph=selected_subgraph,
        steps=steps[:MAX_PLAN_STEPS],
        tier=tier,
    )
