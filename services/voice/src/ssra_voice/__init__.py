"""Phase 4 Voice/IVR ASR Pipeline, DTMF Fallback, Recording Consent & Warm Transfer (Section 11)."""

from __future__ import annotations

from dataclasses import dataclass

from ssra_core import LocaleCode

# Launch a language on voice only after its word-error rate on SSRA test sets meets the gate (<= 0.12)
MAX_VOICE_WER_GATE: float = 0.12

# ASR model selection per Section 11: Whisper-class for en/ar; Meta Omnilingual ASR for pga & local languages
ASR_MODEL_BY_LOCALE: dict[LocaleCode, str] = {
    LocaleCode.EN: "whisper-large-v3-turbo-sovereign",
    LocaleCode.AR: "whisper-large-v3-turbo-sovereign",
    LocaleCode.PGA: "meta-omnilingual-asr-ssra",
    LocaleCode.DIN: "meta-omnilingual-asr-ssra",
    LocaleCode.NUS: "meta-omnilingual-asr-ssra",
    LocaleCode.BFA: "meta-omnilingual-asr-ssra",
    LocaleCode.ZNE: "meta-omnilingual-asr-ssra",
    LocaleCode.SHK: "meta-omnilingual-asr-ssra",
}


@dataclass(frozen=True)
class VoiceSessionDecision:
    session_id: str
    locale: LocaleCode
    asr_engine: str
    recording_enabled: bool
    action: str  # STREAM_ASR | DTMF_MENU | WARM_TRANSFER_TO_OFFICER
    warm_transfer_summary: str | None = None


def is_voice_language_approved(locale: LocaleCode, measured_wer: float) -> bool:
    _ = locale
    return 0.0 <= measured_wer <= MAX_VOICE_WER_GATE


def route_voice_turn(
    *,
    session_id: str,
    locale: LocaleCode,
    measured_wer: float,
    recording_consent_granted: bool,
    dtmf_digit: str | None = None,
    barge_in_detected: bool = False,
) -> VoiceSessionDecision:
    _ = barge_in_detected
    asr_engine = ASR_MODEL_BY_LOCALE[locale]

    if dtmf_digit == "0" or not is_voice_language_approved(locale, measured_wer):
        return VoiceSessionDecision(
            session_id=session_id,
            locale=locale,
            asr_engine=asr_engine,
            recording_enabled=recording_consent_granted,
            action="WARM_TRANSFER_TO_OFFICER",
            warm_transfer_summary=(
                f"Warm transfer from IVR ({locale.value}): caller pressed 0 or language WER "
                f"{measured_wer:.2f} exceeded gate {MAX_VOICE_WER_GATE}."
            ),
        )

    if dtmf_digit is not None:
        return VoiceSessionDecision(
            session_id=session_id,
            locale=locale,
            asr_engine=asr_engine,
            recording_enabled=recording_consent_granted,
            action="DTMF_MENU",
        )

    return VoiceSessionDecision(
        session_id=session_id,
        locale=locale,
        asr_engine=asr_engine,
        recording_enabled=recording_consent_granted,
        action="STREAM_ASR",
    )


__all__ = [
    "ASR_MODEL_BY_LOCALE",
    "MAX_VOICE_WER_GATE",
    "VoiceSessionDecision",
    "is_voice_language_approved",
    "route_voice_turn",
]
