# Phase R2-K Report: What the Caller Hears and Receives

**Date:** 2026-10-24

**Status:** Source remediation implemented. Gate R2 has not been evaluated or approved.
**Scope:** AUD-041, AUD-042, AUD-044, and AUD-045 in `libs/ssra_core`, `services/voice`, `services/channel-gateway`, and `packages/chat-ui`. AUD-046 and AUD-047 were recorded but not changed.

## Evidence boundary

No live telephony path exists, and the SSRA GPU stack was not running. All evidence comes from unit tests, the evaluation suites, and a probe that ran the same inputs against the R2-J code and the R2-K code. The disclosure and consent wording is interim and unapproved.

## Before and after

| Behaviour | R2-J | R2-K |
|---|---|---|
| SMS adapter, "Total due: 1,234,567 SSP." across the 160-character limit | Sent "…Total due: 1,2" | Drops the sentence: "…25,000 SSP. ..." |
| Voice SMS follow-up over 160 characters | "SSRA OFFICIAL: …The withh": citation and portal reference cut off | "SSRA Assist (automated): …" with whole sentences, citation, and portal reference |
| IVR answer marked as an estimate | Spoken without framing, up to 1,000 characters, labelled "ssml_or_text" | "Estimate only." plus at most three sentences, `content_type: text/plain` |
| Guard, "valid for twelve (3) months" with 3 expected (strict) | Passed | Fails (12 is not allowed) |
| Guard, `٤٥٠٬٠٠٠` with 450,000 expected | Failed | Passes |
| Call opening | No disclosure available | AI disclosure (not interruptible by speech), then opt-in recording request |
| 120 ms noise while the assistant speaks | Treated as a barge-in | Ignored |
| Barge-in during a turn | No signal to cancel the reply | `cancel_active_reply=True`; directive stops playback and cancels generation |
| Whisper segment marked as silence, utterance confidence 0.97 | Would stream to the runtime | Keypad menu, "no speech detected" |
| Reduced motion while the assistant speaks | Orb mode `idle` | Orb mode `speaking`, level frozen |

## Implemented controls

- `ssra_core.channel_text`: `split_sentences` (moved from `ssra_voice`; also splits at `؟`), `sms_encoding` and `count_sms_segments` (moved from the gateway; adds `Æ æ ß É` to GSM-7 and counts UCS-2 in UTF-16 code units), `fit_text`, and `compose_spoken_reply`. The gateway and `ssra_voice` import them, so only one implementation exists.
- The SMS and IVR adapters use the shared fitting; the IVR output is plain text with an `omitted_sentences` count.
- `build_voice_spoken_turn_and_sms_followup` returns `sms_encoding`, `sms_segments`, and `sms_shortened`. A 160-character Arabic follow-up is reported as up to three UCS-2 segments.
- The figure guard reads digits in any script and spelled-out English numbers. A lone "one" counts only before a quantity noun ("one month"), not in "one of the forms".
- `build_call_opening_prompts`, `VoicePrompt`, and `resolve_recording_consent`. Both prompts are fixed prompts, so their audio may be cached (ADR-025).
- `BargeInDirective`, `VoiceStreamSession.trigger_barge_in(…, speech_ms, prompt_interruptible)`, and `VoiceSessionDecision.cancel_active_reply`.
- `WhisperSegmentSignals`, `assess_whisper_segment`, and `route_voice_turn(…, whisper_signals=…)` with `asr_rejected_reason`.
- `buildCallReceptionistScreen` adds `speakingWith`, `recordingIndicator` (from a required `recording` input), and a `not_started` tone; `computeCallOrbFrame` keeps the mode under reduced motion.

See [ADR-026](../adr/0026-voice-caller-output-disclosure-and-figure-safe-text.md).

## Validation

| Check | Result |
|---|---|
| Probe against the R2-J code | Each defect in the table reproduced |
| Python suites in `libs`, `services`, `mcp-servers`, and `evals/suites`, with the worktree packages first on the path | 112 passed |
| `packages/chat-ui`: Biome, `tsc --noEmit`, Vitest | Pass (3 tests) |
| Ruff, Ruff format, strict basedpyright on every changed Python file | Pass, 0 errors |

## Findings recorded, not changed

- **AUD-046.** The official CMS snapshot says TCCs are "valid for twelve (3) months". An engineer must not choose the value; SSRA should confirm it and republish (OQ-019). The R2-K guard blocks speaking the sentence.
- **AUD-047.** `ssra-voice` does not declare `ssra-security`. Fixing it changes `uv.lock`, so it belongs in its own change.

## Threat-model delta

- **Removed:** split figures and dropped citations in SMS and IVR text, model text treated as SSML, a silent AI identity on calls, recording without an explicit yes, stale replies continuing after a barge-in, and hallucinated transcripts reaching the runtime.
- **Residual:** number words in other languages, the USSD, WhatsApp, web, and console adapters' length cuts, approval of the wording, and the media pipeline that must act on these contracts.
