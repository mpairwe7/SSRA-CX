"""Tests for Phase 4 Voice/IVR ASR language gate, Omnilingual ASR routing, DTMF fallback, and recording consent."""

from __future__ import annotations

from ssra_core import LocaleCode
from ssra_voice import ASR_MODEL_BY_LOCALE, is_voice_language_approved, route_voice_turn


def test_voice_asr_model_selection_wer_gate_and_warm_transfer() -> None:
    assert "whisper" in ASR_MODEL_BY_LOCALE[LocaleCode.EN]
    assert "omnilingual" in ASR_MODEL_BY_LOCALE[LocaleCode.PGA]
    assert "omnilingual" in ASR_MODEL_BY_LOCALE[LocaleCode.DIN]

    # Language meeting WER gate (<= 0.12) streams ASR
    d1 = route_voice_turn(
        session_id="v_01",
        locale=LocaleCode.PGA,
        measured_wer=0.09,
        recording_consent_granted=False,
    )
    assert d1.action == "STREAM_ASR"
    assert d1.recording_enabled is False

    # Language exceeding WER gate (> 0.12) warm-transfers to an officer with AI summary
    assert is_voice_language_approved(LocaleCode.DIN, 0.18) is False
    d2 = route_voice_turn(
        session_id="v_02",
        locale=LocaleCode.DIN,
        measured_wer=0.18,
        recording_consent_granted=True,
    )
    assert d2.action == "WARM_TRANSFER_TO_OFFICER"
    assert d2.recording_enabled is True
    assert d2.warm_transfer_summary is not None

    # Low utterance confidence (< 0.75) shifts to DTMF menu; 2 consecutive strikes warm-transfer
    from ssra_voice import (
        build_voice_spoken_turn_and_sms_followup,
        verify_voice_dtmf_step_up,
    )

    d_low = route_voice_turn(
        session_id="v_03",
        locale=LocaleCode.EN,
        measured_wer=0.05,
        recording_consent_granted=False,
        utterance_confidence=0.60,
        consecutive_low_confidence_turns=1,
    )
    assert d_low.action == "DTMF_MENU"

    d_strike2 = route_voice_turn(
        session_id="v_04",
        locale=LocaleCode.EN,
        measured_wer=0.05,
        recording_consent_granted=False,
        utterance_confidence=0.55,
        consecutive_low_confidence_turns=2,
    )
    assert d_strike2.action == "WARM_TRANSFER_TO_OFFICER"

    # Voice DTMF step-up blocks spoken OTP and SIM-swap, and masks TIN on keypad entry
    spoken_attempt = verify_voice_dtmf_step_up(
        dtmf_tin_digits="1002001234",
        dtmf_otp_digits="123456",
        input_modality="spoken_asr",
    )
    assert spoken_attempt.authorized is False
    assert spoken_attempt.action == "REJECTED_SPOKEN_OTP"

    t4_attempt = verify_voice_dtmf_step_up(
        dtmf_tin_digits="1002001234",
        dtmf_otp_digits="123456",
        requested_tier="T4",
    )
    assert t4_attempt.action == "WARM_TRANSFER_TO_OFFICER"

    dtmf_ok = verify_voice_dtmf_step_up(
        dtmf_tin_digits="1002001234",
        dtmf_otp_digits="123456",
        input_modality="dtmf_rfc4733",
        requested_tier="T3",
    )
    assert dtmf_ok.authorized is True
    assert dtmf_ok.action == "BOUND_T3"
    assert dtmf_ok.tin_masked == "••••1234"
    assert dtmf_ok.recording_paused_for_dtmf is True

    import pytest
    from ssra_core import SSRAError

    with pytest.raises(SSRAError):
        verify_voice_dtmf_step_up(dtmf_tin_digits="123", dtmf_otp_digits="12")

    followup = build_voice_spoken_turn_and_sms_followup(
        reply_text="Your PAYE is 25,000 SSP per month. File by the 15th. Pay via bank only. Extra fourth sentence omitted.",
        citation_anchor="Taxation Act 2009 Sec 64",
        is_estimate=True,
    )
    assert followup["sentence_count"] == 3
    assert followup["spoken_text"].startswith("Estimate only.")
    assert len(followup["sms_continuation_text"]) <= 160
