# ADR-027: Multi-Turn Voice Continuity, Post-TTS Acoustic Echo Guard, and Backchannel Immunity

- **Status:** Accepted as a repository safety baseline; not production authorization
- **Date:** 2026-10-24
- **Deciders:** SSRA Assist engineering maintainers
- **Reversal Cost:** Medium
- **Related:** [ADR-024](./0024-voice-identity-step-up-and-carryover-fail-closed.md), [ADR-025](./0025-voice-launch-evidence-and-truthful-call-records.md), [ADR-026](./0026-voice-caller-output-disclosure-and-figure-safe-text.md), [Call Receptionist Audit](../product/call-receptionist-audit-2026-10.md)

## Context

In high-stakes tax assistance, a voice session fails after the first spoken reply when three turn-taking hazards are left unhandled:

1. **Acoustic echo self-triggering ("agent talks to itself"):** When `speechSynthesis` or a TTS stream finishes, room reverberation and speaker-to-microphone coupling feed the tail of the assistant's own sentence into the recognizer. Without pausing recognition during TTS, waiting for an acoustic tail cooldown (`450 ms`), and filtering transcripts that match the assistant's just-spoken reply, the assistant transcribes its own output or halts mid-conversation.
2. **One-shot browser recognition & missing turn-continuation loop:** In `apps/web/server.js`, `SpeechRecognition` ran once per click, placed the transcript into the text box without sending it, and never re-armed after `speechSynthesis` finished speaking the reply.
3. **Disconnected per-turn voice state in `ssra_voice`:** `build_call_opening_prompts`, `resolve_recording_consent`, and `route_voice_turn` were standalone functions. There was no stateful session object tracking the transition from opening disclosure to opt-in consent to active multi-turn conversation, resetting `consecutive_low_confidence_turns` after a recovered clarification turn, ignoring listener backchannels (`"mm-hm"`, `"okay"`, `"نعم"`) during assistant speech, or trimming unspoken sentences from conversation context after a barge-in.

## Options Considered

1. **Keep `SpeechRecognition.continuous = true` open while `speechSynthesis` plays.** Rejected: without hardware/WebRTC acoustic echo cancellation tied to `speechSynthesis`, the browser microphone captures the assistant's own voice, creating an echo feedback loop, and mobile browsers still terminate `continuous` sessions after short pauses.
2. **Require the user to manually click the microphone button and the Send button on every turn.** Rejected for hands-free voice mode: it breaks multi-turn conversational continuity after the first spoken reply.
3. **Stateful echo-gated turn-taking with a 450 ms post-TTS cooldown, lexical echo rejection, backchannel immunity, and bounded silent retries (chosen).**

## Decision

1. **Three-layer echo suppression (`POST_TTS_ECHO_COOLDOWN_MS = 450`).**
   - In the browser (`apps/web/server.js`), active `SpeechRecognition` is stopped before `speechSynthesis.speak()` begins, a 10-second pause/resume watchdog prevents Chromium's 15-second cutoff on longer replies, and recognition re-arms `450 ms` after `utterance.onend`.
   - In both `ssra_voice` (`is_likely_tts_echo`) and `@ssra/chat-ui` (`isLikelyAssistantEcho`), transcripts arriving within `450 ms` of TTS completion that are substrings or `>= 75%` token overlaps of the assistant's last spoken reply (or `>= 4`-word, `>= 85%` overlaps at any time) are discarded as speaker echo rather than submitted as caller turns.
2. **Backchannel immunity (`is_backchannel_utterance` / `isBackchannelText`).**
   - Short listener acknowledgements (`<= 2` tokens such as `"mm-hm"`, `"uh-huh"`, `"okay"`, `"نعم"`, `"تمام"`) spoken while the assistant is talking do not trigger barge-in or cancel the active reply.
