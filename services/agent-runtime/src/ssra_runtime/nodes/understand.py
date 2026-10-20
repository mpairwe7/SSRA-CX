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
_MONEY_RE = re.compile(r"\b(\d{1,3}(?:,\d{3})+|\d{4,10})(?:\.\d+)?\b")


def classify_intent_deterministic(text: str, locale: LocaleCode) -> Intent:
    """Classify taxpayer user text into a typed Intent with extracted slots."""
    lower = text.lower()
    slots: dict[str, str | int | float | bool] = {}

    amount_match = _MONEY_RE.search(text)
    if amount_match:
        slots["amount_ssp"] = amount_match.group(1).replace(",", "")

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
            for k in ("etax.nra.gov.ss", "payment portal", "channel", "sender", "account")
        )
    ):
        candidate = (
            "https://etax.nra.gov.ss/"
            if "etax.nra.gov.ss" in lower
            else "unverified-collector-account"
        )
        slots["candidate_channel"] = candidate
        return Intent(
            intent=IntentName.VERIFY_OFFICIAL_CHANNEL,
            slots=slots,
            language=locale,
            confidence=0.98,
        )

    # 5. PAYE calculator (T0)
    if any(
        w in lower
        for w in ("paye", "salary tax", "income tax on", "dariba ta mahiya", "ضريبة الدخل")
    ) and (
        "amount_ssp" in slots or "calculate" in lower or "estimate" in lower or "how much" in lower
    ):
        if "amount_ssp" not in slots:
            slots["amount_ssp"] = "250000"
        return Intent(
            intent=IntentName.CALCULATE_PAYE,
            slots=slots,
            language=locale,
            confidence=0.98,
        )

    # 6. Withholding calculator (T0)
    if any(w in lower for w in ("withholding", "wht")) and (
        "amount_ssp" in slots or "calculate" in lower or "estimate" in lower
    ):
        if "amount_ssp" not in slots:
            slots["amount_ssp"] = "1000000"
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
    if any(w in lower for w in ("my filing status", "did my return go through")):
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
        resumed_intent = existing_intent.model_copy(update={"intent": resumed_intent_name})
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
    intent_obj = validate_inter_model_handoff(classify_intent_deterministic(routing_text, locale))
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
        "tier": tier,
        "plan": plan,
    }
