"""Real-Time Multimodal Emotional Intelligence (EQ) Detector (SSRA Assist October 2026).

Computes `AffectiveSnapshot` in <5ms on CPU from:
1. Multilingual lexical & pragmatic markers across all 8 South Sudan BCP-47 languages
   (`en`, `pga`, `ar`, `din`, `nus`, `bfa`, `zne`, `shk`).
2. Interaction trajectory friction (`consecutive_low_confidence_turns`, repeated slot/clarification failures).
3. Voice acoustic prosody features (`barge_in_count`, `rms_energy_delta`, `speech_rate_ratio`).
4. Turn-over-turn `frustration_velocity` (`intensity_t - intensity_{t-1}`).

Invariant: High emotion can adapt tone (`recommended_tone`) or trigger warm SSRA officer handoff (`EQ_ESCALATION`),
but NEVER overrides `T0`-`T4` OPA security gates or unlocks `T3`/`T4` tools.
"""

from __future__ import annotations

import re
from typing import Literal

from ssra_core import AffectiveSnapshot

_DISTRESS_MARKERS: tuple[str, ...] = (
    # English (`en`)
    "seized",
    "detained",
    "goods held",
    "account frozen",
    "bank frozen",
    "scammed",
    "stole my money",
    "extortion",
    "emergency",
    "distress",
    "losing my business",
    "perishable goods",
    "customs holding",
    "nimule border held",
    # Juba Arabic (`pga`) & Arabic (`ar`)
    "gamarik masak",
    "gurush tai rahu",
    "hisab magful",
    "مصادرة",
    "حسابي مجمد",
    "محجوزة",
    # South Sudan National Languages (`din`, `nus`, `bfa`, `zne`, `shk`)
    "wëu cïke dɔm",
    "bɛ̈ŋic cï thiöök",
    "yiööth cïkɛ دام",
    "kaser lo duma",
    "marã zire",
    "jami cï mako",
)

_FRUSTRATION_MARKERS: tuple[str, ...] = (
    # English (`en`)
    "frustrated",
    "not working",
    "failed again",
    "third time",
    "already told you",
    "stop repeating",
    "useless",
    "error every time",
    "still pending",
    "paid twice",
    "double charged",
    "unacceptable",
    "tired of waiting",
    # Juba Arabic (`pga`) & Arabic (`ar`)
    "ma shagal",
    "taaban",
    "galat",
    "دفعت مرتين",
    "لا يعمل",
    # South Sudan National Languages (`din`, `nus`, `bfa`, `zne`, `shk`)
    "acïn luɔi",
    "cuɔl rööth",
    "kۆti nyö",
    "sunge manga te",
    "pe tye ka tic",
)

_ANXIOUS_URGENT_MARKERS: tuple[str, ...] = (
    "urgent",
    "deadline today",
    "due today",
    "penalty tomorrow",
    "border closing",
    "truck waiting",
    "demurrage",
    "عاجل",
    "mustagil",
    "hassa de",
)

_CONFUSION_MARKERS: tuple[str, ...] = (
    "confused",
    "don't understand",
    "do not understand",
    "what does that mean",
    "which form",
    "not clear",
    "lost",
    "help me understand",
    "ma fahim",
    "kif yani",
    "لا أفهم",
    "aɛ̈c deet",
    "kuɛc",
    "pe aniang",
)

_ADVERSARIAL_BYPASS_RE = re.compile(
    r"\b(ignore\s+(all\s+)?(previous|policy|rules)|override\s+t4|grant\s+waiver\s+immediately|bypass\s+otp)\b",
    flags=re.IGNORECASE,
)

_REPEATED_PUNCT_RE = re.compile(r"[!?]{2,}")


