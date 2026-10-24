"""Specialist subgraph: guided_journey (TIN registration, return filing, bank payment, TCC, customs basics — Section 3 & 6.1)."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Set
from dataclasses import dataclass
from typing import Any, Literal

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
                instruction="Arsil iqrarak fi https://etax.nra.gov.ss/ gabil al-mawid al-qanuni bi tawqit Juba.",
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


@dataclass(frozen=True)
class JourneyPrerequisiteSpec:
    """Statutory or operational prerequisite in an SSRA guided journey DAG (`journey_copilot.py` Pillar 1)."""

    id: str
    label: str
    slot: str = ""
    remediation_journey: str = ""
    remediation_journey_name: str = ""


@dataclass(frozen=True)
class JourneyFormFieldSpec:
    """Declarative A2UI form box mapping for an SSRA guided journey slot (`journey_copilot.py` Pillar 2)."""

    box: str
    label: str
    slot: str


SSRA_JOURNEY_PREREQUISITE_DAG: dict[str, tuple[JourneyPrerequisiteSpec, ...]] = {
    "tin_registration": (
        JourneyPrerequisiteSpec(
            id="applicant_category",
            label="Applicant classification (Individual, Business, or NGO)",
            slot="taxpayer_type",
        ),
        JourneyPrerequisiteSpec(
            id="identity_or_moj_docs",
            label="National ID / Passport, Ministry of Justice eServices, or Humanitarian Services registration",
            slot="documents_ready",
        ),
    ),
    "obtain_tcc": (
        JourneyPrerequisiteSpec(
            id="active_tin_tcc",
            label="Active SSRA TIN on e-Tax",
            slot="has_tin",
            remediation_journey="tin_registration",
            remediation_journey_name="TIN Registration Guide",
        ),
        JourneyPrerequisiteSpec(
            id="returns_up_to_date",
            label="All required periodic tax returns filed on https://etax.nra.gov.ss/",
            slot="returns_filed",
            remediation_journey="file_and_pay",
            remediation_journey_name="File and Pay Guide",
        ),
        JourneyPrerequisiteSpec(
            id="tax_due_settled",
            label="Undisputed tax balances settled via approved TSA commercial bank",
            slot="tax_paid",
            remediation_journey="file_and_pay",
            remediation_journey_name="File and Pay Guide",
        ),
    ),
    "file_and_pay": (
        JourneyPrerequisiteSpec(
            id="active_tin",
            label="Active SSRA TIN",
            slot="has_tin",
            remediation_journey="tin_registration",
            remediation_journey_name="TIN Registration Guide",
        ),
        JourneyPrerequisiteSpec(
            id="tsa_bank_verified",
            label="Designated TSA-remitting commercial bank selected (Cash-Free Directive)",
            slot="tsa_bank_ready",
        ),
    ),
    "customs_clearance": (
        JourneyPrerequisiteSpec(
            id="customs_valuation_evidence",
            label="Commercial invoice, CIF valuation & HS code ready for TANCIS++",
            slot="valuation_ready",
        ),
        JourneyPrerequisiteSpec(
            id="customs_supporting_documents",
            label="Bill of lading / airway bill and packing list ready",
            slot="documents_ready",
        ),
    ),
}

SSRA_JOURNEY_FORM_SCHEMAS: dict[str, tuple[str, str, tuple[JourneyFormFieldSpec, ...]]] = {
    "tin_registration": (
        "ETAX-TIN-01",
        "SSRA TIN Registration Readiness Schedule",
        (
            JourneyFormFieldSpec("Box A1", "Applicant Classification", "taxpayer_type"),
            JourneyFormFieldSpec("Box A2", "Supporting Registration Documents", "documents_ready"),
        ),
    ),
    "obtain_tcc": (
        "ETAX-TCC-01",
        "SSRA Tax Compliance Certificate (TCC) Readiness Schedule",
        (
            JourneyFormFieldSpec("Sec A", "Active SSRA TIN Confirmed", "has_tin"),
            JourneyFormFieldSpec("Sec B", "All Periodic Returns Filed", "returns_filed"),
            JourneyFormFieldSpec("Sec C", "TSA Tax Balances Settled", "tax_paid"),
        ),
    ),
    "file_and_pay": (
        "ETAX-RET-PAY-01",
        "SSRA e-Tax Return & TSA Bank Payment Schedule",
        (
            JourneyFormFieldSpec("Line 1", "Active SSRA TIN", "has_tin"),
            JourneyFormFieldSpec("Line 2", "Tax Head / Return Type", "tax_type"),
            JourneyFormFieldSpec("Line 3", "Designated TSA Bank Verified", "tsa_bank_ready"),
        ),
    ),
    "customs_clearance": (
        "TANCIS-CUS-01",
        "SSRA TANCIS++ Customs Clearance Schedule",
        (
            JourneyFormFieldSpec("Box 1", "HS Code & CIF Valuation Ready", "valuation_ready"),
            JourneyFormFieldSpec("Box 2", "Shipping & Packing Documents Ready", "documents_ready"),
        ),
    ),
}


def evaluate_journey_prerequisites(
    journey_id: str,
    slots: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Evaluate the Prerequisite DAG for *journey_id* (`journey_copilot.py` Pillar 1)."""
    specs = SSRA_JOURNEY_PREREQUISITE_DAG.get(journey_id, ())
    out: list[dict[str, Any]] = []
    for spec in specs:
        raw_val = slots.get(spec.slot) if spec.slot else None
        is_missing = raw_val is False or str(raw_val).strip().lower() in ("false", "no", "unknown")
        if is_missing:
            status = "missing"
        elif raw_val not in ("", None):
            status = "satisfied"
        else:
            status = "pending"
        item: dict[str, Any] = {"id": spec.id, "label": spec.label, "status": status}
        if spec.slot:
            item["slot"] = spec.slot
        if spec.remediation_journey and status == "missing":
            item["remediation_journey"] = spec.remediation_journey
            item["remediation_action"] = f"Guide me through {spec.remediation_journey_name}"
        out.append(item)
    return out


