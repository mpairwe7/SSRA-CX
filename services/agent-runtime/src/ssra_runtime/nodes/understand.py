"""Node 4: understand — classify typed Intent and look up immutable RiskTier from risk-tiers.yaml (Section 4 & 6.1)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from ssra_core import Intent, IntentName, LocaleCode, RiskTier, evaluate_flag
from ssra_security import validate_inter_model_handoff

from ssra_runtime.nodes.language_state import (
    LanguageStateLiteral,
    build_english_router_envelope,
)
from ssra_runtime.nodes.planner import build_execution_plan
from ssra_runtime.state import ConversationGraphState

_RISK_TIERS_FILE = Path(__file__).resolve().parents[5] / "ai" / "policies" / "risk-tiers.yaml"


def _load_intent_tiers() -> dict[str, RiskTier]:
    """Load the deterministic intent-to-RiskTier mapping from `ai/policies/risk-tiers.yaml`."""
    raw = yaml.safe_load(_RISK_TIERS_FILE.read_text(encoding="utf-8"))
    mapping = raw.get("intent_tiers", {})
    return {str(k): RiskTier(str(v)) for k, v in mapping.items()}


_INTENT_TIERS = _load_intent_tiers()
_ARABIC_DIGIT_TRANS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٬", "01234567890123456789,")
_TAGGED_MONEY_RE = re.compile(
    r"(?:(?:\b(?:cif|ssp|usd)\b|\$)\s*(?:\$\s*)?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{1,10}(?:\.\d+)?)\b"
    r"|\b(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{1,10}(?:\.\d+)?)\s*(?:\b(?:ssp|usd)\b|جنيه|دولار))",
    re.IGNORECASE,
)
_CIF_USD_MONEY_RE = re.compile(
    r"(?:(?:\b(?:cif|usd)\b|\$)\s*(?:\$\s*)?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{1,10}(?:\.\d+)?)\b"
    r"|\b(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{1,10}(?:\.\d+)?)\s*(?:\busd\b|دولار))",
    re.IGNORECASE,
)
_UNTAGGED_MONEY_RE = re.compile(r"\b(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{4,10}(?:\.\d+)?)\b")
_HS_CODE_RE = re.compile(r"\b(\d{4}\.\d{2})\b")
_HS_CUE_RE = re.compile(
    r"\b(?:hs|hs\s+code|tariff|customs|duty|duties)\b",
    re.IGNORECASE,
)
_URL_TOKEN_RE = re.compile(r"(https?://\S+)", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
_PHONE_211_RE = re.compile(r"(\+211[\s-]?\d{3}[\s-]?\d{3}[\s-]?\d{3}|\+211\d{9})")
_DOMAIN_CANDIDATE_RE = re.compile(
    r"(?<!\S)((?:[^\s/$.?#]+\.)+[a-z\u0400-\u04ff]{2,}(?::[0-9A-Za-z]+)?(?:/\S*)?)",
    re.IGNORECASE,
)


def _normalise_amount_token(raw_token: str) -> str:
    """Strip thousands commas and redundant trailing '.00' while preserving non-zero fractional cents."""
    cleaned = raw_token.replace(",", "").strip()
    if "." in cleaned:
        cleaned = cleaned.rstrip("0").rstrip(".")
    return cleaned or "0"


def _extract_all_monetary_amounts(scan_text: str) -> list[str]:
    """Extract all monetary amounts in order of appearance, skipping calendar years (1900-2099)."""
    amounts: list[str] = []
    for match in _TAGGED_MONEY_RE.finditer(scan_text):
        raw_val = match.group(1) or match.group(2)
        if raw_val:
            norm = _normalise_amount_token(raw_val)
            if norm not in amounts:
                amounts.append(norm)
    for match in _UNTAGGED_MONEY_RE.finditer(scan_text):
        tok = match.group(1)
        if "," not in tok and "." not in tok and len(tok) == 4 and 1900 <= int(tok) <= 2099:
            continue
        norm = _normalise_amount_token(tok)
        if norm not in amounts:
            amounts.append(norm)
    return amounts


def _extract_monetary_amount(scan_text: str) -> str | None:
    """Extract a monetary amount, prioritizing explicit SSP/USD/CIF/$ tags and skipping calendar years (1900-2099)."""
    all_amounts = _extract_all_monetary_amounts(scan_text)
    return all_amounts[0] if all_amounts else None


_WHT_NON_RESIDENT_RE = re.compile(
    r"\b(?:non[- ]resident|foreign contractor)\b|غير مقيم|مقاول أجنبي",
    re.IGNORECASE,
)
_WHT_GOV_CONTRACTOR_RE = re.compile(
    r"\b(?:government contractor|resident contractor|ministry contract)\b|مقاول حكومي",
    re.IGNORECASE,
)
_WHT_TECH_FEES_RE = re.compile(
    r"\b(?:technical fees?|technical service|management fee|professional fee|consultanc(?:y|ies)|consulting)\b|رسوم فنية|استشارات",
    re.IGNORECASE,
)
_WHT_MOBILE_MONEY_RE = re.compile(
    r"\b(?:mobile money|m-?gurush|momo|dealer commission)\b|عمولة المحفظة",
    re.IGNORECASE,
)
_WHT_EOSB_RE = re.compile(
    r"\b(?:end of service|eosb|gratuity|severance)\b|نهاية الخدمة",
    re.IGNORECASE,
)
_WHT_RENT_RE = re.compile(
    r"\b(?:rent|rental|landlord|lease|ijar)\b|إيجار|ايجار",
    re.IGNORECASE,
)


def _has_explicit_wht_category_cue(lower: str) -> bool:
    """Return True if the text explicitly names a statutory Withholding Tax category."""
    return any(
        rx.search(lower) is not None
        for rx in (
            _WHT_NON_RESIDENT_RE,
            _WHT_GOV_CONTRACTOR_RE,
            _WHT_TECH_FEES_RE,
            _WHT_MOBILE_MONEY_RE,
            _WHT_EOSB_RE,
            _WHT_RENT_RE,
        )
    )


def _detect_withholding_category(lower: str) -> str:
    """Resolve the South Sudan statutory Withholding Tax category (Financial Act 2024/2025)."""
    if _WHT_NON_RESIDENT_RE.search(lower) is not None:
        return "government_contractors_non_resident"
    if _WHT_GOV_CONTRACTOR_RE.search(lower) is not None:
        return "government_contractors_resident"
    if _WHT_TECH_FEES_RE.search(lower) is not None:
        return "technical_fees"
    if _WHT_MOBILE_MONEY_RE.search(lower) is not None:
        return "mobile_money_commissions"
    if _WHT_EOSB_RE.search(lower) is not None:
        return "end_of_service_benefits"
    if _WHT_RENT_RE.search(lower) is not None:
        return "rent"
    return "goods_and_services"


def _extract_official_channel_candidate(text: str, lower: str) -> tuple[str, str]:
    """Extract the candidate identifier and verification mode ('sender' vs 'payment_account')."""
    is_sender_query = "verify sender" in lower or "sender id" in lower or "sms from" in lower
    url_match = _URL_TOKEN_RE.search(text)
    if url_match:
        raw_url = url_match.group(1).rstrip(".,;:)]?!'\"")
        return raw_url, "sender" if is_sender_query else "payment_account"
    if "[redacted_email]" in lower or "+211•••••••" in text:
        return "unverified-sender-contact", "sender"
    email_match = _EMAIL_RE.search(text)
    if email_match:
        return email_match.group(1), "sender"
    phone_match = _PHONE_211_RE.search(text)
    if phone_match:
        return phone_match.group(1), "sender"
    domain_match = _DOMAIN_CANDIDATE_RE.search(text)
    if domain_match:
        raw_dom = domain_match.group(1).rstrip(".,;:)]?!'\"")
        return raw_dom, "sender" if is_sender_query else "payment_account"
    if "tsa-etax-bank" in lower:
        return "TSA-ETAX-BANK", "payment_account"
    if is_sender_query and "ssra" in lower and "fake" not in lower and "scam" not in lower:
        return "SSRA", "sender"
    return "unverified-collector-account", "sender" if is_sender_query else "payment_account"


def classify_intent_deterministic(text: str, locale: LocaleCode) -> Intent:
    """Classify taxpayer user text into a typed Intent with extracted slots."""
    normalized_digits_text = text.translate(_ARABIC_DIGIT_TRANS)
    lower = normalized_digits_text.lower()
    slots: dict[str, str | int | float | bool] = {}

    has_hs_cue = _HS_CUE_RE.search(lower) is not None
    hs_match = _HS_CODE_RE.search(normalized_digits_text) if has_hs_cue else None
    if hs_match:
        slots["hs_code"] = hs_match.group(1)

    # Strip HS code before money extraction only when an HS/customs cue is present
    money_scan_text = (
        _HS_CODE_RE.sub(" ", normalized_digits_text) if has_hs_cue else normalized_digits_text
    )
    extracted_amount = _extract_monetary_amount(money_scan_text)
    if extracted_amount is not None:
        slots["amount_ssp"] = extracted_amount
    cif_match = _CIF_USD_MONEY_RE.search(money_scan_text)
    if cif_match is not None:
        raw_cif = cif_match.group(1) or cif_match.group(2)
        if raw_cif:
            slots["cif_value_usd"] = _normalise_amount_token(raw_cif)
    elif extracted_amount is not None and (
        "cif" in lower or "usd" in lower or "$" in normalized_digits_text
    ):
        slots["cif_value_usd"] = extracted_amount

    # 1. T4 Human-only intents: waivers, penalty remission, refunds, tax disputes, legal rulings
    if any(
        w in lower
        for w in (
            "waive",
            "waiver",
            "penalty remission",
            "forgive my penalty",
            "tax dispute",
            "appeal assessment",
            "binding legal ruling",
            "refund my tax",
        )
    ):
        return Intent(
            intent=IntentName.REQUEST_WAIVER_OR_DISPUTE_T4,
            slots=slots,
            language=locale,
            confidence=0.99,
        )

    # 2. Out-of-scope / non-SSRA political or unrelated topics
    if any(
        w in lower
        for w in (
            "election",
            "political party",
            "football",
            "weather forecast",
            "recipe",
            "cryptocurrency",
        )
    ):
        return Intent(
            intent=IntentName.OUT_OF_SCOPE,
            slots=slots,
            language=locale,
            confidence=0.98,
        )

    # 3. Report scam (T2 write)
    if any(w in lower for w in ("report a scam", "report scam", "fake collector demanded")):
        slots["suspected_identifier"] = "+211-UNVERIFIED-COLLECTOR"
        slots["summary"] = text[:200]
        return Intent(
            intent=IntentName.REPORT_SCAM,
            slots=slots,
            language=locale,
            confidence=0.97,
        )

    # 4. Verify official channel / anti-impersonation check (T0)
    if any(
        w in lower
        for w in (
            "is this really ssra",
            "verify account",
            "verify sender",
            "scam check",
            "cash collector",
        )
    ) or (
        "official" in lower
        and any(
            k in lower
            for k in (
                "etax.nra.gov.ss",
                "nra.gov.ss",
                "eservices.gov.ss",
                "boss.gov.ss",
                "mofp.gov.ss",
                "+211",
                "payment portal",
                "channel",
                "sender",
                "account",
                "email",
                "phone",
            )
        )
    ):
        candidate, verification_mode = _extract_official_channel_candidate(
            normalized_digits_text, lower
        )
        slots["candidate_channel"] = candidate
        slots["verification_mode"] = verification_mode
        return Intent(
            intent=IntentName.VERIFY_OFFICIAL_CHANNEL,
            slots=slots,
            language=locale,
            confidence=0.98,
        )

    # 5. PAYE calculator (T0) — also supports compound PAYE + WHT in the same turn (Toolathlon)
    has_paye_cue = any(
        w in lower
        for w in ("paye", "salary tax", "income tax on", "dariba ta mahiya", "ضريبة الدخل")
    ) and (
        "amount_ssp" in slots or "calculate" in lower or "estimate" in lower or "how much" in lower
    )
    has_wht_cue = any(
        w in lower
        for w in (
            "withholding",
            "wht",
            "ضريبة الاستقطاع",
            "الخصم من المنبع",
            "dariba ta wht",
        )
    ) and (
        "amount_ssp" in slots
        or "calculate" in lower
        or "estimate" in lower
        or "احسب" in lower
        or "كم" in lower
    )
    if has_paye_cue:
        all_amounts = _extract_all_monetary_amounts(money_scan_text)
        if "amount_ssp" not in slots:
            slots["amount_ssp"] = "250000"
            slots["amount_defaulted"] = True
        if has_wht_cue:
            slots["compound_wht"] = True
            slots["wht_amount_ssp"] = (
                all_amounts[1] if len(all_amounts) >= 2 else str(slots["amount_ssp"])
            )
            slots["wht_category"] = _detect_withholding_category(lower)
        return Intent(
            intent=IntentName.CALCULATE_PAYE,
            slots=slots,
            language=locale,
            confidence=0.98,
        )

    # 6. Withholding calculator (T0) — supports all 7 Financial Act 2024/2025 WHT categories
    if has_wht_cue:
        if "amount_ssp" not in slots:
            slots["amount_ssp"] = "1000000"
            slots["amount_defaulted"] = True
        slots["wht_category"] = _detect_withholding_category(lower)
        return Intent(
            intent=IntentName.CALCULATE_WITHHOLDING,
            slots=slots,
            language=locale,
            confidence=0.96,
        )

    # 7. Authenticated T1/T2 self-service intents
    if any(
        w in lower
        for w in ("my balance", "check my tax balance", "how much do i owe", "ledger balance")
    ):
        return Intent(
            intent=IntentName.GET_BALANCE,
            slots=slots,
            language=locale,
            confidence=0.98,
        )
    has_customs_declaration_cue = any(
        w in lower
        for w in (
            "my customs declaration",
            "customs declaration status",
            "my nimule declaration",
            "nimule declaration status",
        )
    )
    if (
        any(
            w in lower
            for w in (
                "my filing status",
                "did my return go through",
                "my tax declaration status",
            )
        )
        or has_customs_declaration_cue
    ):
        if has_customs_declaration_cue:
            slots["include_customs_declaration"] = True
        return Intent(
            intent=IntentName.GET_FILING_STATUS,
            slots=slots,
            language=locale,
            confidence=0.97,
        )
    if any(w in lower for w in ("my tcc status", "check my tcc")):
        return Intent(
            intent=IntentName.GET_TCC_STATUS,
            slots=slots,
            language=locale,
            confidence=0.97,
        )
    if any(w in lower for w in ("book an appointment", "book appointment", "schedule appointment")):
        slots["office_code"] = "JUBA_HQ"
        slots["slot_id"] = "slot_2026_10_20_0900"
        return Intent(
            intent=IntentName.BOOK_APPOINTMENT,
            slots=slots,
            language=locale,
            confidence=0.97,
        )
    if any(
        w in lower
        for w in ("open a support case", "create a support case", "open a case", "create a case")
    ):
        slots["case_type"] = "INQUIRY"
        slots["summary"] = text[:200]
        return Intent(
            intent=IntentName.CREATE_CASE,
            slots=slots,
            language=locale,
            confidence=0.97,
        )

    # 8. Guided journeys & Knowledge Q&A (T0)
    if any(
        w in lower
        for w in (
            "step by step how to file",
            "guided filing",
            "how do i file and pay",
            "file my return and pay",
        )
    ):
        return Intent(
            intent=IntentName.GUIDED_FILING_AND_PAYMENT,
            slots=slots,
            language=locale,
            confidence=0.96,
        )
    if any(w in lower for w in ("tin", "register", "رقم الضريبي", "الرقم الضريبي", "tasjil")):
        return Intent(
            intent=IntentName.GUIDED_TIN_REGISTRATION,
            slots=slots,
            language=locale,
            confidence=0.96,
        )
    if any(w in lower for w in ("tcc", "tax compliance certificate", "شهادة الامتثال")):
        return Intent(
            intent=IntentName.GUIDED_TCC,
            slots=slots,
            language=locale,
            confidence=0.95,
        )

    return Intent(
        intent=IntentName.KNOWLEDGE_QA,
        slots=slots,
        language=locale,
        confidence=0.94,
    )


_STEP_CONTINUATION_RE = re.compile(
    r"^\s*(?:next(?:\s+step)?|continue|proceed|resume|go\s+on|what(?:'s|\s+is)\s+next|step\s+([123]))\b",
    re.IGNORECASE,
)
_STEP_CONTINUATION_ELIGIBLE: frozenset[IntentName] = frozenset(
    {
        IntentName.KNOWLEDGE_QA,
        IntentName.GUIDED_TIN_REGISTRATION,
        IntentName.GUIDED_FILING_AND_PAYMENT,
        IntentName.GUIDED_TCC,
    }
)
_ANAPHORIC_FOLLOWUP_RE = re.compile(
    r"\b(?:what\s+if|what\s+about|how\s+about|and\s+for|instead|now\s+for|if\s+it\s+is|for\s+cif)\b",
    re.IGNORECASE,
)


def _resolve_multiturn_followup(
    *,
    intent_obj: Intent,
    routing_text: str,
    prior_intent: str | None,
    prior_slots: dict[str, Any],
    workflow_stack: list[dict[str, Any]],
) -> tuple[Intent, list[dict[str, Any]]]:
    """Resolve multi-turn anaphoric slot carry-over and guided-journey step continuation (ADR-028)."""
    lower = routing_text.translate(_ARABIC_DIGIT_TRANS).lower().strip()
    updated_stack = [dict(c) for c in workflow_stack]

    # 1. Guided journey step continuation ('next step', 'continue', 'step 2') on active workflow_stack
    step_match = _STEP_CONTINUATION_RE.search(lower)
    is_eligible_step = bool(
        step_match is not None
        and updated_stack
        and intent_obj.intent in _STEP_CONTINUATION_ELIGIBLE
    )
    if is_eligible_step and step_match is not None:
        top = updated_stack[-1]
        j_intent_str = str(top.get("journey_intent", ""))
        if j_intent_str in IntentName._value2member_map_:
            cur_step = int(top.get("current_step", 1))
            total_steps = int(top.get("total_steps", 2))
            explicit_step = int(step_match.group(1)) if step_match.group(1) else 0
            next_step = (
                min(max(1, explicit_step), total_steps)
                if explicit_step > 0
                else min(cur_step + 1, total_steps)
            )
            top["current_step"] = next_step
            top["status"] = "COMPLETED" if next_step >= total_steps else "ACTIVE"
            new_slots = {**intent_obj.slots, "guided_step_number": next_step}
            return (
                intent_obj.model_copy(
                    update={
                        "intent": IntentName(j_intent_str),
                        "slots": new_slots,
                        "confidence": 0.97,
                    }
                ),
                updated_stack,
            )

    # 2. If explicit CALCULATE_WITHHOLDING matched without a new amount, inherit prior amount_ssp
    should_inherit_wht_amt = bool(
        intent_obj.intent == IntentName.CALCULATE_WITHHOLDING
        and intent_obj.slots.get("amount_defaulted")
        and "amount_ssp" in prior_slots
    )
    if should_inherit_wht_amt:
        inherited = {
            **intent_obj.slots,
            "amount_ssp": str(prior_slots["amount_ssp"]),
            "amount_defaulted": False,
        }
        return intent_obj.model_copy(update={"slots": inherited}), updated_stack

    # 3. Elliptical / anaphoric follow-ups when primary classification fell through to KNOWLEDGE_QA
    if intent_obj.intent == IntentName.KNOWLEDGE_QA:
        is_anaphoric = _ANAPHORIC_FOLLOWUP_RE.search(lower) is not None
        has_wht_cat = _has_explicit_wht_category_cue(lower)

        # 3a. Customs HS code carry-over when follow-up provides CIF value or asks about duty
        should_carry_hs = bool(
            "hs_code" not in intent_obj.slots
            and "hs_code" in prior_slots
            and (
                "cif_value_usd" in intent_obj.slots
                or (
                    is_anaphoric
                    and any(w in lower for w in ("duty", "duties", "cif", "usd", "$", "tariff"))
                )
            )
        )
        if should_carry_hs:
            carried_slots = {**intent_obj.slots, "hs_code": str(prior_slots["hs_code"])}
            return intent_obj.model_copy(update={"slots": carried_slots}), updated_stack

        # 3b. Withholding Tax follow-up ('What if it is for technical fees?' or 'What if it is 3,000,000 SSP?')
        if prior_intent == IntentName.CALCULATE_WITHHOLDING.value and (
            has_wht_cat or (is_anaphoric and "amount_ssp" in intent_obj.slots)
        ):
            carried_amount = str(
                intent_obj.slots.get("amount_ssp") or prior_slots.get("amount_ssp", "1000000")
            )
            carried_cat = (
                _detect_withholding_category(lower)
                if has_wht_cat
                else str(prior_slots.get("wht_category", "goods_and_services"))
            )
            wht_slots = {
                **intent_obj.slots,
                "amount_ssp": carried_amount,
                "wht_category": carried_cat,
            }
            return (
                intent_obj.model_copy(
                    update={
                        "intent": IntentName.CALCULATE_WITHHOLDING,
                        "slots": wht_slots,
                        "confidence": 0.95,
                    }
                ),
                updated_stack,
            )

        # 3c. PAYE Calculator follow-up ('What if it is 800,000 SSP?')
        should_promote_paye = bool(
            prior_intent == IntentName.CALCULATE_PAYE.value
            and is_anaphoric
            and "amount_ssp" in intent_obj.slots
            and "hs_code" not in intent_obj.slots
            and not has_wht_cat
        )
        if should_promote_paye:
            return (
                intent_obj.model_copy(
                    update={
                        "intent": IntentName.CALCULATE_PAYE,
                        "confidence": 0.96,
                    }
                ),
                updated_stack,
            )

    return intent_obj, updated_stack


def understand_node(state: ConversationGraphState) -> dict[str, Any]:
    """Execute Stage 4 & 5: English-Router normalization, intent classification, tier lookup, and bounded goal planning."""
    # Microsoft agent-framework#8132: Preserve or promote restored intent/tier on AG-UI confirmation resume turns
    existing_pending = state.get("pending_confirmation")
    existing_intent = state.get("intent")
    if (
        existing_pending is not None
        and state.get("confirmation_token_in")
        and existing_intent is not None
    ):
        tool_to_intent = {
            "create_case": IntentName.CREATE_CASE,
            "book_appointment": IntentName.BOOK_APPOINTMENT,
            "report_scam": IntentName.REPORT_SCAM,
        }
        resumed_intent_name = tool_to_intent.get(existing_pending.tool, existing_intent.intent)
        merged_resumed_slots = {**existing_intent.slots, **existing_pending.arguments}
        resumed_intent = existing_intent.model_copy(
            update={"intent": resumed_intent_name, "slots": merged_resumed_slots}
        )
        tier = _INTENT_TIERS.get(resumed_intent.intent.value, state.get("tier", RiskTier.T2))
        return {
            "intent": resumed_intent,
            "slots": dict(resumed_intent.slots),
            "tier": tier,
        }

    text = state.get("redacted_user_text") or state.get("raw_user_text", "")
    locale = state.get("locale", LocaleCode.EN)
    subject_id = state.get("subject_ref") or state.get("thread_id", "thr_default")
    channel_str = str(state.get("channel", "web"))

    raw_lang_state = state.get("language_state", "LOCKED")
    lang_state: LanguageStateLiteral = (
        raw_lang_state
        if raw_lang_state in ("LOCKED", "CODE_SWITCHING", "CANDIDATE_SHIFT", "FALLBACK_EN")
        else "LOCKED"
    )
    router_env = build_english_router_envelope(
        text,
        source_locale=locale,
        language_state=lang_state,
    )
    routing_text = (
        router_env.canonical_en_query
        if evaluate_flag(
            "FF_ENGLISH_ROUTER_CANONICAL",
            subject_ref=subject_id,
            channel=channel_str,
            locale=locale.value,
        )
        else text
    )
    raw_intent = classify_intent_deterministic(routing_text, locale)
    resolved_intent, updated_wf_stack = _resolve_multiturn_followup(
        intent_obj=raw_intent,
        routing_text=routing_text,
        prior_intent=state.get("prior_intent"),
        prior_slots=state.get("prior_slots") or {},
        workflow_stack=list(state.get("workflow_stack") or []),
    )
    intent_obj = validate_inter_model_handoff(resolved_intent)
    merged_slots: dict[str, Any] = {**state.get("slots", {}), **intent_obj.slots}
    router_env = router_env.model_copy(update={"extracted_slots": dict(intent_obj.slots)})

    # Risk tier NEVER comes from the model; it comes deterministically from risk-tiers.yaml
    tier = _INTENT_TIERS.get(intent_obj.intent.value, RiskTier.T0)

    planner_enabled = evaluate_flag(
        "FF_AUTONOMOUS_GOAL_PLANNER",
        subject_ref=subject_id,
        channel=channel_str,
        locale=locale.value,
    )
    plan = build_execution_plan(
        intent=intent_obj,
        canonical_query=router_env.canonical_en_query,
        tier=tier,
        planner_enabled=planner_enabled,
    )

    return {
        "english_router_envelope": router_env,
        "intent": intent_obj,
        "slots": merged_slots,
        "workflow_stack": updated_wf_stack,
        "tier": tier,
        "plan": plan,
    }
