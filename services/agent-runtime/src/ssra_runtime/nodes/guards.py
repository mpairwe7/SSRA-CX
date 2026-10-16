"""Node 3: input_guard & Node 9: output_guard (Section 6.1)."""

from __future__ import annotations

from typing import Any

from ssra_core import Answer, AnswerSegment, HandoffTicket, LocaleCode, RiskTier

from ssra_runtime.guardrails import (
    check_prompt_injection,
    redact_pii,
    validate_grounding,
    validate_neutrality_and_promises,
    validate_numeric_provenance,
    verify_no_cross_subject_or_unmasked_pii,
)
from ssra_runtime.state import ConversationGraphState


def detect_language(text: str, default_locale: LocaleCode = LocaleCode.EN) -> LocaleCode:
    # 1. Detect Arabic script (U+0600..U+06FF)
    if any("\u0600" <= ch <= "\u06ff" for ch in text):
        return LocaleCode.AR
    lower = text.lower()
    # 2. Tier C Nilotic & Central Sudanic languages (Dinka, Nuer, Bari, Zande, Shilluk)
    if any(m in lower for m in ("tënë", "wëu", "ajul", "bɛ̈ŋic", "paguot")):
        return LocaleCode.DIN
    if any(m in lower for m in ("yiööth", "juäärä", "cuɔl", "gɔ̱r", "thok naath")):
        return LocaleCode.NUS
    if any(m in lower for m in ("kaser", "lɔŋɔt", "banki lo", "kegga namba")):
        return LocaleCode.BFA
    if any(m in lower for m in ("marã", "tumosi", "dunduko", "rogo ssra")):
        return LocaleCode.ZNE
    if any(m in lower for m in ("cøøri", "ocul jami", "bëëne", "dhøg")):
        return LocaleCode.SHK
    # 3. Juba Arabic (pga) Latin-script markers & code-switching
    pga_markers = (
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
    )
    if any(m in lower for m in pga_markers):
        return LocaleCode.PGA
    return default_locale


def input_guard_node(state: ConversationGraphState) -> dict[str, Any]:
    raw = state.get("raw_user_text", "")
    default_loc = state.get("locale", LocaleCode.EN)
    detected_loc = detect_language(raw, default_loc)

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
        "redacted_user_text": redaction.redacted_text,
        "safety_flags": sorted(set(flags)),
    }


def output_guard_node(state: ConversationGraphState) -> dict[str, Any]:
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