def build_journey_form_draft_surface(
    journey_id: str,
    slots: Mapping[str, Any],
    *,
    sensitive_slots: Set[str] = frozenset({"tin", "phone", "subject_ref"}),
) -> dict[str, Any]:
    """Build a declarative A2UI form co-completion schedule without leaking sensitive values (`journey_copilot.py` Pillar 2)."""
    schema = SSRA_JOURNEY_FORM_SCHEMAS.get(journey_id)
    if schema is None:
        return {
            "protocol": "a2ui/v1",
            "surface_id": f"ssra-form-{journey_id}",
            "form_code": "ETAX-GEN-01",
            "title": "SSRA Guided Preparation Schedule",
            "completion_pct": 0,
            "filled_count": 0,
            "total_fields": 0,
            "ready_for_portal": False,
            "fields": [],
        }
    form_code, title, field_specs = schema
    fields: list[dict[str, Any]] = []
    for fspec in field_specs:
        val = slots.get(fspec.slot)
        is_filled = val not in ("", None)
        is_masked = fspec.slot in sensitive_slots
        if not is_filled:
            display_val = "Pending"
            status = "pending"
        elif is_masked:
            display_val = "•••• (Masked)"
            status = "filled"
        elif isinstance(val, bool):
            display_val = "Confirmed" if val else "Action required"
            status = "filled" if val else "attention_needed"
        else:
            display_val = "Recorded"
            status = "filled"
        fields.append(
            {
                "box": fspec.box,
                "label": fspec.label,
                "slot": fspec.slot,
                "status": status,
                "display_value": display_val,
                "masked": is_masked,
            }
        )
    total_fields = len(fields)
    filled_count = sum(1 for f in fields if f["status"] == "filled")
    completion_pct = round((filled_count / total_fields) * 100)
    attention_needed = any(f["status"] == "attention_needed" for f in fields)
    return {
        "protocol": "a2ui/v1",
        "surface_id": f"ssra-form-{journey_id}",
        "form_code": form_code,
        "title": title,
        "completion_pct": completion_pct,
        "filled_count": filled_count,
        "total_fields": total_fields,
        "ready_for_portal": filled_count == total_fields and not attention_needed,
        "fields": fields,
    }


_SSRA_OBJECTIVE_PATTERNS: tuple[tuple[re.Pattern[str], dict[str, str]], ...] = (
    (
        re.compile(
            r"\b(?:bid\s+for\s+a\s+tender|government\s+contract\s+clearance|apply\s+for\s+(?:a\s+)?tcc|"
            r"need\s+(?:a\s+)?tax\s+clearance|clearance\s+certificate)\b",
            re.IGNORECASE,
        ),
        {
            "objective_id": "tax_clearance_application",
            "title": "Apply for an SSRA Tax Compliance Certificate (TCC) on e-Tax",
            "journey_id": "obtain_tcc",
            "official_portal": "https://etax.nra.gov.ss/",
            "prerequisites_summary": "Active TIN, all periodic returns filed, and undisputed tax balances settled via TSA bank",
        },
    ),
    (
        re.compile(
            r"\b(?:goods\s+(?:stuck|held|detained)\s+at\s+(?:nimule|kaya|juba|customs|border)|"
            r"clear\s+(?:my\s+)?(?:container|shipment|cargo|import)|tancis\s+declaration)\b",
            re.IGNORECASE,
        ),
        {
            "objective_id": "customs_cargo_clearance",
            "title": "Clear Imported Goods via TANCIS++ Customs",
            "journey_id": "customs_clearance",
            "official_portal": "https://etax.nra.gov.ss/",
            "prerequisites_summary": "Commercial invoice, CIF valuation, HS code, bill of lading, and packing list",
        },
    ),
    (
        re.compile(
            r"\b(?:opening\s+a\s+(?:shop|business|company)|starting\s+a\s+(?:new\s+)?business|"
            r"register\s+my\s+new\s+business\s+for\s+tax|first\s+time\s+taxpayer)\b",
            re.IGNORECASE,
        ),
        {
            "objective_id": "new_business_tax_onboarding",
            "title": "Onboard a New Business & Register for an SSRA TIN (ETAX-TIN-01)",
            "journey_id": "tin_registration",
            "official_portal": "https://etax.nra.gov.ss/",
            "prerequisites_summary": "National ID/Passport (citizens), Ministry of Justice eServices (businesses), or Humanitarian Services registration (NGOs)",
        },
    ),
)


