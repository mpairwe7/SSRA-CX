"""Node 3: input_guard & Node 9: output_guard (Section 6.1)."""

from __future__ import annotations

import math
import re
from typing import Any

from ssra_core import (
    AffectiveSnapshot,
    Answer,
    AnswerSegment,
    HandoffTicket,
    LocaleCode,
    RiskTier,
    evaluate_flag,
)

from ssra_runtime.guardrails import (
    check_prompt_injection,
    compute_affective_state,
    redact_pii,
    validate_grounding,
    validate_neutrality_and_promises,
    validate_numeric_provenance,
    verify_no_cross_subject_or_unmasked_pii,
)
from ssra_runtime.nodes.language_state import (
    detect_explicit_locale_switch,
    evaluate_language_state_transition,
    fold_south_sudan_orthography,
)
from ssra_runtime.state import ConversationGraphState

_WORD_SPLIT_RE = re.compile(r"[^\s,.;:!?()\"'؟،]+")
_PGA_ARABIC_SCRIPT_WORDS: frozenset[str] = frozenset(
    {
        "بتاع",
        "بتاعت",
        "شنو",
        "قروش",
        "هسي",
        "داير",
        "دايرة",
    }
)
_LANGUAGE_MARKER_LEXICON: dict[LocaleCode, tuple[str, ...]] = {
    LocaleCode.PGA: (
        "kif",
        "ta dariba",
        "dariba",
        "gurush",
        "mawgi",
        "zol",
        "bikun",
        "shunu",
        "gamarik",
        "tasjil",
        "shahada ta imtisal",
        "bita",
        "anina",
        "ashan",
    ),
    LocaleCode.DIN: (
        "tene",
        "weu",
        "ajul",
        "bengic",
        "paguot",
        "thuongjang",
        "namba de ajul",
        "waraga de cuok",
    ),
    LocaleCode.NUS: (
        "yiooth",
        "juaara",
        "cuol",
        "gor",
        "thok naath",
        "thok nath",
        "muthoor",
    ),
    LocaleCode.BFA: (
        "kaser",
        "longot",
        "banki lo",
        "kegga namba",
        "kutuk na bari",
        "namba lo kaser",
    ),
    LocaleCode.ZNE: (
        "mara",
        "tumosi",
        "dunduko",
        "rogo ssra",
        "namba mara",
        "waraga mara",
        "pa pazande",
        "pazande",
    ),
    LocaleCode.SHK: (
        "coori",
        "ocul jami",
        "beene",
        "dhog",
        "dhog collo",
    ),
}


def score_language_candidates(text: str) -> dict[LocaleCode, int]:
    """Count deduplicated lexical & phrase marker matches across South Sudan languages."""
    folded = fold_south_sudan_orthography(text or "")
    words = set(_WORD_SPLIT_RE.findall(folded))
    scores: dict[LocaleCode, int] = {}
    for loc, markers in _LANGUAGE_MARKER_LEXICON.items():
        hits = 0
        for m in markers:
            if " " in m:
                if m in folded:
                    hits += 2
            elif m in words:
                hits += 1
        if hits > 0:
            scores[loc] = hits
    return scores


def detect_language(text: str, default_locale: LocaleCode = LocaleCode.EN) -> LocaleCode:
    """Detect the primary South Sudan BCP-47 language (`en`, `pga`, `ar`, `din`, `nus`, `bfa`, `zne`, `shk`)."""
    explicit = detect_explicit_locale_switch(text)
    if explicit is not None:
        return explicit

    # 1. Detect Arabic script (U+0600..U+06FF), disambiguating Juba Arabic (`pga`) from MSA (`ar`) by whole words
    if any("\u0600" <= ch <= "\u06ff" for ch in text):
        ar_words = set(_WORD_SPLIT_RE.findall(text))
        if (ar_words & _PGA_ARABIC_SCRIPT_WORDS) or "عربي جوبا" in text:
            return LocaleCode.PGA
        return LocaleCode.AR

    scores = score_language_candidates(text)
    if not scores:
        return default_locale
    best_loc = max(scores.items(), key=lambda item: item[1])[0]
    return best_loc