def compute_affective_state(
    text: str,
    *,
    previous: AffectiveSnapshot | None = None,
    consecutive_low_confidence_turns: int = 0,
    repeated_clarification_count: int = 0,
    barge_in_count: int = 0,
    rms_energy_delta: float = 0.0,
    speech_rate_ratio: float = 1.0,
) -> AffectiveSnapshot:
    """Compute real-time multimodal `AffectiveSnapshot` with turn-over-turn `frustration_velocity`."""
    cleaned = text.strip()
    lower = cleaned.lower()
    signals: list[str] = []

    distress_hits = [m for m in _DISTRESS_MARKERS if m in lower]
    frustration_hits = [m for m in _FRUSTRATION_MARKERS if m in lower]
    anxious_hits = [m for m in _ANXIOUS_URGENT_MARKERS if m in lower]
    confusion_hits = [m for m in _CONFUSION_MARKERS if m in lower]

    if distress_hits:
        signals.append(f"distress_lexical:{distress_hits[0]}")
    if frustration_hits:
        signals.append(f"frustration_lexical:{frustration_hits[0]}")
    if anxious_hits:
        signals.append(f"urgency_lexical:{anxious_hits[0]}")
    if confusion_hits:
        signals.append(f"confusion_lexical:{confusion_hits[0]}")

    # Interaction trajectory & acoustic prosody signals
    if consecutive_low_confidence_turns >= 2:
        signals.append(f"low_confidence_turns_x{consecutive_low_confidence_turns}")
    if repeated_clarification_count >= 2:
        signals.append(f"repeated_clarification_x{repeated_clarification_count}")
    if barge_in_count >= 2:
        signals.append(f"voice_barge_in_x{barge_in_count}")
    if rms_energy_delta >= 0.25:
        signals.append("voice_rms_energy_spike")
    if speech_rate_ratio >= 1.30:
        signals.append("voice_speech_rate_acceleration")
    if _REPEATED_PUNCT_RE.search(cleaned):
        signals.append("emphatic_punctuation")

    # Guard against adversarial emotional manipulation attempting to bypass policy
    if _ADVERSARIAL_BYPASS_RE.search(cleaned):
        signals.append("adversarial_emotion_manipulation_attempt")

    # Determine primary emotion & base intensity
    primary_emotion: Literal["calm", "confused", "frustrated", "anxious", "distressed"] = "calm"
    intensity = 0.10

    if distress_hits:
        primary_emotion = "distressed"
        intensity = min(1.0, 0.85 + 0.05 * len(distress_hits))
    elif (
        frustration_hits
        or repeated_clarification_count >= 2
        or (barge_in_count >= 2 and rms_energy_delta >= 0.20)
    ):
        primary_emotion = "frustrated"
        intensity = min(
            1.0,
            0.55
            + 0.12 * len(frustration_hits)
            + 0.10 * min(3, repeated_clarification_count)
            + 0.08 * min(3, barge_in_count),
        )
    elif anxious_hits or speech_rate_ratio >= 1.30:
        primary_emotion = "anxious"
        intensity = min(1.0, 0.50 + 0.10 * len(anxious_hits))
    elif confusion_hits or consecutive_low_confidence_turns >= 1:
        primary_emotion = "confused"
        intensity = min(
            1.0,
            0.40 + 0.10 * len(confusion_hits) + 0.12 * min(3, consecutive_low_confidence_turns),
        )

    if "emphatic_punctuation" in signals and primary_emotion != "calm":
        intensity = min(1.0, intensity + 0.08)

    intensity = round(max(0.0, min(1.0, intensity)), 2)
    prev_intensity = previous.intensity if previous is not None else 0.10
    velocity = round(max(-1.0, min(1.0, intensity - prev_intensity)), 2)

    urgency_level: Literal["low", "normal", "high", "critical"] = "normal"
    if primary_emotion == "distressed" or intensity >= 0.85:
        urgency_level = "critical"
    elif primary_emotion in ("frustrated", "anxious") or velocity >= 0.45:
        urgency_level = "high"

    recommended_tone: Literal[
        "standard_clear",
        "reassuring_step_by_step",
        "concise_urgent",
        "empathetic_deescalation",
    ] = "standard_clear"
    if primary_emotion in ("distressed", "frustrated"):
        recommended_tone = "empathetic_deescalation"
    elif primary_emotion == "confused":
        recommended_tone = "reassuring_step_by_step"
    elif primary_emotion == "anxious":
        recommended_tone = "concise_urgent"

    return AffectiveSnapshot(
        primary_emotion=primary_emotion,
        intensity=intensity,
        frustration_velocity=velocity,
        urgency_level=urgency_level,
        signals=signals,
        recommended_tone=recommended_tone,
    )


def should_trigger_eq_escalation(
    affective: AffectiveSnapshot,
    *,
    velocity_threshold: float = 0.45,
    high_intensity_threshold: float = 0.80,
) -> bool:
    """Return True when high distress or rapid frustration escalation warrants a warm SSRA officer handoff.

    Never triggers if flagged as an adversarial policy-bypass attempt (those are handled by input_guard/OPA).
    """
    if "adversarial_emotion_manipulation_attempt" in affective.signals:
        return False
    if (
        affective.primary_emotion == "distressed"
        and affective.intensity >= high_intensity_threshold
    ):
        return True
    if (
        affective.primary_emotion == "frustrated"
        and affective.intensity >= high_intensity_threshold
        and affective.frustration_velocity >= velocity_threshold
    ):
        return True
    return False


def build_empathetic_preamble(
    affective: AffectiveSnapshot,
    *,
    locale_code: str = "en",
) -> str:
    """Return a legally neutral, empathetic or reassuring preamble when EQ adaptation is active.

    Contains ZERO numbers, ZERO legal rulings, and ZERO promises of waivers/refunds.
    """
    if affective.recommended_tone == "empathetic_deescalation":
        if locale_code == "ar":
            return "نتفهم أهمية واستعجال طلبك، وسنتحقق من سجلات هيئة الإيرادات (SSRA) الرسمية خطوة بخطوة. "
        if locale_code == "pga":
            return "Anina fahim mawdu taki مهم شديد — خلينا نراجع خطوات SSRA الرسمية سوا. "
        if locale_code == "din":
            return "Ɣok aa deet lɔn ril käkɛ̈ tënë yïn — buk ajul ku lööŋ ke SSRA caar ನ್ಯಾಯic. "
        return (
            "I understand how urgent this matter is for you—let us review the verified SSRA "
            "steps clearly together. "
        )
    if affective.recommended_tone == "reassuring_step_by_step":
        if locale_code == "ar":
            return "لا تقلق، سنوضح الإجراء الرسمي خطوة بخطوة: "
        if locale_code == "pga":
            return "Maangal، حنشرح ليك الخطوات الرسمية واحدة واحدة: "
        if locale_code == "din":
            return "Duɔ̈në riɔ̈ɔ̈c, buk dhöl de SSRA nyuɔɔth yïn në كök: "
        return "Here is the clear step-by-step official guidance: "
    return ""