def infer_taxpayer_journey_objective(text: str) -> dict[str, str] | None:
    """Map natural-language taxpayer situations to explicit SSRA journey objectives (`journey_copilot.py` Pillar 4)."""
    clean = (text or "").strip()
    if not clean:
        return None
    for pattern, descriptor in _SSRA_OBJECTIVE_PATTERNS:
        if pattern.search(clean):
            return dict(descriptor)
    return None


def evaluate_journey_step_up_auth(
    journey_id: str,
    slots: Mapping[str, Any],
    *,
    is_authenticated: bool = False,
    requires_auth: bool = False,
) -> dict[str, Any] | None:
    """Return an inline Step-Up Auth descriptor preserving anonymous slots (`journey_copilot.py` Pillar 5, WCAG 2.2 SC 3.3.7)."""
    filled_keys = [k for k in slots if not k.startswith("_") and slots.get(k) not in ("", None)]
    portal_blocked = (
        slots.get("portal_access") is False
        or str(slots.get("portal_access", "")).lower() == "false"
    )
    if portal_blocked:
        return {
            "required": True,
            "mode": "recover_access",
            "reason": "SSRA e-Tax portal access is required to submit this declaration.",
            "login_url": "https://etax.nra.gov.ss/",
            "remediation_journey_id": "tin_registration",
            "preserves_slots": True,
            "preserved_slot_count": len(filled_keys),
        }
    if requires_auth and not is_authenticated:
        return {
            "required": True,
            "mode": "login_or_register",
            "reason": "Sign in to your SSRA e-Tax account (or register for a TIN) to complete submission.",
            "login_url": "https://etax.nra.gov.ss/",
            "register_journey_id": "tin_registration",
            "preserves_slots": True,
            "preserved_slot_count": len(filled_keys),
        }
    return None


