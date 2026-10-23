"""Tests for Phase 4 Voice/IVR ASR language gate, Omnilingual ASR routing, DTMF fallback, and recording consent."""

from __future__ import annotations

from ssra_core import LocaleCode
from ssra_voice import ASR_MODEL_BY_LOCALE, is_voice_language_approved, route_voice_turn


class _SyntheticAttemptStore:
    """Test double for the durable per-call attempt store (OQ-015)."""

    def __init__(self) -> None:
        self.failures: dict[str, int] = {}

    def failed_attempts(self, call_id: str) -> int:
        return self.failures.get(call_id, 0)

    def record_failed_attempt(self, call_id: str) -> int:
        self.failures[call_id] = self.failures.get(call_id, 0) + 1
        return self.failures[call_id]


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

    d_clarify = route_voice_turn(
        session_id="v_03_clarify",
        locale=LocaleCode.DIN,
        measured_wer=0.05,
        recording_consent_granted=False,
        utterance_confidence=0.65,
        consecutive_low_confidence_turns=1,
        enable_spoken_clarify_gate=True,
    )
    assert d_clarify.action == "CLARIFY_INTENT_SPOKEN"

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
    store = _SyntheticAttemptStore()
    spoken_attempt = verify_voice_dtmf_step_up(
        dtmf_tin_digits="1002001234",
        dtmf_otp_digits="123456",
        input_modality="spoken_asr",
        call_id="call_dtmf",
        attempt_store=store,
    )
    assert spoken_attempt.authorized is False
    assert spoken_attempt.action == "REJECTED_SPOKEN_OTP"

    t4_attempt = verify_voice_dtmf_step_up(
        dtmf_tin_digits="1002001234",
        dtmf_otp_digits="123456",
        requested_tier="T4",
        call_id="call_dtmf",
        attempt_store=store,
    )
    assert t4_attempt.action == "WARM_TRANSFER_TO_OFFICER"

    no_verifier = verify_voice_dtmf_step_up(
        dtmf_tin_digits="1002001234",
        dtmf_otp_digits="123456",
        input_modality="dtmf_rfc4733",
        requested_tier="T3",
        call_id="call_dtmf",
        attempt_store=store,
    )
    assert no_verifier.authorized is False
    assert no_verifier.action == "WARM_TRANSFER_TO_OFFICER"
    assert no_verifier.tin_masked is None

    def _synthetic_verifier(tin: str, otp: str) -> bool:
        return tin == "1002001234" and otp == "654321"

    # The store counts every rejected code, so the caller cannot reset the three-attempt limit.
    actions = [
        verify_voice_dtmf_step_up(
            dtmf_tin_digits="1002001234",
            dtmf_otp_digits="123456",
            requested_tier="T3",
            otp_verifier=_synthetic_verifier,
            call_id="call_dtmf",
            attempt_store=store,
        ).action
        for _ in range(3)
    ]
    assert actions == ["OTP_REJECTED", "OTP_REJECTED", "WARM_TRANSFER_TO_OFFICER"]
    assert store.failures["call_dtmf"] == 3
    exhausted = verify_voice_dtmf_step_up(
        dtmf_tin_digits="1002001234",
        dtmf_otp_digits="654321",
        requested_tier="T3",
        otp_verifier=_synthetic_verifier,
        call_id="call_dtmf",
        attempt_store=store,
    )
    assert exhausted.authorized is False
    assert exhausted.action == "WARM_TRANSFER_TO_OFFICER"

    def _failing_verifier(tin: str, otp: str) -> bool:
        raise TimeoutError("identity provider timed out")

    class _BrokenStore(_SyntheticAttemptStore):
        def failed_attempts(self, call_id: str) -> int:
            raise OSError("attempt store unavailable")

    for verifier, attempt_store in (
        (_failing_verifier, _SyntheticAttemptStore()),
        (_synthetic_verifier, _BrokenStore()),
    ):
        unavailable = verify_voice_dtmf_step_up(
            dtmf_tin_digits="1002001234",
            dtmf_otp_digits="654321",
            requested_tier="T3",
            otp_verifier=verifier,
            call_id="call_unavailable",
            attempt_store=attempt_store,
        )
        assert (unavailable.authorized, unavailable.action) == (False, "WARM_TRANSFER_TO_OFFICER")
        assert unavailable.tin_masked is None

    dtmf_ok = verify_voice_dtmf_step_up(
        dtmf_tin_digits="1002001234",
        dtmf_otp_digits="654321",
        input_modality="dtmf_rfc4733",
        requested_tier="T3",
        otp_verifier=_synthetic_verifier,
        call_id="call_dtmf_ok",
        attempt_store=store,
    )
    assert dtmf_ok.authorized is True
    assert dtmf_ok.action == "BOUND_T3"
    assert dtmf_ok.tin_masked == "••••1234"
    assert dtmf_ok.recording_paused_for_dtmf is True

    import pytest
    from ssra_core import SSRAError

    with pytest.raises(SSRAError):
        verify_voice_dtmf_step_up(
            dtmf_tin_digits="123", dtmf_otp_digits="12", call_id="call_dtmf", attempt_store=store
        )
    with pytest.raises(SSRAError):
        verify_voice_dtmf_step_up(
            dtmf_tin_digits="1002001234",
            dtmf_otp_digits="654321",
            otp_verifier=_synthetic_verifier,
            call_id=" ",
            attempt_store=store,
        )

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
    assert (
        verify_spoken_figure_fidelity(
            "Balance is 450,000 SSP and 99,000 SSP",
            ["450,000"],
            strict_no_extra_numbers=True,
        )
        is False
    )
    assert (
        verify_spoken_figure_fidelity(
            "Under Section 18, balance is 450,000 SSP",
            ["450,000"],
            strict_no_extra_numbers=True,
            allowed_context_numbers=["18"],
        )
        is True
    )
    assert verify_spoken_figure_fidelity(norm_speech, ["999,999"]) is False

    from ssra_voice import split_tts_sentences

    abbrev_sents = split_tts_sentences(
        "Per Reg. 1.21 and Sec. 18, PAYE is 25,000 SSP. Pay via bank."
    )
    assert len(abbrev_sents) == 2

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
    revived = lobby.apply_event("call.risk", {"call_id": "c1", "level": "watch"})
    assert revived.status == "ended"
    assert "c1" not in lobby.calls

    claim_lobby = CallLobbyManager()
    claim_lobby.apply_event("call.started", {"call_id": "c2"})
    with pytest.raises(ValueError, match="not waiting"):
        claim_lobby.apply_event("call.claimed", {"call_id": "c2", "officer_id": "stf_1"})
    waiting = claim_lobby.apply_event(
        "call.transfer_requested", {"call_id": "c2", "reason": "user"}
    )
    assert waiting.waiting_since is None
    claim_lobby.apply_event("call.claimed", {"call_id": "c2", "officer_id": "stf_1"})
    with pytest.raises(ValueError, match="already claimed"):
        claim_lobby.apply_event("call.claimed", {"call_id": "c2", "officer_id": "stf_2"})
    assert claim_lobby.calls["c2"].claimed_by == "stf_1"
    with pytest.raises(ValueError, match="Unsupported call lobby event"):
        claim_lobby.apply_event("call.teleported", {"call_id": "c2"})
    with pytest.raises(ValueError, match="Unsupported call priority"):
        claim_lobby.apply_event("call.priority_raised", {"call_id": "c2", "priority": "vip"})

    # A rejected event changes nothing, so a call never half-enters the waiting queue.
    partial = CallLobbyManager()
    partial.apply_event("call.started", {"call_id": "c3", "topic": "paye"})
    with pytest.raises(ValueError, match="Unsupported call priority"):
        partial.apply_event(
            "call.transfer_requested", {"call_id": "c3", "priority": "vip", "topic": "vat"}
        )
    assert (partial.calls["c3"].status, partial.calls["c3"].topic) == ("ai", "general")
    with pytest.raises(ValueError, match="not waiting"):
        partial.apply_event("call.claimed", {"call_id": "c3", "officer_id": "stf_1"})
    nan_wait = partial.apply_event(
        "call.transfer_requested", {"call_id": "c3", "waiting_since": float("nan")}
    )
    assert nan_wait.waiting_since is None
    # Only call.started adds a call, so an unknown or evicted call cannot reappear in the queue.
    with pytest.raises(ValueError, match="not in the lobby"):
        partial.apply_event("call.transfer_requested", {"call_id": "c_unknown"})
    assert partial.apply_event("call.ended", {"call_id": "c_never_seen"}).status == "ended"
    assert "c_never_seen" not in partial.calls

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

    from ssra_voice import (
        TtsCachedAudio,
        TtsPhraseCache,
        build_chat_to_call_carryover,
        build_voice_consent_audit_entry,
        looks_like_valid_audio_bytes,
    )

    valid_wav = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 32
    assert looks_like_valid_audio_bytes(valid_wav) is True
    assert looks_like_valid_audio_bytes(b"short") is False

    def _mock_synth(_txt: str, *, language: str, voice: str) -> TtsCachedAudio:
        """Return a synthetic valid WAV audio clip for TTS phrase cache verification."""
        return TtsCachedAudio(
            audio=valid_wav, backend="mms", voice=voice, language=language, latency_ms=12.0
        )

    cache = TtsPhraseCache(max_entries=2)
    r1 = cache.get_or_synthesize(
        "Hello",
        language="en",
        voice="ssra_eng_0001",
        synthesizer=_mock_synth,
    )
    assert r1.backend == "mms"
    r2 = cache.get_or_synthesize(
        "Hello",
        language="en",
        voice="ssra_eng_0001",
        synthesizer=_mock_synth,
    )
    assert r2.backend == "mms+cache"
    assert r2.latency_ms == 0.0

    aud_entry = build_voice_consent_audit_entry(
        event_type="recording_start",
        session_id="vs_01",
        audio_bytes=valid_wav,
    )
    assert aud_entry["raw_audio_stored"] is False
    assert aud_entry["audio_sha256"] is not None

    carry = build_chat_to_call_carryover(
        conversation_id="conv_01",
        owner_user_id="usr_01",
        owner_session_id="ses_01",
        caller_user_id="usr_01",
    )
    assert carry is not None and carry.local_models_only is True

    from ssra_voice import VoiceWebSocketConcurrencyGuard, validate_audio_pcm_expansion_budget

    assert (
        validate_audio_pcm_expansion_budget(compressed_bytes=10_000, duration_seconds=5.0)
        == 320_000
    )
    ws_guard = VoiceWebSocketConcurrencyGuard(per_user_cap=2, global_cap=4)
    ok_acq, _ = ws_guard.try_acquire("anon::1", pool="voice")
    assert ok_acq is True
    assert ws_guard.active_count("voice") == 1
    assert ws_guard.rekey_slot("anon::1", "usr_1", pool="voice") is True
    ws_guard.release("usr_1", pool="voice")
    assert ws_guard.active_count("voice") == 0

    # VR-QW3, VR-QW4, VR-MT2, VR-MT3: Spoken Figure Guard Verbalizer, Live Lobby EQ Sync, CallToWebCarryover & Drop Resumption
    from ssra_voice import (
        build_call_to_web_carryover,
        sync_affective_state_to_call_lobby,
        verbalize_statutory_figures_for_tts,
        verify_call_to_web_carryover,
    )

    verb_en = verbalize_statutory_figures_for_tts(
        "Balance is 450,000 SSP.",
        locale=LocaleCode.EN,
        expected_numeric_values=["450,000"],
    )
    assert verb_en.figures_verified is True
    assert "South Sudanese Pounds" in verb_en.phonetic_tts_text

    with pytest.raises(SSRAError):
        verbalize_statutory_figures_for_tts(
            "Balance is 450,000 SSP.",
            locale=LocaleCode.EN,
            expected_numeric_values=["45,000"],
        )

    lobby_eq = CallLobbyManager()
    lobby_eq.apply_event("call.started", {"call_id": "c_eq"})
    risk_entry = sync_affective_state_to_call_lobby(
        lobby_eq,
        call_id="c_eq",
        primary_emotion="distressed",
        intensity=0.88,
        frustration_velocity=0.55,
        signals=["distress_lexical:seized"],
    )
    assert risk_entry.risk_level == "at_risk"
    assert risk_entry.priority == "urgent"
    repeat_risk = sync_affective_state_to_call_lobby(
        lobby_eq,
        call_id="c_eq",
        primary_emotion="distressed",
        intensity=0.90,
        frustration_velocity=0.10,
        signals=["distress_lexical:seized"],
    )
    assert repeat_risk.risk_level == "at_risk"
    watch_entry = sync_affective_state_to_call_lobby(
        lobby_eq,
        call_id="c_eq",
        primary_emotion="frustrated",
        intensity=0.60,
        frustration_velocity=0.20,
        signals=["frustration_lexical:failed"],
    )
    assert watch_entry.risk_level == "watch"
    calm_entry = sync_affective_state_to_call_lobby(
        lobby_eq,
        call_id="c_eq",
        primary_emotion="calm",
        intensity=0.10,
        frustration_velocity=0.0,
    )
    assert calm_entry.risk_level == "none"

    from dataclasses import replace

    carry_key = "synthetic-test-carryover-key-0123456789"
    with pytest.raises(SSRAError):
        build_call_to_web_carryover(
            call_id="call_01",
            conversation_id="conv_01",
            owner_user_id="usr_01",
            caller_user_id="usr_01",
            signing_salt="too-short",
        )
    c2w = build_call_to_web_carryover(
        call_id="call_01",
        conversation_id="conv_01",
        owner_user_id="usr_01",
        caller_user_id="usr_01",
        signing_salt=carry_key,
        now=1_000_000.0,
    )
    assert c2w is not None and c2w.local_models_only is True
    assert (
        verify_call_to_web_carryover(
            c2w, caller_user_id="usr_01", signing_salt=carry_key, now=1_000_100.0
        )
        is True
    )
    assert (
        verify_call_to_web_carryover(
            c2w, caller_user_id="usr_02", signing_salt=carry_key, now=1_000_100.0
        )
        is False
    )
    assert (
        verify_call_to_web_carryover(
            c2w, caller_user_id="usr_01", signing_salt=carry_key, now=1_000_901.0
        )
        is False
    )
    assert (
        verify_call_to_web_carryover(
            replace(c2w, issued_at=c2w.issued_at + 100),
            caller_user_id="usr_01",
            signing_salt=carry_key,
            now=1_000_100.0,
        )
        is False
    )
    assert (
        verify_call_to_web_carryover(
            replace(c2w, pending_action="tampered_action"),
            caller_user_id="usr_01",
            signing_salt=carry_key,
            now=1_000_100.0,
        )
        is False
    )
    assert (
        verify_call_to_web_carryover(
            replace(c2w, local_models_only=False),
            caller_user_id="usr_01",
            signing_salt=carry_key,
            now=1_000_100.0,
        )
        is False
    )
    assert (
        build_call_to_web_carryover(
            call_id="call_01",
            conversation_id="conv_01",
            owner_user_id="usr_01",
            caller_user_id="usr_02",
            signing_salt=carry_key,
        )
        is None
    )

    resumed_chunks = v_stream.resume_after_network_drop(
        "First sentence acked. Second resumed. Third resumed.",
        last_acked_sentence_index=0,
    )
    assert len(resumed_chunks) == 2
    assert resumed_chunks[0]["sentence_index"] == 1
