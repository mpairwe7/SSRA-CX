"""Tests for Phase 4 Voice/IVR ASR language gate, Omnilingual ASR routing, DTMF fallback, and recording consent."""

from __future__ import annotations

from ssra_core import LocaleCode
from ssra_voice import ASR_MODEL_BY_LOCALE, is_voice_language_approved, route_voice_turn


def test_voice_asr_model_selection_wer_gate_and_warm_transfer() -> None:
    """Verify ASR/TTS model selection, WER gate, DTMF step-up, hybrid speech router, and spoken figure fidelity."""
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

    # Hybrid Speech Router, Localized Tool-Wait Fillers, Statutory Speech Normalizer & Figure Fidelity
    from ssra_voice import (
        get_localized_tool_wait_filler,
        normalize_statutory_text_for_speech,
        select_hybrid_voice_execution_mode,
        verify_spoken_figure_fidelity,
    )

    fast_ack = select_hybrid_voice_execution_mode(
        locale=LocaleCode.DIN,
        requires_tool_call=False,
        contains_statutory_figures=False,
        is_pure_greeting_or_backchannel=True,
    )
    assert fast_ack.mode == "S2S_FAST_ACK_CACHED"
    assert fast_ack.target_ttfa_ms <= 250

    governed_route = select_hybrid_voice_execution_mode(
        locale=LocaleCode.DIN,
        requires_tool_call=True,
        contains_statutory_figures=True,
    )
    assert governed_route.mode == "CASCADED_GOVERNED_STT_LLM_TTS"
    assert governed_route.emit_tool_wait_filler is True
    assert governed_route.filler_text == get_localized_tool_wait_filler(LocaleCode.DIN)

    norm_speech = normalize_statutory_text_for_speech(
        "For TIN ••••1234 under Part-IV-Sec-18, balance is 450,000 SSP on https://etax.nra.gov.ss/."
    )
    assert "T I N ending in 1 2 3 4" in norm_speech
    assert "Part IV, Section 18" in norm_speech
    assert "e-tax dot n r a dot gov dot s s" in norm_speech
    assert verify_spoken_figure_fidelity(norm_speech, ["450,000"]) is True
    assert verify_spoken_figure_fidelity("450,000 SSP", ["45,000"]) is False
    assert verify_spoken_figure_fidelity(norm_speech, ["999,999"]) is False

    # Full-duplex sub-sentence barge-in recovery & Edge Field-Office Appliance Profile
    from ssra_voice import VoiceStreamSession, resolve_edge_appliance_profile

    v_stream = VoiceStreamSession(session_id="vs_01", locale=LocaleCode.EN)
    assert v_stream.record_partial_transcript("how much") is None
    assert v_stream.record_partial_transcript("how much paye tax do") == "how much paye tax"
    v_stream.trigger_barge_in(sentence_index=1)
    chunks = v_stream.stream_tts_sentences(
        "First sentence spoken. Second interrupted. Third unspoken."
    )
    assert len(chunks) == 1
    assert v_stream.unspoken_sentences == ["Second interrupted.", "Third unspoken."]
    v_stream.reset_barge_in()
    assert v_stream.barge_in_cancelled is False
    assert v_stream.interrupted_at_sentence_index is None

    edge_offline = resolve_edge_appliance_profile(
        office_code="NIMULE_CUSTOMS", backhaul_online=False
    )
    assert edge_offline.llm_model == "ssra-sovereign/qwen2.5-3b-cpu-gguf"
    assert edge_offline.opus_bitrate_kbps == 12
    assert edge_offline.store_and_forward_outbox_enabled is True
    edge_online = resolve_edge_appliance_profile(office_code="JUBA_HQ", backhaul_online=True)
    assert edge_online.backhaul_online is True
    assert edge_online.opus_bitrate_kbps == 24

    from ssra_voice import CallLobbyManager, generate_officer_call_brief

    brief = generate_officer_call_brief(
        call_id="call_01",
        turns=[
            {"speaker": "caller", "text": "My account is blocked and urgent", "seq": 1},
            {"speaker": "assistant", "text": "Checking your e-Tax status.", "seq": 2},
        ],
        transfer_reason="Account freeze verification",
    )
    assert brief.sentiment == "distressed"
    assert brief.turns_covered == 2

    brief_frust = generate_officer_call_brief(
        call_id="call_02",
        turns=[{"speaker": "caller", "text": "It failed with an error", "seq": 1}],
        transfer_reason="Error check",
    )
    assert brief_frust.sentiment == "frustrated"

    brief_conf = generate_officer_call_brief(
        call_id="call_03",
        turns=[{"speaker": "caller", "text": "I am confused how to file", "seq": 1}],
        transfer_reason="Filing help",
    )
    assert brief_conf.sentiment == "confused"

    lobby = CallLobbyManager()
    lobby.apply_event("call.started", {"call_id": "c1"})
    lobby.apply_event("call.transfer_requested", {"call_id": "c1", "reason": "user"})
    lobby.apply_event("call.priority_raised", {"call_id": "c1", "priority": "urgent"})
    lobby.apply_event("call.claimed", {"call_id": "c1", "officer_id": "stf_1"})
    lobby.apply_event("call.officer_disconnected", {"call_id": "c1"})
    lobby.apply_event("call.transfer_timed_out", {"call_id": "c1"})
    lobby.apply_event("call.risk", {"call_id": "c1", "level": "at_risk", "signals": ["high"]})
    lobby.apply_event("call.bridged", {"call_id": "c1"})
    lobby.apply_event("call.on_hold", {"call_id": "c1", "on": True})
    ended = lobby.apply_event("call.ended", {"call_id": "c1"})
    assert ended.status == "ended"

    from ssra_voice import resolve_mt_and_tts_turn_plan, validate_call_wrap_up

    mt_plan = resolve_mt_and_tts_turn_plan(
        source_locale="din",
        original_transcript="Ajul de Ariöp",
        inbound_translated_en="PAYE salary tax",
        english_reply_text="PAYE is due by the 15th.",
        outbound_translated_text="Ajul de Ariöp",
    )
    assert mt_plan["reply_language"] == "din"
    wrap = validate_call_wrap_up(
        note="Resolved PAYE question",
        outcome="resolved",
        caller_satisfaction=5,
        caller_satisfaction_status="answered",
        ai_rating=5,
    )
    assert wrap["outcome"] == "resolved"