def elevate_anonymous_journey_slots(
    anonymous_slots: Mapping[str, Any],
    *,
    authenticated_subject_ref: str,
    profile_defaults: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Elevate anonymous journey slots to an authenticated subject with zero data loss (`journey_copilot.py` Pillar 5, WCAG 3.3.7)."""
    merged: dict[str, Any] = dict(anonymous_slots)
    merged["_authenticated_subject_ref"] = authenticated_subject_ref
    if profile_defaults:
        for key, value in profile_defaults.items():
            if value not in ("", None) and merged.get(key) in ("", None):
                merged[key] = value
    return merged


def build_journey_stall_scaffolding(
    step_id: str,
    slot_name: str,
    failed_attempts: int,
    options: list[str] | None = None,
) -> dict[str, Any] | None:
    """Return progressive field-level examples and 1-tap helpers when a user stalls (`journey_copilot.py` Pillar 6)."""
    if failed_attempts <= 0:
        return None
    helper_actions = list(options[:4] if options else ["individual", "business", "ngo"])
    if failed_attempts >= 2 and "Talk to an SSRA officer" not in helper_actions:
        helper_actions.append("Talk to an SSRA officer")
    return {
        "step_id": step_id,
        "slot_name": slot_name,
        "failed_attempts": failed_attempts,
        "hint": (
            f"Please select one of the valid options: {', '.join(options)}."
            if options
            else "Provide a valid value for this step, or ask to speak with an SSRA officer."
        ),
        "helper_actions": helper_actions,
    }


SSRA_RESUME_CODE_PREFIXES: dict[str, str] = {
    "tin_registration": "TIN",
    "obtain_tcc": "TCC",
    "file_and_pay": "PAY",
    "customs_clearance": "CUS",
}
_SSRA_PREFIX_TO_JOURNEY: dict[str, str] = {
    code: jid for jid, code in SSRA_RESUME_CODE_PREFIXES.items()
}
_SSRA_RESUME_CODE_RE = re.compile(r"\bSSRA-([A-Z]{3})-S(\d{1,2})-([A-F0-9]{4})\b", re.IGNORECASE)


def _ssra_resume_check(prefix: str, step_number: int) -> str:
    return hashlib.sha256(f"ssra-resume:{prefix}:{step_number}".encode()).hexdigest()[:4].upper()


def generate_ssra_resume_code(journey_id: str, step_idx: int) -> str:
    """Generate a deterministic, PII-free cross-channel resume code (`journey_copilot.py` Pillar 7)."""
    prefix = SSRA_RESUME_CODE_PREFIXES.get(journey_id or "")
    if prefix is None:
        return ""
    step_num = max(0, int(step_idx)) + 1
    return f"SSRA-{prefix}-S{step_num}-{_ssra_resume_check(prefix, step_num)}"


def looks_like_ssra_resume_code(text: str) -> bool:
    """Return True when *text* contains an SSRA resume code pattern."""
    return bool(text) and _SSRA_RESUME_CODE_RE.search(text) is not None


def parse_ssra_resume_code(text: str) -> dict[str, Any] | None:
    """Parse and verify a cross-channel SSRA resume token (`SSRA-TIN-S2-...`), rejecting typos (`Pillar 7`)."""
    if not text:
        return None
    for match in _SSRA_RESUME_CODE_RE.finditer(text):
        prefix = match.group(1).upper()
        step_num = int(match.group(2))
        digest = match.group(3).upper()
        journey_id = _SSRA_PREFIX_TO_JOURNEY.get(prefix)
        if journey_id is None or step_num < 1 or digest != _ssra_resume_check(prefix, step_num):
            continue
        return {
            "code": f"SSRA-{prefix}-S{step_num}-{digest}",
            "prefix": prefix,
            "journey_id": journey_id,
            "step_number": step_num,
            "step_idx": step_num - 1,
            "digest": digest,
        }
    return None


_SSRA_PORTAL_ERROR_CATALOG: tuple[tuple[re.Pattern[str], dict[str, Any]], ...] = (
    (
        re.compile(
            r"\b(?:session\s+expired|timed\s+out|unauthorized|login\s+expired)\b", re.IGNORECASE
        ),
        {
            "error_code": "ETAX_SESSION_EXPIRED",
            "title": "e-Tax Portal Session Expired",
            "root_cause": "Your SSRA e-Tax session timed out due to inactivity.",
            "official_portal": "https://etax.nra.gov.ss/",
            "resolution_steps": [
                "Return to https://etax.nra.gov.ss/ and sign in again with your TIN.",
                "Re-open your draft return or payment schedule from your taxpayer dashboard.",
            ],
        },
    ),
    (
        re.compile(
            r"\b(?:duplicate\s+return|already\s+filed\s+for\s+period|return\s+already\s+exists)\b",
            re.IGNORECASE,
        ),
        {
            "error_code": "ETAX_DUPLICATE_RETURN",
            "title": "Duplicate Return for Filing Period",
            "root_cause": "An original return has already been submitted for this tax period on e-Tax.",
            "official_portal": "https://etax.nra.gov.ss/",
            "resolution_steps": [
                "Check your filing history on https://etax.nra.gov.ss/ for the existing return receipt.",
                "If a correction is needed, select 'Amended Return' rather than filing a new original return.",
            ],
        },
    ),
    (
        re.compile(
            r"\b(?:tcc\s+application\s+rejected|outstanding\s+tax\s+arrears|compliance\s+block|unfiled\s+returns)\b",
            re.IGNORECASE,
        ),
        {
            "error_code": "TCC_COMPLIANCE_ARREARS_BLOCK",
            "title": "TCC Compliance Block — Unfiled Returns or Outstanding Arrears",
            "root_cause": "e-Tax blocked TCC issuance because periodic returns or undisputed tax balances remain open.",
            "official_portal": "https://etax.nra.gov.ss/",
            "resolution_steps": [
                "Review your e-Tax ledger on https://etax.nra.gov.ss/ for any unfiled monthly PAYE or WHT periods.",
                "Settle any undisputed balance through a designated TSA commercial bank, then re-apply for the TCC online.",
            ],
        },
    ),
)


def diagnose_ssra_portal_error(text: str) -> dict[str, Any] | None:
    """Diagnose known SSRA e-Tax / TANCIS++ portal error messages into structured resolution steps (`portal_copilot.py`)."""
    clean = (text or "").strip()
    if not clean:
        return None
    for pattern, diag in _SSRA_PORTAL_ERROR_CATALOG:
        if pattern.search(clean):
            return dict(diag)
    return None