def _safe_meta_int(val: Any, default: int = 0, *, max_val: int = 100) -> int:
    """Safely parse a non-negative bounded integer from untrusted event metadata."""
    try:
        parsed = int(str(val).strip())
        return max(0, min(max_val, parsed))
    except (ValueError, TypeError):
        return default


def _safe_meta_float(val: Any, default: float = 0.0, *, max_val: float = 10.0) -> float:
    """Safely parse a finite non-negative bounded float from untrusted event metadata."""
    try:
        parsed = float(str(val).strip())
        if not math.isfinite(parsed):
            return default
        return max(0.0, min(max_val, parsed))
    except (ValueError, TypeError):
        return default


def input_guard_node(state: ConversationGraphState) -> dict[str, Any]:
    """Execute Stage 3 input guards: language detection, EQ scoring, PII redaction, and prompt-injection blocking."""
    raw = state.get("raw_user_text", "")
    default_loc = state.get("locale", LocaleCode.EN)
    detected_loc = detect_language(raw, default_loc)
    subject_id = state.get("subject_ref") or state.get("thread_id", "thr_default")
    channel_str = str(state.get("channel", "web"))

    lang_state = "LOCKED"
    next_candidate: LocaleCode | None = state.get("language_candidate")
    if evaluate_flag(
        "FF_ENGLISH_ROUTER_CANONICAL",
        subject_ref=subject_id,
        channel=channel_str,
        locale=detected_loc.value,
    ):
        _eff_loc, lang_state, next_candidate = evaluate_language_state_transition(
            previous_locale=default_loc,
            detected_locale=detected_loc,
            previous_candidate=state.get("language_candidate"),
            raw_text=raw,
        )

    affective: AffectiveSnapshot | None = None
    if evaluate_flag(
        "FF_REALTIME_EQ_TONE_AND_ESCALATION",
        subject_ref=subject_id,
        channel=channel_str,
        locale=detected_loc.value,
    ):
        slots_meta = state.get("slots", {})
        affective = compute_affective_state(
            raw,
            previous=state.get("affective_state"),
            consecutive_low_confidence_turns=_safe_meta_int(
                slots_meta.get("consecutive_low_confidence_turns", 0)
            ),
            repeated_clarification_count=_safe_meta_int(
                slots_meta.get("repeated_clarification_count", 0)
            ),
            barge_in_count=_safe_meta_int(slots_meta.get("voice_barge_in_count", 0)),
            rms_energy_delta=_safe_meta_float(slots_meta.get("voice_rms_energy_delta", 0.0)),
            speech_rate_ratio=_safe_meta_float(
                slots_meta.get("voice_speech_rate_ratio", 1.0), default=1.0
            ),
        )

    redaction = redact_pii(raw)
    injection = check_prompt_injection(raw)

    flags = list(state.get("safety_flags", []))
    flags.extend(redaction.pii_tags)
    flags.extend(injection.flags)

    if injection.is_blocked:
        thread_id = state.get("thread_id", "thr_default")
        ticket = HandoffTicket(
            conversation_id=thread_id,
            reason="GUARD_FALLBACK",
            queue="SCAM_REPORT",
            summary=f"Input guard blocked adversarial or cross-subject request: {injection.flags}",
            citations=[],
            priority="HIGH",
        )
        return {
            "locale": detected_loc,
            "language_state": lang_state,
            "language_candidate": next_candidate,
            "affective_state": affective,
            "tier": RiskTier.T0,
            "redacted_user_text": redaction.redacted_text,
            "safety_flags": sorted(set(flags)),
            "policy_decision": "DENY",
            "handoff_state": ticket,
            "answer": Answer(
                segments=[
                    AnswerSegment(
                        text=(
                            "I cannot fulfill instructions that bypass SSRA security policies, "
                            "divert official bank payments, or access another taxpayer's record. "
                            "All tax payments run exclusively through https://etax.nra.gov.ss/. "
                            "Would you like to speak with an SSRA officer?"
                        ),
                        citation_ids=[],
                    )
                ],
                citations=[],
                numbers=[],
                is_estimate=False,
                abstained=True,
            ),
        }

    return {
        "locale": detected_loc,
        "language_state": lang_state,
        "language_candidate": next_candidate,
        "affective_state": affective,
        "redacted_user_text": redaction.redacted_text,
        "safety_flags": sorted(set(flags)),
    }


