"""Specialist subgraph: guided_journey (TIN registration, return filing, bank payment, TCC, customs basics — Section 3 & 6.1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ssra_core import IntentName, LocaleCode


@dataclass(frozen=True)
class GuidedJourneyStep:
    journey_id: str
    step_number: int
    total_steps: int
    title: str
    instruction: str
    official_portal: Literal["https://etax.nra.gov.ss/"] = "https://etax.nra.gov.ss/"
    section_anchor: str = "Part-I-Sec-1-TIN-Registration"


def get_guided_journey_steps(
    intent_name: IntentName,
    locale: LocaleCode = LocaleCode.EN,
) -> list[GuidedJourneyStep]:
    _ = locale
    if intent_name == IntentName.GUIDED_TIN_REGISTRATION:
        return [
            GuidedJourneyStep(
                journey_id="tin_registration",
                step_number=1,
                total_steps=3,
                title="Select Applicant Category (Individual, Business, or NGO)",
                instruction=(
                    "Citizens apply directly on https://etax.nra.gov.ss/. Businesses validate first "
                    "via Ministry of Justice eServices. NGOs require a Ministry of Humanitarian "
                    "Services registration number and an active +211 phone number."
                ),
                section_anchor="Part-I-Sec-1-TIN-Registration",
            ),
            GuidedJourneyStep(
                journey_id="tin_registration",
                step_number=2,
                total_steps=3,
                title="Complete Online Application on e-Tax",
                instruction="Submit the ETAX-TIN-01 form online at https://etax.nra.gov.ss/.",
                section_anchor="Part-I-Sec-1-TIN-Registration",
            ),
            GuidedJourneyStep(
                journey_id="tin_registration",
                step_number=3,
                total_steps=3,
                title="Download Official TIN Certificate",
                instruction="Download your digital TIN certificate from your e-Tax account dashboard.",
                section_anchor="Part-I-Sec-1-TIN-Registration",
            ),
        ]

    if intent_name == IntentName.GUIDED_TCC:
        return [
            GuidedJourneyStep(
                journey_id="obtain_tcc",
                step_number=1,
                total_steps=2,
                title="Verify Active TIN & Filing Compliance",
                instruction=(
                    "Ensure your TIN is active and all required tax returns and undisputed balances "
                    "are current on https://etax.nra.gov.ss/."
                ),
                section_anchor="Part-III-Sec-4-TCC",
            ),
            GuidedJourneyStep(
                journey_id="obtain_tcc",
                step_number=2,
                total_steps=2,
                title="Apply Electronically on e-Tax Only",
                instruction=(
                    "Tax Compliance Certificates (TCC) are issued exclusively through "
                    "https://etax.nra.gov.ss/; manual paper TCCs outside e-Tax are invalid."
                ),
                section_anchor="Part-III-Sec-4-TCC",
            ),
        ]

    return [
        GuidedJourneyStep(
            journey_id="file_and_pay",
            step_number=1,
            total_steps=2,
            title="File Return Electronically on e-Tax",
            instruction="Submit your tax return on https://etax.nra.gov.ss/ before the statutory Africa/Juba deadline.",
            section_anchor="Sec-1-Cash-Free-Collection",
        ),
        GuidedJourneyStep(
            journey_id="file_and_pay",
            step_number=2,
            total_steps=2,
            title="Pay Exclusively into Designated Commercial Banks (Cash-Free Directive)",
            instruction=(
                "Under the March 2026 directive, pay strictly into designated banks remitting to "
                "the Treasury Single Account (TSA). Never pay cash to an individual collector."
            ),
            section_anchor="Sec-1-Cash-Free-Collection",
        ),
    ]