3. **Stateful multi-turn `VoiceCallSession` (`ssra_voice`).**
   - Manages the lifecycle `opening_disclosure` -> `recording_consent` -> `active_ai` -> `transferred` / `ended`, keeping `disclosure_playing=True` until `mark_disclosure_finished()` is called so spoken input cannot interrupt or skip the opening AI disclosure (while keypad `0` still transfers to an officer).
   - Declining recording (`dtmf_digit="2"` or `None`) keeps `recording_consent_granted=False` while allowing the caller to continue the AI conversation (`phase="active_ai"`). The recording-consent basis remains jurisdiction-specific and pending OQ-009 legal review. EU AI Act Article 50(1) and the Commission’s Article 50 transparency guidance apply only to the separate AI-interaction disclosure.
   - Tracks `consecutive_low_confidence_turns` across turns: a single low-confidence turn requests spoken clarification (`CLARIFY_INTENT_SPOKEN`), a clear follow-up turn resets the counter to `0` and continues `STREAM_ASR`, and two consecutive low-confidence turns escalate to `WARM_TRANSFER_TO_OFFICER`.
   - When barge-in interrupts a multi-sentence reply (`record_assistant_reply(..., interrupted_at_sentence=k)`), only the spoken prefix (`sentences[:k]`) is stored as heard context; unspoken sentences are stashed separately so later turns never assume the caller heard them. If a pending yes/no offer was active when the caller interrupted (`offer_interrupted=True`), a yes/no reply re-asks the unheard offer question (`reask_unheard_offer`) instead of transferring immediately.
   - Integrates the `FinalYearProject` backend receptionist flows (`brain.py`, `state.py`, `transfer.py`, `risk.py`, `low_bandwidth.py`, `hold_gate.py`, `review.py`): in-call controls (`handle_call_control` for `repeat`, `slower`, `normal_speed`, `more_detail`, `accept_offer`, `decline_offer`, `request_callback`), spoken officer zero-out (`is_spoken_officer_request`), spoken review classification (`classify_spoken_call_review`), procedure-aware sentence splitting (`split_receptionist_spoken_sentences`), officer output hold gate (`should_drop_ai_frame_when_bridged`), transfer queue ranking (`compute_transfer_queue_position`, `format_case_reference`), 6-signal live call risk evaluation (`evaluate_live_call_risk`), and 2G/3G G.711 mu-law transcoding with single-use HMAC-SHA256 drop-resume tickets (`negotiate_low_bandwidth_voice_profile`, `pcm16_16k_to_mulaw_8k`, `mulaw_8k_to_pcm16_16k`, `mint_call_resume_ticket`, `verify_call_resume_ticket`).
   - Production fail-closed governance (`APPROVED_VOICE_WER_EVIDENCE = {}` under `OQ-008`) remains unchanged.
4. **Hands-free multi-turn loop & bounded retry in `apps/web/server.js`.**
   - The voice modal (`#call-modal-backdrop`) provides `Start voice conversation` (`#call-listen-btn`) and `Interrupt & speak` (`#call-interrupt-btn`) controls with a live polite status region (`#call-voice-status`).
   - In continuous voice mode, a final non-echo transcript automatically invokes `sendTurn(transcript, { fromVoiceLoop: true })`, speaks the reply, waits `450 ms`, and re-arms recognition for the next turn.
   - Consecutive silent/no-speech ends are capped at `MAX_CONSECUTIVE_SPEECH_RETRIES = 3` before pausing gracefully.

## Consequences

- Callers in the browser voice flow can hold a continuous multi-turn spoken conversation without the assistant transcribing its own voice or getting stuck after the first reply.
- Barge-in via `Interrupt & speak` or the mic button immediately cancels both `speechSynthesis` and any in-flight `/api/turns` `AbortController`.
- Production telephony remains gated on `OQ-008` WER evidence and `OQ-007` SIP/trunk provisioning.

## Reversal Cost

Medium. Removing the post-TTS cooldown or lexical echo check reintroduces self-triggering echo loops on speakerphone and desktop browsers; removing `VoiceCallSession` loses multi-turn clarification recovery and barge-in context trimming.

## Verification

Covered by `services/voice/tests/test_voice.py` (`test_voice_multiturn_call_session_echo_guard_and_recovery`), `packages/chat-ui/tests/chat-ui.test.ts`, and `tests/browser/public-chat-a11y.spec.ts` (`continuous voice conversation auto-advances across turns and filters speaker echo`).
