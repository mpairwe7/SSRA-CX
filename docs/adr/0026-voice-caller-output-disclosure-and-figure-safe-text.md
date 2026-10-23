# ADR-026: Voice Caller Output, Disclosure, and Figure-Safe Channel Text

- **Status:** Accepted as a repository safety baseline; not production authorization
- **Date:** 2026-10-24
- **Deciders:** SSRA Assist engineering maintainers
- **Reversal Cost:** Medium
- **Related:** [ADR-023](./0023-public-chat-render-boundary-and-truthful-failure-states.md), [ADR-024](./0024-voice-identity-step-up-and-carryover-fail-closed.md), [ADR-025](./0025-voice-launch-evidence-and-truthful-call-records.md), [AUD-041 to AUD-045](../audit/findings.md#call-receptionist-audit-2026-10-24), [R2-K report](../audit/phase-R2-K-voice-caller-output-report.md)

## Context

Each channel adapter shortened answers with a slice such as `text[:160]`. The SMS adapter therefore sent "Total due: 1,234,567 SSP" as "Total due: 1,2". The voice SMS follow-up lost its citation, and the IVR adapter spoke any number of sentences without estimate framing. Two copies of the GSM-7 table and sentence splitting were drifting apart, and one of them was wrong.

The spoken-figure guard read only ASCII-style digit runs. It accepted "valid for twelve (3) months", a sentence that is in the official snapshot, and rejected a correct Arabic-Indic figure.

No call started with an AI disclosure, barge-in only set a flag, and a Whisper transcript of silence would have been answered.

## Decision

1. **One fitting rule for channel text.** `ssra_core.channel_text` owns sentence splitting, SMS segment counting, and `fit_text`. Text is shortened by dropping whole sentences from the end. Only when no sentence fits are whole words dropped, never ending on a number, and shortened text ends with "...". Adapters no longer slice strings.
2. **Voice output.** The IVR adapter and the voice follow-up use `compose_spoken_reply`: at most three whole sentences, with "Estimate only." added when the spoken sentences do not already say so. IVR output is declared `text/plain`; SSML may only come from templates, never from answer text.
3. **SMS follow-up.** It is labelled "SSRA Assist (automated):", always keeps the citation and portal reference, and keeps the existing 160-character budget. It reports its real encoding and segment count, so the cost of UCS-2 messages is visible. A per-language segment budget is for SSRA's channel owners (OQ-007).
4. **Figures in any form.** The spoken-figure guard maps every Unicode digit script to ASCII and reads spelled-out English numbers. Number words in other languages are not yet read; this is a recorded residual.
5. **Call opening.** Every call starts with an AI disclosure that speech cannot interrupt (keypad 0 still works). An opt-in recording request follows when recording is offered: keypad 1 allows recording, and anything else means no recording. Wording is interim English until SSRA approves it (OQ-009 item 2), and the prompt records the language actually spoken.
6. **Barge-in.** An interruption always stops playback, cancels generation, and drops queued audio together. Speech shorter than the VAD minimum and speech over a non-interruptible prompt are ignored.
7. **Whisper output.** A segment the decoder marks as silence or as unreliable (Whisper's default thresholds) never reaches the runtime; the caller gets the keypad menu.

## Consequences

- Shortened messages may carry less detail but never a broken figure. Some answers that spell out numbers will now fail the strict voice guard and fall back, which is the intended direction.
- Arabic follow-ups can use up to three UCS-2 segments under the 160-character budget. That cost is now reported rather than hidden.
- A future media pipeline must act on `BargeInDirective`, `cancel_active_reply`, and `asr_rejected_reason`; these are contracts, not behaviour, until telephony exists.

## Reversal Cost

Medium. Returning to string slicing would again send split figures and drop citations. Removing the disclosure or the opt-in would mislead callers about who they are talking to and whether they are being recorded.

## Verification

`libs/ssra_core/tests/test_channel_text.py`, `services/voice/tests/test_voice.py`, `services/channel-gateway/tests/test_channel_gateway.py`, and `packages/chat-ui/tests/chat-ui.test.ts` cover each decision. A probe against the R2-J code reproduced each defect before the fix.
