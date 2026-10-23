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
    """Return localized step-by-step guided journey instructions in English, Arabic (RTL), or Juba Arabic."""
    if intent_name == IntentName.GUIDED_TIN_REGISTRATION:
        if locale == LocaleCode.AR:
            return [
                GuidedJourneyStep(
                    journey_id="tin_registration",
                    step_number=1,
                    total_steps=3,
                    title="١. اختيار فئة المكلف (فرد، شركة، أو منظمة غير حكومية)",
                    instruction=(
                        "يتقدم المواطنون مباشرة عبر https://etax.nra.gov.ss/. الشركات تتحقق أولاً عبر بوابة "
                        "وزارة العدل، والمنظمات تتطلب رقم تسجيل شؤون الإغاثة ورقم هاتف +211 فعال."
                    ),
                    section_anchor="Part-I-Sec-1-TIN-Registration",
                ),
                GuidedJourneyStep(
                    journey_id="tin_registration",
                    step_number=2,
                    total_steps=3,
                    title="٢. تعبئة طلب التسجيل الإلكتروني ETAX-TIN-01",
                    instruction="أرسل استمارة ETAX-TIN-01 إلكترونياً عبر https://etax.nra.gov.ss/.",
                    section_anchor="Part-I-Sec-1-TIN-Registration",
                ),
                GuidedJourneyStep(
                    journey_id="tin_registration",
                    step_number=3,
                    total_steps=3,
                    title="٣. تحميل شهادة الرقم الضريبي TIN الرسمية",
                    instruction="قم بتنزيل شهادة الرقم الضريبي الرقمية من لوحة حسابك في نظام e-Tax.",
                    section_anchor="Part-I-Sec-1-TIN-Registration",
                ),
            ]
        if locale == LocaleCode.PGA:
            return [
                GuidedJourneyStep(
                    journey_id="tin_registration",
                    step_number=1,
                    total_steps=3,
                    title="1. Ikhtar Noo ta Mukallaf (Fard, Sharika, aw Munazzama)",
                    instruction=(
                        "Muwatinin bi سجلو tawali fi https://etax.nra.gov.ss/. Sharikat bi aamlo tasdiq "
                        "awwal fi Wizarat al-Adl, wa NGOs lazim raqam tasjil wa tilifon +211."
                    ),
                    section_anchor="Part-I-Sec-1-TIN-Registration",
                ),
                GuidedJourneyStep(
                    journey_id="tin_registration",
                    step_number=2,
                    total_steps=3,
                    title="2. Amil Form ETAX-TIN-01 fi e-Tax",
                    instruction="Arsil talab ETAX-TIN-01 online fi https://etax.nra.gov.ss/.",
                    section_anchor="Part-I-Sec-1-TIN-Registration",
                ),
                GuidedJourneyStep(
                    journey_id="tin_registration",
                    step_number=3,
                    total_steps=3,
                    title="3. Nazzil Shahada ta TIN al-Rasmiya",
                    instruction="Nazzil shahada ta TIN min hisabak fi https://etax.nra.gov.ss/.",
                    section_anchor="Part-I-Sec-1-TIN-Registration",
                ),
            ]
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
        if locale == LocaleCode.AR:
            return [
                GuidedJourneyStep(
                    journey_id="obtain_tcc",
                    step_number=1,
                    total_steps=2,
                    title="١. التحقق من فعالية الرقم الضريبي وتقديم الإقرارات",
                    instruction=(
                        "تأكد من أن رقمك الضريبي TIN فعال وأن جميع الإقرارات والأرصدة غير المتنازع عليها "
                        "مسددة عبر https://etax.nra.gov.ss/."
                    ),
                    section_anchor="Part-III-Sec-4-TCC",
                ),
                GuidedJourneyStep(
                    journey_id="obtain_tcc",
                    step_number=2,
                    total_steps=2,
                    title="٢. التقديم الإلكتروني الحصري عبر نظام e-Tax",
                    instruction=(
                        "تصدر شهادات الامتثال الضريبي (TCC) حصرياً عبر https://etax.nra.gov.ss/؛ "
                        "الشهادات الورقية اليدوية غير معتمدة."
                    ),
                    section_anchor="Part-III-Sec-4-TCC",
                ),
            ]
        if locale == LocaleCode.PGA:
            return [
                GuidedJourneyStep(
                    journey_id="obtain_tcc",
                    step_number=1,
                    total_steps=2,
                    title="1. At'akkad min TIN wa Iqrarat ta Dariba",
                    instruction=(
                        "At'akkad inno TIN bitaak shaghghal wa kul iqrarat wa hisabat khalas "
                        "fi https://etax.nra.gov.ss/."
                    ),
                    section_anchor="Part-III-Sec-4-TCC",
                ),
                GuidedJourneyStep(
                    journey_id="obtain_tcc",
                    step_number=2,
                    total_steps=2,
                    title="2. قدم الطلب في e-Tax فقط",
                    instruction=(
                        "Shahada ta TCC bi tatla bas min https://etax.nra.gov.ss/; "
                        "shahada waraqiya barra e-Tax ma maqbula."
                    ),
                    section_anchor="Part-III-Sec-4-TCC",
                ),
            ]
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

    if locale == LocaleCode.AR:
        return [
            GuidedJourneyStep(
                journey_id="file_and_pay",
                step_number=1,
                total_steps=2,
                title="١. تقديم الإقرار الضريبي إلكترونياً عبر e-Tax",
                instruction="قدم إقرارك الضريبي عبر https://etax.nra.gov.ss/ قبل الموعد القانوني بتوقيت جوبا.",
                section_anchor="Sec-1-Cash-Free-Collection",
            ),
            GuidedJourneyStep(
                journey_id="file_and_pay",
                step_number=2,
                total_steps=2,
                title="٢. السداد الحصري عبر البنوك التجارية المعتمدة (منع الدفع النقدي)",
                instruction=(
                    "بموجب توجيه مارس ٢٠٢٦، يتم السداد حصرياً عبر البنوك المعتمدة المرتبطة بحساب الخزانة الموحد (TSA). "
                    "يُمنع دفع أي مبالغ نقدية للمحصلين."
                ),
                section_anchor="Sec-1-Cash-Free-Collection",
            ),
        ]
    if locale == LocaleCode.PGA:
        return [
            GuidedJourneyStep(
                journey_id="file_and_pay",
                step_number=1,
                total_steps=2,
                title="1. Arsil Iqrar ta Dariba fi e-Tax",
                instruction="Arsil iqrarak fi https://etax.nra.gov.ss/ gabil يوم 15 بتوقيت جوبا.",
                section_anchor="Sec-1-Cash-Free-Collection",
            ),
            GuidedJourneyStep(
                journey_id="file_and_pay",
                step_number=2,
                total_steps=2,
                title="2. Adfa bil Bank al-Mu'tamad Bas (Mamnu Kaash)",
                instruction=(
                    "Hasab qarar March 2026, adfa bas fi bunuk TSA bita https://etax.nra.gov.ss/. "
                    "Abadan ma tadfa guruush kaash li ayyi zol."
                ),
                section_anchor="Sec-1-Cash-Free-Collection",
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
