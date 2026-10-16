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
