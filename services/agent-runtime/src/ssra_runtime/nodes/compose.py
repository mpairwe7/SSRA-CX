"""Node 8: compose — Grounded answer assembly with citations, numeric claims, and Generative UI cards (Section 6.1-6.3, 9.3)."""

from __future__ import annotations

from typing import Any

from ssra_core import (
    Answer,
    AnswerSegment,
    ChannelCapabilities,
    Citation,
    GenerativeUIComponent,
    GenerativeUIComponentName,
    IntentName,
    LocaleCode,
    NumericClaim,
    NumericUnit,
)
from ssra_llm import PromptRegistry

from ssra_runtime.state import ConversationGraphState


def compose_node(state: ConversationGraphState) -> dict[str, Any]:
    # If an earlier deterministic node, policy gate, or confirmation sheet already produced the Answer, keep it
    if state.get("answer") is not None:
        return {}

    intent = state.get("intent")
    intent_name = intent.intent if intent else IntentName.KNOWLEDGE_QA
    locale = state.get("locale", LocaleCode.EN)
    artifacts = list(state.get("artifacts", []))
    citations = list(state.get("citations", []))
    capabilities = state.get("capabilities", ChannelCapabilities())

    # Build L0-L5 spotlighted prompt envelope for audit/trace reconstructability
    registry = PromptRegistry.load_default()
    _envelope = registry.build_layered_prompt(
        prompt_id="compose_v1",
        locale=locale,
        capabilities=capabilities,
        user_input_redacted=state.get("redacted_user_text", ""),
        retrieved_evidence=[c.model_dump(mode="json") for c in citations],
        tool_artifacts=[a.structured_content for a in artifacts],
    )

    # 1. Out-of-scope abstention (Section 14.2 >= 95% abstention gate)
    if intent_name == IntentName.OUT_OF_SCOPE:
        return {
            "answer": Answer(
                segments=[
                    AnswerSegment(
                        text=(
                            "I am SSRA Assist, the virtual assistant for the South Sudan Revenue Authority (SSRA). "
                            "I can only answer questions about South Sudan domestic taxes, customs procedures, "
                            "official e-Tax channels (https://etax.nra.gov.ss/), and taxpayer services. "
                            "Would you like to speak with an SSRA officer?"
                        ),
                        citation_ids=[],
                    )
                ],
                citations=[],
                numbers=[],
                ui_component=GenerativeUIComponent(
                    name=GenerativeUIComponentName.HANDOFF_CARD,
                    props={"reason": "OUT_OF_SCOPE"},
                )
                if capabilities.rich_ui
                else None,
                is_estimate=False,
                abstained=True,
            )
        }

    # 2. PAYE Calculator response (`CalculatorForm` generative UI card)
    paye_art = next((a for a in artifacts if a.tool == "calculate_paye_estimate"), None)
    if paye_art is not None:
        sc = paye_art.structured_content
        cit_id = citations[0].id if citations else "cit_paye_act"
        if not citations:
            citations = [
                Citation(
                    id="cit_paye_act",
                    snapshot_version=str(sc.get("snapshot_version", "2026.10.1")),
                    doc_title="Taxation Act 2009 (as amended by Financial Act 2024/2025)",
                    section_anchor="Part-IV-Sec-18-PAYE",
                    effective_from="2024-07-01",
                    url="https://etax.nra.gov.ss/",
                )
            ]
        numbers = [NumericClaim.model_validate(n) for n in sc.get("numeric_claims", [])]
        gross = sc["gross_monthly_ssp"]
        tax = sc["estimated_tax_ssp"]
        net = sc["net_monthly_ssp"]
        eff = sc["effective_rate_percent"]
        due_day = sc["filing_deadline_day"]

        text = (
            f"ESTIMATE ONLY (Not an official assessment): For a gross monthly salary of {gross} SSP, "
            f"the estimated monthly PAYE tax is {tax} SSP (effective rate {eff}%), leaving an estimated "
            f"net monthly pay of {net} SSP. Monthly PAYE returns and bank payments via "
            f"https://etax.nra.gov.ss/ are due by day {due_day} of the following month (Africa/Juba time)."
        )
        return {
            "citations": citations,
            "answer": Answer(
                segments=[AnswerSegment(text=text[: capabilities.max_len], citation_ids=[cit_id])],
                citations=citations,
                numbers=numbers,
                ui_component=GenerativeUIComponent(
                    name=GenerativeUIComponentName.CALCULATOR_FORM,
                    props={
                        "calculator_type": "PAYE",
                        "gross_monthly_ssp": gross,
                        "estimated_tax_ssp": tax,
                        "net_monthly_ssp": net,
                        "effective_rate_percent": eff,
                        "filing_deadline_day": due_day,
                        "is_estimate": True,
                    },
                )
                if capabilities.rich_ui
                else None,
                is_estimate=True,
                abstained=False,
            ),
        }

    # 3. Withholding Tax Calculator response
    wht_art = next((a for a in artifacts if a.tool == "calculate_withholding_estimate"), None)
    if wht_art is not None:
        sc = wht_art.structured_content
        cit = Citation(
            id="cit_wht_act",
            snapshot_version=str(sc.get("snapshot_version", "2026.10.1")),
            doc_title="Taxation Act 2009 (as amended by Financial Act 2024/2025)",
            section_anchor="Part-IX-Withholding-Tax",
            effective_from="2024-07-01",
            url="https://etax.nra.gov.ss/",
        )
        numbers = [NumericClaim.model_validate(n) for n in sc.get("numeric_claims", [])]
        gross = sc["gross_amount_ssp"]
        rate = sc["rate_percent"]
        wht = sc["withholding_tax_ssp"]
        net = sc["net_payable_ssp"]
        text = (
            f"ESTIMATE ONLY: For a gross payment of {gross} SSP ({sc['category']}), "
            f"the withholding tax at {rate}% is {wht} SSP, with {net} SSP net payable."
        )
        return {
            "citations": [cit],
            "answer": Answer(
                segments=[AnswerSegment(text=text[: capabilities.max_len], citation_ids=[cit.id])],
                citations=[cit],
                numbers=numbers,
                ui_component=GenerativeUIComponent(
                    name=GenerativeUIComponentName.CALCULATOR_FORM,
                    props=sc,
                )
                if capabilities.rich_ui
                else None,
                is_estimate=True,
                abstained=False,
            ),
        }

    # 4. Official channel verification (`PaymentInstructionsCard`)
    verify_art = next(
        (a for a in artifacts if a.tool in ("verify_payment_account", "verify_sender")),
        None,
    )
    if verify_art is not None:
        sc = verify_art.structured_content
        cit = Citation(
            id="cit_cashfree_2026",
            snapshot_version="2026.10.1",
            doc_title="March 2026 Directive on Exclusive National e-Tax & Cash-Free Bank Collection",
            section_anchor="Sec-1-Cash-Free-Collection",
            effective_from="2026-03-01",
            url="https://etax.nra.gov.ss/",
        )
        return {
            "citations": [cit],
            "answer": Answer(
                segments=[
                    AnswerSegment(
                        text=f"{sc['status']}: {sc['guidance']}"[: capabilities.max_len],
                        citation_ids=[cit.id],
                    )
                ],
                citations=[cit],
                numbers=[],
                ui_component=GenerativeUIComponent(
                    name=GenerativeUIComponentName.PAYMENT_INSTRUCTIONS_CARD,
                    props={
                        "identifier": sc["identifier"],
                        "status": sc["status"],
                        "guidance": sc["guidance"],
                        "official_portal": "https://etax.nra.gov.ss/",
                    },
                )
                if capabilities.rich_ui
                else None,
                is_estimate=False,
                abstained=False,
            ),
        }

    # 5. Authenticated T1 Balance (`BalanceCard`)
    bal_art = next((a for a in artifacts if a.tool == "get_balance"), None)
    if bal_art is not None:
        sc = bal_art.structured_content
        amt = str(sc["total_outstanding_ssp"])
        tin_masked = str(sc["tin_masked"])
        as_of = str(sc["as_of"])
        cit = Citation(
            id="cit_etax_ledger",
            snapshot_version="2026.10.1",
            doc_title="SSRA National e-Tax Ledger Record",
            section_anchor=f"Ledger-{tin_masked}",
            effective_from=as_of,
            url="https://etax.nra.gov.ss/",
        )
        num_claim = NumericClaim(
            value=amt,
            unit=NumericUnit.SSP,
            source_ref=f"{bal_art.id}.total_outstanding_ssp",
        )
        text = (
            f"For TIN {tin_masked}, your outstanding e-Tax balance is {amt} SSP as of {as_of} "
            f"(Filing status: {sc['filing_status']}). Pay exclusively through "
            f"https://etax.nra.gov.ss/ into designated commercial banks."
        )
        return {
            "citations": [cit],
            "answer": Answer(
                segments=[AnswerSegment(text=text[: capabilities.max_len], citation_ids=[cit.id])],
                citations=[cit],
                numbers=[num_claim],
                ui_component=GenerativeUIComponent(
                    name=GenerativeUIComponentName.BALANCE_CARD,
                    props={
                        "tin_masked": tin_masked,
                        "total_outstanding_ssp": amt,
                        "currency": "SSP",
                        "filing_status": sc["filing_status"],
                        "as_of": as_of,
                    },
                )
                if capabilities.rich_ui
                else None,
                is_estimate=False,
                abstained=False,
            ),
        }

    # 5b. Authenticated T1 Filing Status (`FilingStatusTimeline`) & TCC Status
    filing_art = next((a for a in artifacts if a.tool == "get_filing_status"), None)
    if filing_art is not None:
        sc = filing_art.structured_content
        tin_masked = str(sc["tin_masked"])
        as_of = str(sc["as_of"])
        cit = Citation(
            id="cit_etax_filing",
            snapshot_version="2026.10.1",
            doc_title="SSRA National e-Tax Filing Record",
            section_anchor=f"Filing-{tin_masked}",
            effective_from=as_of,
            url="https://etax.nra.gov.ss/",
        )
        text = (
            f"For TIN {tin_masked}, your e-Tax filing status is {sc['filing_status']} "
            f"(Last filed period: {sc['last_filed_period']}) as of {as_of} via https://etax.nra.gov.ss/."
        )
        return {
            "citations": [cit],
            "answer": Answer(
                segments=[AnswerSegment(text=text[: capabilities.max_len], citation_ids=[cit.id])],
                citations=[cit],
                numbers=[],
                ui_component=GenerativeUIComponent(
                    name=GenerativeUIComponentName.FILING_STATUS_TIMELINE,
                    props={
                        "tin_masked": tin_masked,
                        "filing_status": sc["filing_status"],
                        "last_filed_period": sc["last_filed_period"],
                        "as_of": as_of,
                    },
                )
                if capabilities.rich_ui
                else None,
                is_estimate=False,
                abstained=False,
            ),
        }

    tcc_art = next((a for a in artifacts if a.tool == "get_tcc_status"), None)
    if tcc_art is not None:
        sc = tcc_art.structured_content
        tin_masked = str(sc["tin_masked"])
        as_of = str(sc["as_of"])
        cit = Citation(
            id="cit_etax_tcc",
            snapshot_version="2026.10.1",
            doc_title="SSRA National e-Tax TCC Registry",
            section_anchor=f"TCC-{tin_masked}",
            effective_from=as_of,
            url="https://etax.nra.gov.ss/",
        )
        text = (
            f"For TIN {tin_masked}, your electronic Tax Compliance Certificate (TCC) status on "
            f"https://etax.nra.gov.ss/ is {sc['tcc_status']} (Expiry: {sc.get('tcc_expiry_date') or 'N/A'})."
        )
        return {
            "citations": [cit],
            "answer": Answer(
                segments=[AnswerSegment(text=text[: capabilities.max_len], citation_ids=[cit.id])],
                citations=[cit],
                numbers=[],
                is_estimate=False,
                abstained=False,
            ),
        }

    # 6. Confirmed T2 write actions (`report_scam`, `book_appointment`, or `create_case`)
    scam_art = next((a for a in artifacts if a.tool == "report_scam"), None)
    if scam_art is not None:
        sc = scam_art.structured_content
        cit = Citation(
            id="cit_scam_case",
            snapshot_version="2026.10.1",
            doc_title="SSRA SecOps Anti-Impersonation Registry",
            section_anchor="Sec-Scam-Intake",
            effective_from="2026-03-01",
            url="https://etax.nra.gov.ss/",
        )
        return {
            "citations": [cit],
            "answer": Answer(
                segments=[
                    AnswerSegment(
                        text=f"Scam report {sc['report_id']} has been logged with SSRA SecOps ({sc['status']}).",
                        citation_ids=[cit.id],
                    )
                ],
                citations=[cit],
                numbers=[],
                is_estimate=False,
                abstained=False,
            ),
        }

    appt_art = next((a for a in artifacts if a.tool == "book_appointment"), None)
    if appt_art is not None:
        sc = appt_art.structured_content
        cit = Citation(
            id="cit_appt_confirm",
            snapshot_version="2026.10.1",
            doc_title="SSRA Taxpayer Scheduling Service",
            section_anchor="Sec-Appointments",
            effective_from=str(sc.get("as_of", "2026-03-01")),
            url="https://etax.nra.gov.ss/",
        )
        return {
            "citations": [cit],
            "answer": Answer(
                segments=[
                    AnswerSegment(
                        text=(
                            f"Appointment {sc['appointment_id']} at office {sc['office_code']} "
                            f"is {sc['status']}."
                        ),
                        citation_ids=[cit.id],
                    )
                ],
                citations=[cit],
                numbers=[],
                is_estimate=False,
                abstained=False,
            ),
        }

    case_art = next((a for a in artifacts if a.tool == "create_case"), None)
    if case_art is not None:
        sc = case_art.structured_content
        cit = Citation(
            id="cit_case_confirm",
            snapshot_version="2026.10.1",
            doc_title="SSRA Taxpayer Case Service",
            section_anchor="Sec-Cases",
            effective_from=str(sc.get("as_of", "2026-03-01")),
            url="https://etax.nra.gov.ss/",
        )
        return {
            "citations": [cit],
            "answer": Answer(
                segments=[
                    AnswerSegment(
                        text=(
                            f"Support case {sc['case_id']} ({sc['case_type']}) has been opened "
                            f"with status {sc['status']}."
                        ),
                        citation_ids=[cit.id],
                    )
                ],
                citations=[cit],
                numbers=[],
                is_estimate=False,
                abstained=False,
            ),
        }

    # 7. Grounded Knowledge Q&A (`CitationList`)
    kn_art = next((a for a in artifacts if a.tool == "search_knowledge"), None)
    if kn_art is not None and kn_art.structured_content.get("results"):
        results: list[dict[str, Any]] = list(kn_art.structured_content["results"])
        top = results[0]
        cit = Citation(
            id=str(top["id"]),
            snapshot_version=str(kn_art.structured_content.get("snapshot_version", "2026.10.1")),
            doc_title=str(top["doc_title"]),
            section_anchor=str(top["section_anchor"]),
            effective_from=str(top["effective_from"]),
            url=str(top.get("url", "https://etax.nra.gov.ss/")),
        )
        content_text = str(top["content"])
        numbers: list[NumericClaim] = []
        for tf_art in artifacts:
            if tf_art.tool == "get_tax_fact":
                fact_obj = tf_art.structured_content.get("fact") or {}
                if "value" in fact_obj and "unit" in fact_obj and "key" in fact_obj:
                    numbers.append(
                        NumericClaim(
                            value=str(fact_obj["value"]),
                            unit=NumericUnit(str(fact_obj["unit"])),
                            source_ref=str(fact_obj["key"]),
                        )
                    )
        return {
            "citations": [cit],
            "answer": Answer(
                segments=[
                    AnswerSegment(
                        text=content_text[: capabilities.max_len],
                        citation_ids=[cit.id],
                    )
                ],
                citations=[cit],
                numbers=numbers,
                ui_component=GenerativeUIComponent(
                    name=GenerativeUIComponentName.CITATION_LIST,
                    props={"citations": [cit.model_dump(mode="json")]},
                )
                if capabilities.rich_ui
                else None,
                is_estimate=False,
                abstained=False,
            ),
        }

    # 8. Default: Principle 1 — Grounded or silent (abstain + offer handoff)
    return {
        "answer": Answer(
            segments=[
                AnswerSegment(
                    text=(
                        "I do not have sufficient published SSRA evidence to answer that question "
                        "with certainty. Would you like me to connect you with an SSRA officer?"
                    ),
                    citation_ids=[],
                )
            ],
            citations=[],
            numbers=[],
            ui_component=GenerativeUIComponent(
                name=GenerativeUIComponentName.HANDOFF_CARD,
                props={"reason": "INSUFFICIENT_EVIDENCE"},
            )
            if capabilities.rich_ui
            else None,
            is_estimate=False,
            abstained=True,
        )
    }
