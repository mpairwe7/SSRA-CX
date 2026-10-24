"""Tests for Phase 4 Voice/IVR ASR language gate, Omnilingual ASR routing, DTMF fallback, and recording consent."""

from __future__ import annotations

from datetime import date

from ssra_core import LocaleCode
from ssra_voice import (
    ASR_MODEL_BY_LOCALE,
    VoiceWerEvidence,
    is_voice_language_approved,
    route_voice_turn,
)


def _synthetic_wer(locale: LocaleCode, wer: float) -> dict[LocaleCode, VoiceWerEvidence]:
    """Return synthetic launch evidence for one language; no real measurement exists (OQ-008)."""
    return {
        locale: VoiceWerEvidence(
            locale=locale,
            word_error_rate=wer,
            test_set="synthetic-unit-test-set",
            measured_on=date(2026, 10, 24),
            utterance_count=200,
        )
    }


def test_voice_language_gate_requires_governed_evidence() -> None:
    """No language is approved without evidence, and the transfer summary states the real reasons."""
    assert is_voice_language_approved(LocaleCode.EN) is False
    assert is_voice_language_approved(LocaleCode.PGA, _synthetic_wer(LocaleCode.PGA, 0.12)) is True
    assert is_voice_language_approved(LocaleCode.PGA, _synthetic_wer(LocaleCode.DIN, 0.05)) is False
    assert (
        is_voice_language_approved(LocaleCode.DIN, _synthetic_wer(LocaleCode.DIN, float("nan")))
        is False
    )

    unmeasured = route_voice_turn(
        session_id="v_none", locale=LocaleCode.EN, recording_consent_granted=False
    )
    assert unmeasured.action == "WARM_TRANSFER_TO_OFFICER"
    assert unmeasured.warm_transfer_summary == (
        "Warm transfer from IVR (en): no approved word-error-rate evidence for en (OQ-008)."
    )
    pressed_zero = route_voice_turn(
        session_id="v_zero",
        locale=LocaleCode.EN,
        recording_consent_granted=False,
        wer_evidence=_synthetic_wer(LocaleCode.EN, 0.05),
        dtmf_digit="0",
    )
    assert pressed_zero.warm_transfer_summary == (
        "Warm transfer from IVR (en): caller pressed 0 for an officer."
    )


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
        wer_evidence=_synthetic_wer(LocaleCode.PGA, 0.09),
        recording_consent_granted=False,
    )
    assert d1.action == "STREAM_ASR"
    assert d1.recording_enabled is False

    # Language exceeding WER gate (> 0.12) warm-transfers to an officer with AI summary
    assert is_voice_language_approved(LocaleCode.DIN, _synthetic_wer(LocaleCode.DIN, 0.18)) is False
    d2 = route_voice_turn(
        session_id="v_02",
        locale=LocaleCode.DIN,
        wer_evidence=_synthetic_wer(LocaleCode.DIN, 0.18),
        recording_consent_granted=True,
    )
    assert d2.action == "WARM_TRANSFER_TO_OFFICER"
    assert d2.recording_enabled is True
    assert d2.warm_transfer_summary == (
        "Warm transfer from IVR (din): din word-error rate 0.18 on synthetic-unit-test-set "
        "is above the 0.12 gate."
    )

    # Low utterance confidence (< 0.75) shifts to DTMF menu; 2 consecutive strikes warm-transfer
    from ssra_voice import (
        build_voice_spoken_turn_and_sms_followup,
        verify_voice_dtmf_step_up,
    )

    d_low = route_voice_turn(
        session_id="v_03",
        locale=LocaleCode.EN,
        wer_evidence=_synthetic_wer(LocaleCode.EN, 0.05),
        recording_consent_granted=False,
        utterance_confidence=0.60,
        consecutive_low_confidence_turns=1,
    )
    assert d_low.action == "DTMF_MENU"

    d_clarify = route_voice_turn(
        session_id="v_03_clarify",
        locale=LocaleCode.DIN,
        wer_evidence=_synthetic_wer(LocaleCode.DIN, 0.05),
        recording_consent_granted=False,
        utterance_confidence=0.65,
        consecutive_low_confidence_turns=1,
        enable_spoken_clarify_gate=True,
    )
    assert d_clarify.action == "CLARIFY_INTENT_SPOKEN"

    d_strike2 = route_voice_turn(
        session_id="v_04",
        locale=LocaleCode.EN,
        wer_evidence=_synthetic_wer(LocaleCode.EN, 0.05),
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
    assert brief.model is None
    assert brief.still_open[0].text == "Latest caller request: My account is blocked and urgent"
    assert brief.still_open[0].turn_seqs == [1]

    long_call = generate_officer_call_brief(
        call_id="call_04",
        turns=[
            {"speaker": "caller", "text": "Show me my filing options", "seq": 1},
            {"speaker": "assistant", "text": "Reply one.", "seq": 2},
            {"speaker": "assistant", "text": "Reply two.", "seq": 3},
            {"speaker": "assistant", "text": "Reply three.", "seq": 4},
            {"speaker": "assistant", "text": "Reply four.", "seq": 5},
            {"speaker": "caller", "text": "My TIN is 1002001234 and nobody helps", "seq": 6},
        ],
        transfer_reason="Caller asked for an officer",
    )
    assert [c.turn_seqs for c in long_call.ai_already_said] == [[3], [4], [5]]
    boundary = generate_officer_call_brief(
        call_id="call_06",
        turns=[
            {"speaker": "caller", "text": "What is my TIN?", "seq": 1},
            {"speaker": "assistant", "text": "x" * 134 + " 1002001234 is on file.", "seq": 2},
        ],
        transfer_reason="Caller asked for an officer",
    )
    assert all("10020" not in c.text for c in boundary.ai_already_said)
    assert long_call.sentiment == "calm"
    assert "1002001234" not in long_call.still_open[0].text
    assert all("filing/payment" not in c.text for c in long_call.still_open)
    unsequenced = generate_officer_call_brief(
        call_id="call_05",
        turns=[{"speaker": "caller", "text": "Hello"}],
        transfer_reason="Caller asked for an officer",
    )
    assert unsequenced.caller_goal.turn_seqs == []

    brief_frust = generate_officer_call_brief(
        call_id="call_02",
        turns=[{"speaker": "caller", "text": "It failed with an error", "seq": 1}],
        transfer_reason="Error check",
    )
    assert brief_frust.sentiment == "frustrated"
    assert (
        generate_officer_call_brief(
            call_id="call_02b",
            turns=[
                {
                    "speaker": "caller",
                    "text": "I keep getting errors and this is frustrating",
                    "seq": 1,
                }
            ],
            transfer_reason="Error check",
        ).sentiment
        == "frustrated"
    )
    assert (
        generate_officer_call_brief(
            call_id="call_02c",
            turns=[{"speaker": "caller", "text": "There is a seizure notice", "seq": 1}],
            transfer_reason="Seizure notice",
        ).sentiment
        == "distressed"
    )

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
    claim_lobby.apply_event("call.risk", {"call_id": "c2", "level": "at_risk"})
    with pytest.raises(ValueError, match="Unsupported call risk level"):
        claim_lobby.apply_event("call.risk", {"call_id": "c2", "level": "AT_RISK"})
    assert claim_lobby.calls["c2"].risk_level == "at_risk"

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
    filler = get_localized_tool_wait_filler(LocaleCode.EN)
    r1 = cache.get_or_synthesize(
        filler,
        language="en",
        voice="ssra_eng_0001",
        synthesizer=_mock_synth,
    )
    assert r1.backend == "mms"
    r2 = cache.get_or_synthesize(
        filler,
        language="en",
        voice="ssra_eng_0001",
        synthesizer=_mock_synth,
    )
    assert r2.backend == "mms+cache"
    assert r2.latency_ms == 0.0
    personal = "Your PAYE for this month is 25,000 SSP."
    for _ in range(2):
        r_personal = cache.get_or_synthesize(
            personal, language="en", voice="ssra_eng_0001", synthesizer=_mock_synth
        )
        assert r_personal.backend == "mms"

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


def test_voice_caller_output_disclosure_barge_in_and_asr_guard() -> None:
    """R2-K: what the caller hears and receives (AUD-041, AUD-042, AUD-044)."""
    import re

    from ssra_core import count_sms_segments
    from ssra_voice import (
        VoiceStreamSession,
        WhisperSegmentSignals,
        assess_whisper_segment,
        build_call_opening_prompts,
        build_voice_spoken_turn_and_sms_followup,
        fixed_voice_prompts,
        resolve_recording_consent,
        verify_spoken_figure_fidelity,
    )

    # SMS follow-up: automated label, citation kept, whole sentences only, within 160 characters.
    reply = (
        "Your PAYE for this month is 25,000 SSP. File the return through the e-Tax portal by the "
        "15th day of the following month. Pay only through a designated bank, never in cash."
    )
    followup = build_voice_spoken_turn_and_sms_followup(
        reply_text=reply, citation_anchor="Taxation Act 2009 Sec 64", is_estimate=True
    )
    sms = followup["sms_continuation_text"]
    assert sms.startswith("SSRA Assist (automated): Estimate only.")
    assert "SSRA OFFICIAL" not in sms
    assert sms.endswith("(Taxation Act 2009 Sec 64) Ref: https://etax.nra.gov.ss/")
    assert len(sms) <= 160
    assert followup["sms_segments"] == 1 and count_sms_segments(sms) == 1
    assert followup["sms_shortened"] is True
    for figure in re.findall(r"\d[\d,]*", sms.split("(Taxation")[0]):
        assert figure in reply
    arabic = build_voice_spoken_turn_and_sms_followup(
        reply_text="ضريبة الدخل الشهرية هي ٢٥٬٠٠٠ جنيه. ادفع عبر البنك فقط.", is_estimate=False
    )
    assert "٢٥٬٠٠٠ جنيه." in arabic["sms_continuation_text"]
    assert (arabic["sms_encoding"], arabic["sms_segments"]) == ("UCS-2", 2)

    # Figure guard: spelled-out English numbers and Arabic-Indic digits are figures too.
    contradictory = "Tax Compliance Certificates are valid for twelve (3) months only."
    assert (
        verify_spoken_figure_fidelity(contradictory, ["3"], strict_no_extra_numbers=True) is False
    )
    assert verify_spoken_figure_fidelity(
        "Ten percent (10%) applies.", ["10"], strict_no_extra_numbers=True
    )
    assert verify_spoken_figure_fidelity("PAYE is twenty five thousand SSP.", ["25,000"])
    assert verify_spoken_figure_fidelity("PAYE is twenty five thousand SSP.", ["30,000"]) is False
    assert verify_spoken_figure_fidelity("Two thousand five hundred SSP.", ["2,500"])
    assert verify_spoken_figure_fidelity("الرصيد ٤٥٠٬٠٠٠ جنيه", ["450,000"])
    assert (
        verify_spoken_figure_fidelity(
            "الرصيد ٤٥٠٬٠٠٠ جنيه", ["45,000"], strict_no_extra_numbers=True
        )
        is False
    )
    assert verify_spoken_figure_fidelity("Use one of the forms.", [], strict_no_extra_numbers=True)
    assert (
        verify_spoken_figure_fidelity("Wait one month.", [], strict_no_extra_numbers=True) is False
    )

    # Every call opens with the AI disclosure; recording needs an explicit keypad 1.
    opening = build_call_opening_prompts(LocaleCode.DIN, recording_offered=True)
    assert [p.prompt_id for p in opening] == ["ai_disclosure", "recording_consent"]
    assert opening[0].interruptible_by_speech is False
    assert opening[0].spoken_locale == LocaleCode.EN  # no reviewed Dinka wording yet
    assert opening[0].wording_approved is False
    assert "automated" in opening[0].text and "press 0" in opening[0].text
    assert [
        p.prompt_id for p in build_call_opening_prompts(LocaleCode.EN, recording_offered=False)
    ] == ["ai_disclosure"]
    assert opening[0].text in fixed_voice_prompts()
    assert resolve_recording_consent("1") is True
    assert not any(resolve_recording_consent(d) for d in ("2", "9", "#", None))

    # Barge-in stops playback and cancels generation together; noise and the disclosure are ignored.
    session = VoiceStreamSession(session_id="vs_barge", locale=LocaleCode.EN)
    assert session.trigger_barge_in(speech_ms=120) is None
    assert session.trigger_barge_in(speech_ms=900, prompt_interruptible=False) is None
    assert len(session.stream_tts_sentences("One. Two. Three.")) == 3
    directive = session.trigger_barge_in(sentence_index=1, speech_ms=400)
    assert directive is not None
    assert (directive.stop_playback, directive.cancel_generation, directive.flush_queued_audio) == (
        True,
        True,
        True,
    )
    assert len(session.stream_tts_sentences("One. Two. Three.")) == 1
    barged = route_voice_turn(
        session_id="v_barge",
        locale=LocaleCode.EN,
        recording_consent_granted=False,
        wer_evidence=_synthetic_wer(LocaleCode.EN, 0.05),
        barge_in_detected=True,
    )
    assert (barged.action, barged.cancel_active_reply) == ("STREAM_ASR", True)

    # Whisper text produced on silence or as a repetition loop never reaches the runtime.
    silent = WhisperSegmentSignals(no_speech_prob=0.92, avg_logprob=-1.4, compression_ratio=1.1)
    looping = WhisperSegmentSignals(no_speech_prob=0.05, avg_logprob=-0.3, compression_ratio=3.2)
    clean = WhisperSegmentSignals(no_speech_prob=0.05, avg_logprob=-0.3, compression_ratio=1.4)
    assert assess_whisper_segment(silent) == "no_speech"
    assert assess_whisper_segment(looping) == "unreliable"
    assert assess_whisper_segment(clean) == "accept"
    assert assess_whisper_segment(WhisperSegmentSignals(float("nan"), -0.3, 1.4)) == "unreliable"
    hallucinated = route_voice_turn(
        session_id="v_silence",
        locale=LocaleCode.EN,
        recording_consent_granted=False,
        wer_evidence=_synthetic_wer(LocaleCode.EN, 0.05),
        utterance_confidence=0.97,
        whisper_signals=silent,
    )
    assert hallucinated.action == "DTMF_MENU"
    assert hallucinated.asr_rejected_reason == "no speech detected"


def test_voice_multiturn_call_session_echo_guard_and_recovery() -> None:
    """ADR-027: multi-turn call continuity, post-TTS echo guard, backchannel immunity, and recovery."""
    from ssra_voice import (
        POST_TTS_ECHO_COOLDOWN_MS,
        VoiceCallSession,
        is_backchannel_utterance,
        is_likely_tts_echo,
    )

    assert POST_TTS_ECHO_COOLDOWN_MS == 450
    assert is_backchannel_utterance("mm-hm") is True
    assert is_backchannel_utterance("Okay") is True
    assert is_backchannel_utterance("نعم") is True
    assert is_backchannel_utterance("wait stop talking") is False

    assistant_line = (
        "Your PAYE return is due by the fifteenth day of the following month via the e-Tax portal."
    )
    assert (
        is_likely_tts_echo(
            "following month via the e-Tax portal",
            assistant_line,
            elapsed_since_tts_end_ms=180,
        )
        is True
    )
    assert (
        is_likely_tts_echo(
            "What is the PAYE filing deadline?",
            assistant_line,
            elapsed_since_tts_end_ms=180,
        )
        is False
    )
    assert is_likely_tts_echo("", assistant_line) is False
    assert (
        is_likely_tts_echo(
            "no",
            "Please let us know your question.",
            elapsed_since_tts_end_ms=100,
        )
        is False
    )
    assert (
        is_likely_tts_echo(
            "PAYE return due fifteenth",
            assistant_line,
            elapsed_since_tts_end_ms=200,
        )
        is True
    )
    assert (
        is_likely_tts_echo(
            "Your PAYE return is due by the fifteenth",
            assistant_line,
            elapsed_since_tts_end_ms=900,
        )
        is True
    )

    # Keypad 0 during recording consent transfers immediately; keypad 1 via process_caller_turn grants consent.
    call_zero = VoiceCallSession(
        session_id="call_zero",
        locale=LocaleCode.EN,
        wer_evidence=_synthetic_wer(LocaleCode.EN, 0.05),
    )
    call_zero.start_call()
    assert call_zero.phase == "opening_disclosure"
    assert call_zero.disclosure_playing is True
    # Spoken input while the non-interruptible AI disclosure plays is ignored without advancing phase.
    blocked_during_disclosure = call_zero.process_caller_turn(
        transcript="What is the PAYE rate?",
        assistant_speaking=True,
    )
    assert blocked_during_disclosure.decision is None
    assert call_zero.phase == "opening_disclosure"
    # Keypad 0 still transfers even during disclosure.
    zero_from_turn = call_zero.process_caller_turn(dtmf_digit="0")
    assert zero_from_turn.phase == "transferred"
    assert (
        zero_from_turn.decision is not None
        and zero_from_turn.decision.action == "WARM_TRANSFER_TO_OFFICER"
    )

    call_zero_consent = VoiceCallSession(
        session_id="call_zero_consent",
        locale=LocaleCode.EN,
        wer_evidence=_synthetic_wer(LocaleCode.EN, 0.05),
    )
    call_zero_consent.start_call()
    zero_out = call_zero_consent.submit_recording_consent("0")
    assert zero_out.phase == "transferred"
    assert zero_out.decision is not None and zero_out.decision.action == "WARM_TRANSFER_TO_OFFICER"

    call_direct = VoiceCallSession(
        session_id="call_direct",
        locale=LocaleCode.EN,
        wer_evidence=_synthetic_wer(LocaleCode.EN, 0.05),
    )
    call_direct.start_call()
    call_direct.mark_disclosure_finished()
    assert call_direct.phase == "recording_consent"
    assert call_direct.process_caller_turn(dtmf_digit="1").phase == "active_ai"
    assert call_direct.recording_consent_granted is True
    assert (
        call_direct.record_assistant_reply("Full spoken reply with no interruption.")
        == "Full spoken reply with no interruption."
    )

    call_unspoken_consent = VoiceCallSession(
        session_id="call_unspoken_consent",
        locale=LocaleCode.EN,
        wer_evidence=_synthetic_wer(LocaleCode.EN, 0.05),
    )
    call_unspoken_consent.start_call()
    call_unspoken_consent.mark_disclosure_finished()
    direct_turn = call_unspoken_consent.process_caller_turn(
        transcript="What is the business profit tax rate?",
        elapsed_since_tts_end_ms=800,
        utterance_confidence=0.95,
    )
    assert direct_turn.phase == "active_ai"

    call = VoiceCallSession(
        session_id="call_multi_01",
        locale=LocaleCode.EN,
        wer_evidence=_synthetic_wer(LocaleCode.EN, 0.05),
    )
    prompts = call.start_call()
    assert len(prompts) == 2
    assert call.phase == "opening_disclosure"
    call.mark_disclosure_finished()
    assert call.phase == "recording_consent"

    # Declining recording (keypad 2) keeps the AI conversation active without recording.
    consent_out = call.submit_recording_consent("2")
    assert consent_out.phase == "active_ai"
    assert call.recording_consent_granted is False

    # Turn 1: clear question succeeds with STREAM_ASR.
    t1 = call.process_caller_turn(
        transcript="When is the monthly PAYE return due?",
        elapsed_since_tts_end_ms=800,
        utterance_confidence=0.94,
    )
    assert t1.decision is not None and t1.decision.action == "STREAM_ASR"
    assert t1.turn_index == 1

    # Assistant speaks reply, interrupted at sentence 1: only spoken sentence is retained as heard context.
    heard = call.record_assistant_reply(
        "Your PAYE return is due by the 15th day of the following month. Pay through an approved bank.",
        interrupted_at_sentence=1,
    )
    assert heard == "Your PAYE return is due by the 15th day of the following month."
    assert call.last_interrupted_unspoken_text == "Pay through an approved bank."

    # Acoustic echo right after TTS ends (within 450 ms) is ignored without consuming a turn.
    echo_out = call.process_caller_turn(
        transcript="due by the 15th day of the following month",
        elapsed_since_tts_end_ms=220,
        utterance_confidence=0.91,
    )
    assert echo_out.ignored_as_echo is True
    assert echo_out.decision is None
    assert call.turn_index == 1

    # Listener backchannel ("uh-huh") while assistant speaks is ignored without cancelling reply.
    bc_out = call.process_caller_turn(
        transcript="uh-huh",
        assistant_speaking=True,
        utterance_confidence=0.92,
    )
    assert bc_out.ignored_as_backchannel is True
    assert bc_out.decision is None

    # Turn 2: single low-confidence turn asks for spoken clarification.
    t2_low = call.process_caller_turn(
        transcript="how about withholding",
        elapsed_since_tts_end_ms=900,
        utterance_confidence=0.66,
    )
    assert t2_low.decision is not None and t2_low.decision.action == "CLARIFY_INTENT_SPOKEN"
    assert t2_low.consecutive_low_confidence_turns == 1

    # Turn 3: caller repeats clearly -> consecutive_low_confidence_turns resets to 0 and conversation continues!
    t3_recovered = call.process_caller_turn(
        transcript="What is the withholding tax rate on a contract invoice?",
        elapsed_since_tts_end_ms=900,
        utterance_confidence=0.95,
    )
    assert t3_recovered.decision is not None and t3_recovered.decision.action == "STREAM_ASR"
    assert t3_recovered.consecutive_low_confidence_turns == 0
    assert call.phase == "active_ai"

    # Two consecutive low-confidence turns escalate to an officer.
    call.process_caller_turn(
        transcript="mumble one", elapsed_since_tts_end_ms=700, utterance_confidence=0.62
    )
    t5_esc = call.process_caller_turn(
        transcript="mumble two", elapsed_since_tts_end_ms=700, utterance_confidence=0.61
    )
    assert t5_esc.decision is not None and t5_esc.decision.action == "WARM_TRANSFER_TO_OFFICER"
    assert call.phase == "transferred"


def test_receptionist_spoken_intent_control_offer_review_and_sentence_splitter() -> None:
    """FinalYearProject brain.py & review.py parity: spoken zero-out, controls, offer reply, review & procedure splitting."""
    from ssra_voice import (
        classify_pending_offer_reply,
        classify_spoken_call_review,
        is_callback_request,
        is_goodbye_request,
        is_normal_pace_request,
        is_repeat_request,
        is_slower_pace_request,
        is_spoken_officer_request,
        is_tax_dispute,
        split_receptionist_spoken_sentences,
    )

    assert is_spoken_officer_request("Connect me to an officer please") is True
    assert is_spoken_officer_request("Officer, please.") is True
    assert is_spoken_officer_request("أريد موظف") is True
    assert is_spoken_officer_request("What does a tax officer do?") is False

    assert is_tax_dispute("I want to appeal this assessment at the tribunal") is True
    assert is_tax_dispute("What is the PAYE filing deadline?") is False

    assert is_repeat_request("Could you repeat that?") is True
    assert (
        is_repeat_request("I said repeat that to my accountant when filing PAYE returns yesterday")
        is False
    )
    assert is_slower_pace_request("Please speak slower") is True
    assert is_normal_pace_request("Speak at normal speed") is True
    assert is_callback_request("Can you call me back later?") is True
    assert is_goodbye_request("That's all, thank you") is True
    assert is_goodbye_request("Goodbye") is True
    assert is_goodbye_request("That is all the money I have for tax") is False

    assert classify_pending_offer_reply("", "officer") == "none"
    assert classify_pending_offer_reply("Yes, please connect me", "officer") == "accept"
    assert classify_pending_offer_reply("No, I'm fine thanks", "officer") == "decline"
    assert classify_pending_offer_reply("Tell me more", "officer") == "none"
    assert classify_pending_offer_reply("Tell me more", "more") == "accept"
    assert classify_pending_offer_reply("Yes, and what is the excise rate?", "officer") == "none"

    assert classify_spoken_call_review("") == "unclear"
    assert classify_spoken_call_review("No, thank you") == "unclear"
    assert classify_spoken_call_review("Not too bad") == "neutral"
    assert classify_spoken_call_review("It was not helpful at all") == "negative"
    assert classify_spoken_call_review("Sort of") == "neutral"
    assert classify_spoken_call_review("Very helpful, thank you") == "positive"
    assert classify_spoken_call_review("Yes") == "positive"
    assert classify_spoken_call_review("No") == "negative"
    assert classify_spoken_call_review("Fine") == "neutral"
    assert classify_spoken_call_review("Purple elephant") == "unclear"

    proc_text = (
        "Happy to help! To register for a TIN in South Sudan: "
        "1. Open the e-Tax portal 2. Upload your company certificate, e.g. Form A 3. Submit the form. "
        "The standard rate is 18. Thank you."
    )
    split_proc = split_receptionist_spoken_sentences(proc_text)
    assert len(split_proc) == 4
    assert split_proc[1].startswith("To register for a TIN in South Sudan: 1. Open")
    assert split_proc[1].endswith("3. Submit the form.")
    assert split_proc[2] == "The standard rate is 18."
    assert split_proc[3] == "Thank you."
    assert split_receptionist_spoken_sentences(
        "1. Visit the portal.\n2. Open TIN Registration."
    ) == [
        "1. Visit the portal.",
        "2. Open TIN Registration.",
    ]


def test_voice_call_session_controls_pending_offers_interruption_and_transfer_epoch() -> None:
    """FinalYearProject brain.py, state.py & transfer.py parity inside VoiceCallSession."""
    from ssra_voice import VoiceCallSession

    session = VoiceCallSession(
        session_id="call_brain_01",
        locale=LocaleCode.EN,
        recording_offered=False,
        wer_evidence=_synthetic_wer(LocaleCode.EN, 0.05),
    )
    session.start_call()
    session.mark_disclosure_finished()
    assert session.phase == "active_ai"

    session.record_assistant_reply("Monthly PAYE returns are due by the 15th.")
    state_frame = session.build_call_state_frame(turn_phase="listening")
    assert state_frame["type"] == "call_state"
    assert state_frame["has_last_answer"] is True
    assert state_frame["speech_rate_slow"] is False

    # Control actions: slower, normal_speed, repeat, more_detail
    slow_out = session.handle_call_control("slower")
    assert slow_out.speech_rate_slow is True
    assert slow_out.control_action_applied == "slower"

    norm_out = session.handle_call_control("normal_speed")
    assert norm_out.speech_rate_slow is False
    assert norm_out.control_action_applied == "normal_speed"

    rep_out = session.handle_call_control("repeat")
    assert rep_out.control_action_applied == "repeat"
    assert (
        rep_out.spoken_response_text
        == "Sure, let me repeat that: Monthly PAYE returns are due by the 15th."
    )

    # Pending offer interrupted by barge-in: saying 'yes' over the answer re-asks the offer question!
    session.set_pending_offer(
        "officer",
        reason="complex_case",
        more_detail="Additional penalty rules apply under Section 42.",
        at_risk=True,
    )
    assert session.risk_offer_made is True
    session.record_assistant_reply(
        "First sentence of the answer. Would you like to speak with an officer?",
        interrupted_at_sentence=1,
    )
    assert session.offer_interrupted is True
    reask_out = session.process_caller_turn(transcript="okay", elapsed_since_tts_end_ms=700)
    assert reask_out.control_action_applied == "reask_unheard_offer"
    assert session.pending_offer == "officer"
    assert session.phase == "active_ai"

    # If interrupted again and caller asks a new question instead of yes/no, risk_offer_made resets.
    session.offer_interrupted = True
    new_q_out = session.process_caller_turn(
        transcript="What is the withholding tax rate?",
        elapsed_since_tts_end_ms=700,
    )
    assert new_q_out.decision is not None and new_q_out.decision.action == "STREAM_ASR"
    assert session.risk_offer_made is False

    # Persistent last_more_detail_text works even after offer lapsed
    more_spoken = session.process_caller_turn(
        transcript="tell me more", elapsed_since_tts_end_ms=700
    )
    assert more_spoken.control_action_applied == "more_detail"
    assert more_spoken.spoken_response_text == "Additional penalty rules apply under Section 42."

    # Pending 'more' offer accept & decline, plus repeat/pace preserving pending offer
    session.set_pending_offer("more", more_detail="Step 3 is bank payment confirmation.")
    rep_with_offer = session.process_caller_turn(
        transcript="repeat that", elapsed_since_tts_end_ms=700
    )
    assert rep_with_offer.control_action_applied == "repeat"
    assert session.pending_offer == "more"

    slow_with_offer = session.process_caller_turn(
        transcript="speak slower", elapsed_since_tts_end_ms=700
    )
    assert slow_with_offer.control_action_applied == "slower"
    assert session.pending_offer == "more"

    norm_with_offer = session.process_caller_turn(
        transcript="normal speed", elapsed_since_tts_end_ms=700
    )
    assert norm_with_offer.control_action_applied == "normal_speed"
    assert session.pending_offer == "more"

    accept_more = session.handle_call_control("accept_offer")
    assert accept_more.control_action_applied == "offer_accepted_more"
    assert accept_more.spoken_response_text == "Step 3 is bank payment confirmation."

    session.set_pending_offer("more", more_detail="Extra detail to discard.")
    decline_more = session.handle_call_control("decline_offer")
    assert decline_more.control_action_applied == "offer_declined"
    assert session.last_more_detail_text == ""

    # Accept officer offer -> transfers & bumps queue_epoch
    session.set_pending_offer("officer", reason="caller_needs_help")
    accept_off = session.handle_call_control("accept_offer")
    assert accept_off.control_action_applied == "offer_accepted_officer"
    assert session.phase == "transferred"
    assert session.queue_epoch >= 1

    # While transferring, caller says "call me back later" -> ends wait and sets needs_callback
    cb_out = session.process_caller_turn(
        transcript="Please call me back later", elapsed_since_tts_end_ms=700
    )
    assert cb_out.control_action_applied == "callback_requested"
    assert session.needs_callback is True
    assert session.phase == "active_ai"

    # Direct request_callback when not in transferred phase also records needs_callback
    cb_direct = session.handle_call_control("request_callback")
    assert cb_direct.control_action_applied == "callback_requested"
    assert session.needs_callback is True
    session.end_transfer_wait(timed_out=False)

    # Spoken officer request in active_ai transfers immediately
    off_req = session.process_caller_turn(
        transcript="Please connect me to an officer",
        elapsed_since_tts_end_ms=700,
    )
    assert off_req.control_action_applied == "spoken_officer_request"
    assert session.phase == "transferred"

    # While in transferred phase, a general utterance keeps the caller waiting without re-triggering route_voice_turn
    hold_out = session.process_caller_turn(
        transcript="Hello, am I still in the queue?",
        elapsed_since_tts_end_ms=700,
    )
    assert hold_out.control_action_applied == "waiting_for_officer"
    assert session.phase == "transferred"

    # Return to active_ai, test spoken review offer, test spoken tax-dispute escalation, then test goodbye hangup
    session.end_transfer_wait(timed_out=True)
    session.set_pending_offer("review")
    rev_out = session.process_caller_turn(
        transcript="Yes, very helpful thank you",
        elapsed_since_tts_end_ms=700,
    )
    assert rev_out.control_action_applied == "review_recorded"
    assert session.spoken_review_rating == "positive"

    # History FIFO bound (100 entries) and PII redaction
    for i in range(105):
        session.record_assistant_reply(f"Step {i} guidance.")
    assert len(session.history) == 100

    dispute_out = session.process_caller_turn(
        transcript="I want to appeal this assessment at the tribunal",
        elapsed_since_tts_end_ms=700,
    )
    assert dispute_out.control_action_applied == "tax_dispute_escalation"
    assert session.phase == "transferred"

    # Goodbye while in transferred phase ends the call cleanly
    bye_from_transfer = session.process_caller_turn(
        transcript="Goodbye",
        elapsed_since_tts_end_ms=700,
    )
    assert bye_from_transfer.control_action_applied == "caller_voice_hangup"
    assert session.phase == "ended"
    # Terminal-state guard: once ended, turns and controls are no-ops
    assert session.process_caller_turn(transcript="Another question").phase == "ended"
    assert session.handle_call_control("repeat").phase == "ended"


def test_officer_hold_gate_queue_position_and_live_call_risk_evaluator() -> None:
    """FinalYearProject hold_gate.py, transfer.py & risk.py parity."""
    from ssra_voice import (
        LobbyCallEntry,
        compute_transfer_queue_position,
        evaluate_live_call_risk,
        format_case_reference,
        should_drop_ai_frame_when_bridged,
    )

    assert should_drop_ai_frame_when_bridged(call_mode="bridged", frame_kind="output_audio") is True
    assert should_drop_ai_frame_when_bridged(call_mode="bridged", frame_kind="tts_text") is True
    assert should_drop_ai_frame_when_bridged(call_mode="bridged", frame_kind="caption") is False
    assert should_drop_ai_frame_when_bridged(call_mode="ai", frame_kind="output_audio") is False
    assert (
        should_drop_ai_frame_when_bridged(
            call_mode="bridged", frame_kind="output_audio", direction="upstream"
        )
        is False
    )

    assert format_case_reference("SSRA-20261025-001") == "SSRA-20261025-001"
    assert format_case_reference("abcd1234efgh") == "SSRA-ABCD1234"
    assert format_case_reference(None, fallback_call_id="call987654321") == "CALL-CALL9876"
    assert format_case_reference(None) == "CALL-UNKNOWN"

    c_norm_late = LobbyCallEntry(
        call_id="c3", status="transferring", priority="normal", waiting_since=200.0
    )
    c_norm_early = LobbyCallEntry(
        call_id="c2", status="transferring", priority="normal", waiting_since=100.0
    )
    c_urgent = LobbyCallEntry(
        call_id="c1", status="transferring", priority="urgent", waiting_since=300.0
    )
    c_claimed = LobbyCallEntry(
        call_id="c0",
        status="transferring",
        priority="urgent",
        waiting_since=50.0,
        claimed_by="staff_1",
    )
    all_calls = [c_norm_late, c_norm_early, c_urgent, c_claimed]
    assert compute_transfer_queue_position(c_urgent, all_calls) == 1
    assert compute_transfer_queue_position(c_norm_early, all_calls) == 2
    assert compute_transfer_queue_position(c_norm_late, all_calls) == 3

    # Live call risk evaluation: none -> watch -> at_risk
    none_risk = evaluate_live_call_risk(
        turns=[
            {
                "speaker": "caller",
                "text": "What is the PAYE filing deadline?",
                "mean_word_prob": 0.92,
            }
        ],
    )
    assert none_risk.level == "none"
    assert none_risk.should_offer_officer is False

    watch_risk = evaluate_live_call_risk(
        turns=[{"speaker": "caller", "text": "What is the PAYE filing deadline?"}],
        duration_seconds=400.0,
    )
    assert watch_risk.level == "watch"
    assert watch_risk.signals == ("long_call",)

    at_risk = evaluate_live_call_risk(
        turns=[
            {"speaker": "caller", "text": "Where do I file PAYE returns?", "mean_word_prob": 0.42},
            {"speaker": "caller", "text": "Where do I file PAYE return?", "mean_word_prob": 0.41},
            {"speaker": "caller", "kind": "review", "text": "useless!!"},
        ],
        clarifications_asked=2,
        abstentions_count=1,
        duration_seconds=420.0,
        caller_affect="distressed",
        risk_offer_already_made=False,
    )
    assert at_risk.level == "at_risk"
    assert "clarifications:2" in at_risk.signals
    assert "repeated_question" in at_risk.signals
    assert "distress" in at_risk.signals
    assert "low_word_confidence" in at_risk.signals
    assert "abstention" in at_risk.signals
    assert "long_call" in at_risk.signals
    assert at_risk.should_offer_officer is True


def test_low_bandwidth_voice_profile_mulaw_codec_and_call_resume_ticket() -> None:
    """FinalYearProject low_bandwidth.py parity: 2G/3G negotiation, G.711 mu-law transcoding & single-use resume ticket."""
    import struct

    import pytest
    from ssra_voice import (
        mint_call_resume_ticket,
        mulaw_8k_to_pcm16_16k,
        negotiate_low_bandwidth_voice_profile,
        pcm16_16k_to_mulaw_8k,
        verify_call_resume_ticket,
    )

    normal_prof = negotiate_low_bandwidth_voice_profile({"effective_type": "4g", "rtt_ms": 80})
    assert normal_prof.enabled is False
    assert normal_prof.codec == "pcm16_16k"

    edge_prof = negotiate_low_bandwidth_voice_profile({"effective_type": "2g", "rtt_ms": 720})
    assert edge_prof.enabled is True
    assert edge_prof.codec == "mulaw_8k"
    assert edge_prof.sample_rate == 8000
    assert edge_prof.caption_only is False
    assert edge_prof.bitrate_kbps == 64

    slow_2g_prof = negotiate_low_bandwidth_voice_profile(
        {"effective_type": "slow-2g", "rtt_ms": 1800, "audio_codec": "opus_12k"}
    )
    assert slow_2g_prof.enabled is True
    assert slow_2g_prof.codec == "opus_12k"
    assert slow_2g_prof.caption_only is True
    assert slow_2g_prof.bitrate_kbps == 0

    # G.711 mu-law 8 kHz <-> 16 kHz PCM16 transcoding (4x byte reduction)
    from ssra_core import SSRAError
    from ssra_voice import MAX_DECODED_PCM_BYTES

    with pytest.raises(SSRAError):
        pcm16_16k_to_mulaw_8k(b"\x00" * (MAX_DECODED_PCM_BYTES + 2))
    assert pcm16_16k_to_mulaw_8k(b"\x00\x01") == b""
    assert mulaw_8k_to_pcm16_16k(b"") == b""
    single_mulaw = pcm16_16k_to_mulaw_8k(struct.pack("<2h", 4000, -4000))
    assert len(single_mulaw) == 1
    assert len(mulaw_8k_to_pcm16_16k(single_mulaw)) == 4

    pcm_samples = [int(12000 * ((i % 16) - 8) / 8) for i in range(64)]
    pcm_bytes = struct.pack(f"<{len(pcm_samples)}h", *pcm_samples)
    mulaw_bytes = pcm16_16k_to_mulaw_8k(pcm_bytes)
    assert len(mulaw_bytes) == len(pcm_bytes) // 4
    restored_pcm = mulaw_8k_to_pcm16_16k(mulaw_bytes)
    assert len(restored_pcm) == len(pcm_bytes)

    # Single-use HMAC-SHA256 caller drop-resume ticket
    secret = "test-voice-carryover-secret-key-at-least-32-bytes"
    with pytest.raises(ValueError, match="_SAFE_ID_RE"):
        mint_call_resume_ticket("../bad", "conv_drop_0", signing_salt=secret)
    early_ticket = mint_call_resume_ticket(
        "call_drop_0",
        "conv_drop_0",
        user_id="usr_0",
        ttl_seconds=10,
        signing_salt=secret,
        now=900.0,
    )
    assert verify_call_resume_ticket(early_ticket, signing_salt=secret, now=905.0) is not None
    ticket = mint_call_resume_ticket(
        "call_drop_1",
        "conv_drop_1",
        user_id="usr_1",
        ttl_seconds=45,
        signing_salt=secret,
        now=1000.0,
    )
    assert "." in ticket
    assert verify_call_resume_ticket("", signing_salt=secret, now=1010.0) is None
    assert verify_call_resume_ticket("é.1234", signing_salt=secret, now=1010.0) is None
    assert verify_call_resume_ticket(f"{ticket}bad", signing_salt=secret, now=1010.0) is None
    assert verify_call_resume_ticket(ticket, signing_salt=secret, now=2000.0) is None
    assert (
        verify_call_resume_ticket(
            ticket, expected_call_id="wrong_call", signing_salt=secret, now=1010.0
        )
        is None
    )
    assert (
        verify_call_resume_ticket(
            ticket, expected_conversation_id="wrong_conv", signing_salt=secret, now=1010.0
        )
        is None
    )
    assert (
        verify_call_resume_ticket(
            ticket, expected_user_id="wrong_user", signing_salt=secret, now=1010.0
        )
        is None
    )
    claims = verify_call_resume_ticket(
        ticket,
        expected_call_id="call_drop_1",
        expected_user_id="usr_1",
        signing_salt=secret,
        now=1010.0,
    )
    assert claims is not None and claims["cid"] == "call_drop_1"
    # Replay of the same ticket is rejected (single-use nonce consumed)
    assert (
        verify_call_resume_ticket(
            ticket,
            expected_call_id="call_drop_1",
            expected_user_id="usr_1",
            signing_salt=secret,
            now=1011.0,
        )
        is None
    )


def test_speech_normalization_asr_entity_mishears_clarify_gate_and_language_policy() -> None:
    """FinalYearProject speech_normalization.py, clarify.py & language.py parity."""
    from ssra_voice import (
        CallLanguagePolicy,
        LanguageVote,
        assess_spoken_clarification,
        clean_text_for_speech,
        detect_explicit_language_request,
        detect_ssra_entity_mishear,
        repair_ssra_asr_entities,
    )

    raw_md = (
        "### Filing Rules\n"
        "- Under **Sec. 18** and __Art. 12__, your [e-Tax Portal](https://etax.nra.gov.ss/) "
        "account `••••1234` (<TIN_REDACTED>, [REDACTED_PHONE]) is due [1, 2].\n"
        "```sql\nSELECT 1;\n```"
    )
    cleaned = clean_text_for_speech(raw_md)
    assert "[1, 2]" not in cleaned
    assert "Section 18" in cleaned
    assert "Article 12" in cleaned
    assert "T I N ending in 1 2 3 4" in cleaned
    assert "redacted T I N" in cleaned
    assert "redacted phone number" in cleaned
    assert "SELECT 1" not in cleaned
    # Spoofed lookalike URL must fall through to 'web link' and never be spoken as official e-Tax
    spoof_cleaned = clean_text_for_speech(
        "Visit https://etax.nra.gov.ss.evil.example/login or https://etax.nra.gov.ss/pay."
    )
    assert "web link" in spoof_cleaned
    assert "e-tax dot n r a dot gov dot s s" in spoof_cleaned
    assert "evil.example" not in spoof_cleaned

    # ASR phonetic mishear detection & repair
    assert detect_ssra_entity_mishear("ttiimu") == "TIN"
    assert detect_ssra_entity_mishear("era", "from") == "SSRA"
    assert detect_ssra_entity_mishear("payment") is None
    assert repair_ssra_asr_entities("") == ""
    assert (
        repair_ssra_asr_entities("How do I get my ttiimu from era on etaksi?")
        == "How do I get my TIN from SSRA on e-Tax?"
    )

    # Spoken ClarifyGate assessment
    term_dec = assess_spoken_clarification("Where is my tiisiisii certificate?")
    assert term_dec.action == "ask_term"
    assert term_dec.candidate == "TCC"
    assert term_dec.prompt == "Excuse me, did you mean TCC?"

    none_no_words = assess_spoken_clarification("What is the PAYE filing deadline?")
    assert none_no_words.action == "none"

    none_high_conf = assess_spoken_clarification(
        "What is the PAYE deadline?",
        words=[{"word": "What", "prob": 0.95}, {"word": "deadline", "prob": 0.91}],
    )
    assert none_high_conf.action == "none"

    repeat_dec = assess_spoken_clarification(
        "What is the mumbledword?",
        words=[
            {"word": "the", "prob": 0.40},
            {"word": "123", "prob": 0.40},
            {"word": "mumbledword", "prob": 0.42},
        ],
        threshold=0.65,
    )
    assert repeat_dec.action == "ask_repeat"
    assert repeat_dec.target_word == "mumbledword"

    mild_low_dec = assess_spoken_clarification(
        "Tell me about customs duties",
        words=[
            {"word": "Tell", "prob": 0.95},
            {"word": "customs", "prob": 0.62},
            {"word": "duties", "prob": 0.95},
        ],
        threshold=0.65,
    )
    assert mild_low_dec.action == "none"

    # Hysteresis CallLanguagePolicy & negation-safe explicit language request detection
    assert detect_explicit_language_request("") is None
    assert detect_explicit_language_request("Do you have the form in English?") is None
    assert detect_explicit_language_request("Please do not speak in English") is None
    assert detect_explicit_language_request("Not in English — please speak in Arabic") == "ar"
    assert detect_explicit_language_request("Can we speak Juba Arabic?") == "pga"

    policy = CallLanguagePolicy(active="en", supported_languages=("en", "ar", "pga"))
    assert policy.set_override("fr").reason == "unsupported_language"

    # Too-short utterance does not lock
    assert (
        policy.observe(LanguageVote(probs={"ar": 0.95}, top="ar", speech_s=0.6)).reason
        == "too_short"
    )
    # Unsupported language vote ignored
    assert (
        policy.observe(LanguageVote(probs={"fr": 0.95}, top="fr", speech_s=2.0)).reason
        == "unsupported_language"
    )
    # Weak first vote leaves call unlocked
    assert (
        policy.observe(LanguageVote(probs={"en": 0.55}, top="en", speech_s=2.0)).reason
        == "weak_first_vote"
    )
    # Confident first content locks English
    lock_dec = policy.observe(LanguageVote(probs={"en": 0.82}, top="en", speech_s=2.2))
    assert lock_dec.action == "lock"
    assert policy.locked is True
    # Same language clears pending
    assert (
        policy.observe(LanguageVote(probs={"en": 0.80}, top="en", speech_s=2.0)).reason
        == "same_language"
    )
    # Hysteresis: two moderate votes (0.68, 0.72) in window of 3 switch to 'ar'
    h1 = policy.observe(LanguageVote(probs={"ar": 0.68}, top="ar", speech_s=2.0))
    assert h1.reason == "accumulating_hysteresis"
    h2 = policy.observe(LanguageVote(probs={"ar": 0.72}, top="ar", speech_s=2.1))
    assert h2.action == "switch"
    assert h2.target == "ar"
    assert h2.reason == "hysteresis"

    # Code-switched tax loanword guard while locked in 'ar'
    cs_guard = policy.observe(
        LanguageVote(
            probs={"en": 0.92},
            top="en",
            speech_s=2.0,
            text="كيف أسجل في TIN و PAYE؟",
        )
    )
    assert cs_guard.action == "none"
    assert cs_guard.reason == "code_switched_loanword_guard"
    assert policy.active == "ar"

    # Single high-confidence vote (>= 0.90) switches immediately back to 'en'
    high_sw = policy.observe(LanguageVote(probs={"en": 0.94}, top="en", speech_s=2.0))
    assert high_sw.action == "switch"
    assert high_sw.reason == "high_confidence"

    # UI override locks 'pga', ignoring acoustic votes, but explicit spoken request still overrides
    ov_dec = policy.set_override("pga")
    assert ov_dec.source == "override"
    assert (
        policy.observe(LanguageVote(probs={"en": 0.99}, top="en", speech_s=2.5)).reason
        == "override_locked"
    )
    exp_dec = policy.observe(
        LanguageVote(
            probs={"en": 0.50},
            top="en",
            speech_s=0.8,
            text="Please switch to English",
        )
    )
    assert exp_dec.action == "switch"
    assert exp_dec.target == "en"
    assert exp_dec.source == "explicit"


def test_multilingual_contact_url_pronunciation_and_receptionist_structuring() -> None:
    """Verify natural pronunciation of contact info, .gov.ss links, USSD codes, and receptionist structuring across locales."""
    from ssra_voice import VoiceCallSession, clean_text_for_speech

    en_contact = clean_text_for_speech(
        "1. Dial *311# or call +211 912 345 678, 0922 111 222, or 0800 123 456.\n"
        "2. Email support.etax_1+help@nra.gov.ss or visit https://ecustoms.nra.gov.ss/ and www.eservices.gov.ss.\n"
        "3. Check TIN ******1234 or TIN 100-200-1234 at P.O. Box 456.",
        locale=LocaleCode.EN,
    )
    assert "Step 1: Dial star 3 1 1 hash" in en_contact
    assert "plus 2 1 1, 9 1 2, 3 4 5, 6 7 8" in en_contact
    assert "0 9 2 2, 1 1 1, 2 2 2" in en_contact
    assert "0 800, 1 2 3, 4 5 6" in en_contact
    assert (
        "Step 2: Email support dot e-tax underscore 1 plus help at n r a dot gov dot s s"
        in en_contact
    )
    assert "e-customs dot n r a dot gov dot s s" in en_contact
    assert "e-services dot gov dot s s" in en_contact
    assert "Step 3: Check T I N ending in 1 2 3 4" in en_contact
    assert "T I N 1 0 0, 2 0 0, 1 2 3 4" in en_contact
    assert "P O Box 4 5 6" in en_contact

    # Arabic ('ar') and Juba Arabic ('pga') localization + RFC 3986 @ userinfo spoof rejection
    ar_contact = clean_text_for_speech(
        "1. اطلب *311# أو راسل info@etax.nra.gov.ss أو اتصل على +211 912 345 678 لحساب ******9876. "
        "لا تضغط على https://etax.nra.gov.ss@evil.example/phish.",
        locale=LocaleCode.AR,
    )
    assert "الخطوة 1: اطلب نجمة 3 1 1 شباك" in ar_contact
    assert "info آت إي تاكس دوت إن آر إيه دوت جوف دوت إس إس" in ar_contact
    assert "زائد 2 1 1, 9 1 2, 3 4 5, 6 7 8" in ar_contact
    assert "الرقم الضريبي المنتهي بـ 9 8 7 6" in ar_contact
    assert "رابط إلكتروني" in ar_contact
    assert "evil.example" not in ar_contact

    pga_contact = clean_text_for_speech("1. Amlu *311# fi etax.nra.gov.ss.", locale=LocaleCode.PGA)
    assert "Khatwa 1: Amlu star 3 1 1 shibak fi e-tax dot n r a dot gov dot s s." in pga_contact

    # Call Receptionist prepare_spoken_answer: 3-sentence cap, more_detail overflow, and officer offer priority
    session = VoiceCallSession(
        session_id="call_struct_01",
        locale=LocaleCode.EN,
        recording_offered=False,
        wer_evidence=_synthetic_wer(LocaleCode.EN, 0.05),
    )
    session.start_call()
    session.mark_disclosure_finished()
    long_proc = (
        "1. Open https://etax.nra.gov.ss/.\n"
        "2. Enter TIN ******1234.\n"
        "3. Upload your TCC form.\n"
        "4. Download the e-Receipt.\n\n"
        "You might also want to know: BPT rate is 30%."
    )
    spoken_turn = session.prepare_spoken_answer(long_proc)
    assert "Step 1: Open e-tax dot n r a dot gov dot s s." in spoken_turn
    assert "Step 2: Enter T I N ending in 1 2 3 4." in spoken_turn
    assert "Step 3: Upload your TCC form." in spoken_turn
    assert "Step 4" not in spoken_turn
    assert "You might also want to know" not in spoken_turn
    assert "Would you like me to read the remaining details?" in spoken_turn
    assert session.pending_offer == "more"
    assert "4. Download the e-Receipt." in session.more_detail_text

    # Officer offer supersedes more_detail so only one yes/no question is asked per turn
    spoken_officer = session.prepare_spoken_answer(long_proc, offer_officer=True, at_risk=True)
    assert "Would you like me to connect you with an SSRA officer?" in spoken_officer
    assert "remaining details" not in spoken_officer
    assert session.pending_offer == "officer"

    # Single-sentence answer with no overflow and no officer offer
    short_turn = session.prepare_spoken_answer("Your return is filed on https://etax.nra.gov.ss/.")
    assert short_turn == "Your return is filed on e-tax dot n r a dot gov dot s s."

    # Voice Speaker & Regional Dialect profiles across all 8 South Sudan languages
    from ssra_voice import (
        TTS_SPEAKER_PROFILES,
        VOICE_SAMPLES_BY_LOCALE,
        build_voice_catalogue_payload,
        resolve_tts_speaker_profile,
        synthesize_tts_speech_envelope,
    )

    assert len(VOICE_SAMPLES_BY_LOCALE) == 8
    assert resolve_tts_speaker_profile("xx", None) is None
    en_prof = resolve_tts_speaker_profile("en", "ssra_eng_0002")
    assert en_prof is not None and en_prof.name == "Lado"
    assert en_prof.dialect_code == "en-SS-EAC"
    din_prof = resolve_tts_speaker_profile("din", "ssra_din_0003")
    assert din_prof is not None and din_prof.name == "Nyanut"
    assert din_prof.dialect_code == "din-Agar"

    cat_payload = build_voice_catalogue_payload()
    assert set(cat_payload["voices"].keys()) == {
        "en",
        "ar",
        "pga",
        "din",
        "nus",
        "bfa",
        "zne",
        "shk",
    }
    assert len(cat_payload["voices"]["en"]) == 3
    assert cat_payload["voices"]["en"][0]["oq008_approved"] is False
    assert len(TTS_SPEAKER_PROFILES) == 18

    synth_env = synthesize_tts_speech_envelope(
        text="PAYE is due by the 15th.",
        locale=LocaleCode.EN,
        voice="ssra_eng_0003",
        recommended_tone="reassuring_step_by_step",
    )
    assert synth_env["speaker_name"] == "Akol"
    assert synth_env["dialect_code"] == "en-SS-Civic"

    selected_prof = session.set_speaker_voice("ssra_eng_0002")
    assert selected_prof.name == "Lado"
    state_frame = session.build_call_state_frame()
    assert state_frame["voice_id"] == "ssra_eng_0002"
    assert state_frame["speaker_name"] == "Lado"
    assert state_frame["dialect_code"] == "en-SS-EAC"

    # Acoustic + lexical vote fusion (`fuse_language_vote`), `is_native_language_word`, and 8-locale `text_confirmed`
    from ssra_voice import (
        CallLanguagePolicy,
        LanguageVote,
        assess_spoken_clarification,
        detect_explicit_language_request,
        fuse_language_vote,
        is_native_language_word,
        lexical_language_hits,
    )

    assert is_native_language_word("wëu", "din") is True
    assert is_native_language_word("weu", "din") is True
    assert is_native_language_word("weu", "xx") is False
    hits = lexical_language_hits("Ajul weu tene bengic paguot")
    assert hits["din"] >= 4

    # Native vernacular words are not flagged by ClarifyGate as low-confidence English mishears
    clarify_native = assess_spoken_clarification(
        "Ajul weu",
        words=[{"word": "weu", "probability": 0.42}],
        locale=LocaleCode.DIN,
    )
    assert clarify_native.action == "none"

    # fuse_language_vote overrides uncertain acoustic vote (< 0.80) when >= 2 lexical hits agree
    raw_vote = LanguageVote(
        probs={"en": 0.55, "din": 0.30, "ar": 0.15},
        top="en",
        speech_s=2.4,
        text="Namba de ajul weu tene bengic",
    )
    fused = fuse_language_vote(raw_vote, text_confidence=0.80)
    assert fused.top == "din"
    assert fused.confidence == 0.80
    # Already confident vote (>= 0.80) is untouched
    conf_vote = LanguageVote(
        probs={"en": 0.90, "din": 0.10}, top="en", speech_s=2.0, text="ajul weu"
    )
    assert fuse_language_vote(conf_vote).top == "en"

    # 8-language explicit switch & text_confirmed fast switch in CallLanguagePolicy
    assert detect_explicit_language_request("Jam në Thuɔŋjäŋ") == "din"
    assert detect_explicit_language_request("Ruacni Thok Naath") == "nus"
    pol8 = CallLanguagePolicy(active="en")
    pol8.observe(LanguageVote(probs={"en": 0.85}, top="en", speech_s=2.0, text="Hello how are you"))
    assert pol8.locked is True
    txt_conf_dec = pol8.observe(
        LanguageVote(
            probs={"din": 0.75, "en": 0.25},
            top="din",
            speech_s=2.2,
            text="Ajul weu tene bengic paguot",
        )
    )
    assert txt_conf_dec.action == "switch"
    assert txt_conf_dec.target == "din"
    assert txt_conf_dec.reason == "text_confirmed"

    # Auto-fusion inside CallLanguagePolicy.observe on unlocked uncertain acoustic vote (< 0.80)
    pol_auto_fuse = CallLanguagePolicy(active="en")
    auto_fused_dec = pol_auto_fuse.observe(raw_vote)
    assert auto_fused_dec.action == "switch"
    assert auto_fused_dec.target == "din"
    assert auto_fused_dec.reason == "first_content"
