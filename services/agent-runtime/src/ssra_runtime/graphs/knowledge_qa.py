"""Specialist subgraph: knowledge_qa, calculator, guided_journey, and verify_official (Section 6.1)."""

from __future__ import annotations

from typing import Any

from ssra_core import AuthLevel, IntentName, LocaleCode, SSRAError

from ssra_runtime.nodes.verifier import verify_plan_outcomes
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
    """Execute public T0 knowledge search, calculators, and official-channel verification tools."""
    intent = state.get("intent")
    intent_name = intent.intent if intent else IntentName.KNOWLEDGE_QA
    slots = state.get("slots", {})
    locale = state.get("locale", LocaleCode.EN)
    auth_level = state.get("auth_level", AuthLevel.ANONYMOUS)
    subject_ref = state.get("subject_ref")
    budget = state.get("budget")
    artifacts: list[ToolArtifact] = list(state.get("artifacts", []))

    plan = state.get("plan")
    failed_steps: list[str] = []

    if intent_name == IntentName.OUT_OF_SCOPE:
        return {"artifacts": artifacts, "budget": budget}

    if intent_name == IntentName.CALCULATE_PAYE:
        gross = str(slots.get("amount_ssp", "250000"))
        art = gateway.invoke_tool(
            server_name="tax-facts",
            tool_name="calculate_paye_estimate",
            arguments={"gross_monthly_ssp": gross},
            auth_level=auth_level,
            subject_ref=subject_ref,
            budget=budget,
        )
        artifacts.append(art)
        if slots.get("compound_wht"):
            wht_gross = str(slots.get("wht_amount_ssp") or slots.get("amount_ssp", "1000000"))
            wht_cat = str(slots.get("wht_category", "goods_and_services"))
            try:
                wht_art = gateway.invoke_tool(
                    server_name="tax-facts",
                    tool_name="calculate_withholding_estimate",
                    arguments={"gross_amount_ssp": wht_gross, "category": wht_cat},
                    auth_level=auth_level,
                    subject_ref=subject_ref,
                    budget=budget,
                )
                artifacts.append(wht_art)
            except SSRAError:
                failed_steps.append("tax-facts.calculate_withholding_estimate")
        hs_code_comp = str(slots.get("hs_code", "")).strip()
        if hs_code_comp:
            cif_comp = str(slots.get("cif_value_usd", "")).strip()
            try:
                if cif_comp:
                    artifacts.append(
                        gateway.invoke_tool(
                            server_name="customs",
                            tool_name="estimate_duties",
                            arguments={"hs_code": hs_code_comp, "cif_value_usd": cif_comp},
                            auth_level=auth_level,
                            subject_ref=subject_ref,
                            budget=budget,
                        )
                    )
                else:
                    artifacts.append(
                        gateway.invoke_tool(
                            server_name="customs",
                            tool_name="lookup_tariff",
                            arguments={"hs_code": hs_code_comp},
                            auth_level=auth_level,
                            subject_ref=subject_ref,
                            budget=budget,
                        )
                    )
            except SSRAError:
                failed_steps.append(
                    "customs.estimate_duties" if cif_comp else "customs.lookup_tariff"
                )
        verif = verify_plan_outcomes(plan, artifacts, failed_steps=failed_steps)
        return {
            "artifacts": artifacts,
            "budget": budget,
            "outcome_verification": verif.model_dump(mode="json"),
        }

    if intent_name == IntentName.CALCULATE_WITHHOLDING:
        gross = str(slots.get("amount_ssp", "1000000"))
        wht_cat = str(slots.get("wht_category", "goods_and_services"))
        art = gateway.invoke_tool(
            server_name="tax-facts",
            tool_name="calculate_withholding_estimate",
            arguments={"gross_amount_ssp": gross, "category": wht_cat},
            auth_level=auth_level,
            subject_ref=subject_ref,
            budget=budget,
        )
        artifacts.append(art)
        verif = verify_plan_outcomes(plan, artifacts, failed_steps=failed_steps)
        return {
            "artifacts": artifacts,
            "budget": budget,
            "outcome_verification": verif.model_dump(mode="json"),
        }

    if intent_name == IntentName.VERIFY_OFFICIAL_CHANNEL:
        candidate = str(slots.get("candidate_channel", "https://etax.nra.gov.ss/"))
        verif_mode = str(slots.get("verification_mode", "payment_account"))
        if verif_mode == "sender":
            art = gateway.invoke_tool(
                server_name="official-channels",
                tool_name="verify_sender",
                arguments={"sender_id_or_url": candidate},
                auth_level=auth_level,
                subject_ref=subject_ref,
                budget=budget,
            )
        else:
            art = gateway.invoke_tool(
                server_name="official-channels",
                tool_name="verify_payment_account",
                arguments={"account_or_portal": candidate},
                auth_level=auth_level,
                subject_ref=subject_ref,
                budget=budget,
            )
        artifacts.append(art)
        return {"artifacts": artifacts, "budget": budget}

    # Customs HS code tariff lookup / duty estimate (T0 public customs tools; Principle 1 safe abstention on unknown HS codes)
    hs_code = str(slots.get("hs_code", "")).strip()
    if hs_code:
        cif_usd = str(slots.get("cif_value_usd", "")).strip()
        try:
            if cif_usd:
                cust_art = gateway.invoke_tool(
                    server_name="customs",
                    tool_name="estimate_duties",
                    arguments={"hs_code": hs_code, "cif_value_usd": cif_usd},
                    auth_level=auth_level,
                    subject_ref=subject_ref,
                    budget=budget,
                )
                artifacts.append(cust_art)
                return {"artifacts": artifacts, "budget": budget}
            tariff_art = gateway.invoke_tool(
                server_name="customs",
                tool_name="lookup_tariff",
                arguments={"hs_code": hs_code},
                auth_level=auth_level,
                subject_ref=subject_ref,
                budget=budget,
            )
            artifacts.append(tariff_art)
            return {"artifacts": artifacts, "budget": budget}
        except SSRAError:
            return {"artifacts": artifacts, "budget": budget}

    # Default: search published knowledge corpus
    query = state.get("redacted_user_text") or state.get("raw_user_text", "SSRA eTax")
    if slots.get("guided_step_number"):
        guided_query_map = {
            IntentName.GUIDED_TIN_REGISTRATION: "TIN registration e-Tax",
            IntentName.GUIDED_TCC: "Tax Compliance Certificate TCC",
            IntentName.GUIDED_FILING_AND_PAYMENT: "how to file and pay tax return e-Tax",
        }
        query = guided_query_map.get(intent_name, query)
    kn_art = gateway.invoke_tool(
        server_name="knowledge",
        tool_name="search_knowledge",
        arguments={"query": query, "language": locale.value, "top_k": 3},
        auth_level=auth_level,
        subject_ref=subject_ref,
        budget=budget,
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
                budget=budget,
            )
            artifacts.append(tf_art)

    return {"artifacts": artifacts, "budget": budget}
