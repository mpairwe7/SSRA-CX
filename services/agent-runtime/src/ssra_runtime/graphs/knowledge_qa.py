"""Specialist subgraph: knowledge_qa, calculator, guided_journey, and verify_official (Section 6.1)."""

from __future__ import annotations

from typing import Any

from ssra_core import AuthLevel, IntentName, LocaleCode

from ssra_runtime.schemas import ToolArtifact
from ssra_runtime.state import ConversationGraphState
from ssra_runtime.tools import GovernedMcpGatewayClient

# Deterministic mapping from knowledge section_anchor to authoritative TaxFact keys
_ANCHOR_TO_TAX_FACT_KEYS: dict[str, tuple[str, ...]] = {
    "Part-IV-Sec-18-PAYE-Filing": ("paye.filing.deadline_day",),
    "Module-2-Slides-1-19-Declaration-And-Filing": ("etax.filing_and_einvoice.fee_ssp",),
    "Slides-1-18-B2B-EInvoice-Generation-And-Validation": ("etax.filing_and_einvoice.fee_ssp",),
    "Sec-4-FAQs-TIN-Validity-Confidentiality-And-Cancellation": (
        "tin.status_change_notification.deadline_days",
    ),
    "Reg-1.21-1.22-1.36-1.40-Penalties-Extensions-And-Installments": (
        "penalty.late_filing_or_payment.rate_percent",
        "filing.extension.max_months",
        "payment.installment.max_months",
        "payment.installment.min_downpayment_percent",
    ),
    "Chapter-XI-PIT-Exemptions-And-8-Percent-NSIF-Deduction": (
        "pit.nsif_pension_deduction.rate_percent",
    ),
    "Chapter-XII-Sec-74-84-Depreciation-And-Quarterly-Advance-Tax": (
        "bpt.depreciation.cat1_buildings.rate_percent",
        "bpt.depreciation.cat2_vehicles_computers.rate_percent",
        "bpt.depreciation.cat3_other_property.rate_percent",
    ),
    "Chapter-XII-Sec-66-69-Business-Profit-Tax": (
        "bpt.standard.rate_percent",
        "bpt.imported_goods_advance.rate_percent",
        "bpt.rental_investment.rate_percent",
    ),
    "Chapter-XIV-Sec-92-Withholding-Tax": (
        "wht.government_contractors_resident.rate_percent",
        "wht.government_contractors_non_resident.rate_percent",
        "wht.mobile_money_commissions.rate_percent",
        "wht.end_of_service_benefits.rate_percent",
    ),
    "Chapter-XV-Excise-Tax-Schedule": (
        "excise.mineral_water_2201.rate_percent",
        "excise.beer_2203.rate_percent",
        "excise.wine_fermented_2204_2206.rate_percent",
        "excise.spirits_2207_2208.rate_percent",
        "excise.tobacco_2402_2404.rate_percent",
        "excise.perfumes_cosmetics_3303_3307.rate_percent",
        "excise.buses_8702.rate_percent",
        "excise.passenger_cars_8703.rate_percent",
        "excise.goods_vehicles_8704.rate_percent",
        "excise.vehicle_bodies_8707.rate_percent",
        "excise.motorcycles_8711.rate_percent",
    ),
    "Part-V-Sec-12-Customs-Valuation-FX": ("customs.passenger_baggage_exemption.max_usd",),
}


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

    top_results = kn_art.structured_content.get("results", [])
    if top_results:
        anchor = str(top_results[0].get("section_anchor", ""))
        fact_keys = _ANCHOR_TO_TAX_FACT_KEYS.get(anchor, ())
        for fkey in fact_keys:
            tf_art = gateway.invoke_tool(
                server_name="tax-facts",
                tool_name="get_tax_fact",
                arguments={"key": fkey},
                auth_level=auth_level,
                subject_ref=subject_ref,
            )
            artifacts.append(tf_art)

    return {"artifacts": artifacts}