def output_guard_node(state: ConversationGraphState) -> dict[str, Any]:
    """Execute Stage 11 output guardrails: grounding, numeric provenance, PII leak prevention, and political neutrality."""
    answer = state.get("answer")
    if answer is None:
        return {}

    artifacts = [a.structured_content for a in state.get("artifacts", [])]
    full_text = " ".join(seg.text for seg in answer.segments)

    # Find allowed masked_tin from current subject's artifacts if authenticated
    allowed_masked_tin: str | None = None
    for art in artifacts:
        if "tin_masked" in art:
            allowed_masked_tin = str(art["tin_masked"])
            break

    grounding_res = validate_grounding(answer, tool_artifacts=artifacts)
    num_res = validate_numeric_provenance(answer, tool_artifacts=artifacts)
    pii_res = verify_no_cross_subject_or_unmasked_pii(
        full_text, allowed_masked_tin=allowed_masked_tin
    )
    neutral_res = validate_neutrality_and_promises(full_text)

    failures: list[str] = []
    if not grounding_res.passed and grounding_res.reason:
        failures.append(f"GROUNDING_FAILED:{grounding_res.reason}")
    if not num_res.passed and num_res.reason:
        failures.append(f"NUMERIC_PROVENANCE_FAILED:{num_res.reason}")
    if not pii_res.passed and pii_res.reason:
        failures.append(f"PII_GUARD_FAILED:{pii_res.reason}")
    if not neutral_res.passed and neutral_res.reason:
        failures.append(f"NEUTRALITY_GUARD_FAILED:{neutral_res.reason}")

    if not failures:
        return {
            "validator_feedback": None,
            "safety_flags": sorted(set(state.get("safety_flags", []))),
        }

    flags = list(state.get("safety_flags", [])) + failures
    regen_count = state.get("regeneration_count", 0)
    if regen_count < 1:
        # Section 6.1 Step 9: On failure, regenerate once with feedback
        return {
            "answer": None,
            "regeneration_count": regen_count + 1,
            "validator_feedback": failures[0],
            "safety_flags": sorted(set(flags)),
        }

    # Second failure -> return safe fallback and offer handoff (Section 6.1)
    thread_id = state.get("thread_id", "thr_default")
    ticket = HandoffTicket(
        conversation_id=thread_id,
        reason="GUARD_FALLBACK",
        queue="DOMESTIC_TAX",
        summary=f"Output guard intercepted unverified claim: {failures[0]}",
        citations=[],
        priority="HIGH",
    )
    safe_fallback = Answer(
        segments=[
            AnswerSegment(
                text=(
                    "I do not have sufficient verified SSRA source evidence to state that figure "
                    "or claim safely. I have prepared a handoff to an SSRA officer who can assist "
                    "you, or you can check the official portal at https://etax.nra.gov.ss/."
                ),
                citation_ids=[],
            )
        ],
        citations=[],
        numbers=[],
        is_estimate=False,
        abstained=True,
    )
    return {
        "answer": safe_fallback,
        "validator_feedback": None,
        "handoff_state": ticket,
        "safety_flags": sorted(set(flags)),
    }
