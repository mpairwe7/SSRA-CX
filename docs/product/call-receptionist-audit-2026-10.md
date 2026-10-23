# Call Receptionist Audit — October 2026

**Review date:** 2026-10-24 (Africa/Juba)
**Commit:** `70a6d1a`
**Scope:** `services/voice` (`ssra_voice`), `packages/chat-ui/src/call-receptionist.ts`, the `VoiceIvrChannelAdapter`, the web voice-input dialog, the staff "Calls" preview, and the voice services in the GPU Compose profile.

## What exists

The master prompt specifies Voice/IVR as a Phase 4 channel. It requires a SIP trunk into LiveKit SIP or Asterisk/FreeSWITCH, streaming ASR → runtime → TTS, barge-in, a DTMF fallback, a language menu, recording consent, and warm transfer with an AI summary. A language may launch on voice only after its word-error rate on SSRA test sets meets the gate.

| Component | State at `70a6d1a` |
|---|---|
| Telephony (SIP, RTP, voice WebSocket) | **Not present.** No trunk, media server, or voice endpoint is deployed |
| `ssra_voice` | A library of routing, step-up, brief, lobby, caching, and speech-formatting helpers. `python -m ssra_voice` prints a status object and exits. It is called only by unit tests, evaluation suites, and benchmark tools |
| `call-receptionist.ts` | View-model helpers (consent gate, language chip, orb animation, caption pinning). Not imported by the served pages |
| `VoiceIvrChannelAdapter` | Joins answer segments and cuts at 1,000 characters |
| Web voice-input dialog | Browser speech recognition for `en` and `ar`, with the R2-D accessibility fixes |
| Staff "Calls" route | A non-operational preview (ADR-018) |
| GPU profile | Runs an Orpheus TTS container that no SSRA code calls |

## Gaps found

| ID | Severity | Gap | Phase |
|---|---|---|---|
| AUD-034 | S1 (latent) | DTMF step-up authorized any well-formed TIN and OTP, with no OTP check and no attempt limit | R2-I (fixed) |
| AUD-035 | S1 (latent) | Carryover tokens were signed with a public constant key and never expired | R2-I (fixed) |
| AUD-036 | S2 | Call lobby allowed double claims and revived ended calls, accepted unknown events, and invented wait times | R2-I (fixed) |
| AUD-037 | S2 | WER gate trusts a per-call number; benchmarks report STT/TTS without processing audio | R2-J (fixed) |
| AUD-038 | S2 | Officer brief misattributes its producer, adds unsupported claims, and could leak part of a TIN; transfer summary gives generic reasons | R2-J (fixed) |
| AUD-039 | S2 | Voice retention periods invented while OQ-009 is open | R2-J (fixed) |
| AUD-040 | S3 | TTS phrase cache keeps audio of any text | R2-J (fixed) |
| AUD-041 | S2 | SMS and IVR output can cut figures; "SSRA OFFICIAL" label; spelled-out numbers pass the figure guard | R2-K |
| AUD-042 | S2 | No spoken AI disclosure at call start; barge-in not implemented | R2-K |
| AUD-043 | S2 | Core API, Sunflower vLLM, and Orpheus TTS published on all interfaces; Orpheus not digest-pinned | Decision needed (R3) |

Details and evidence are in [the findings register](../audit/findings.md#call-receptionist-audit-2026-10-24).

## Phased remediation

1. **R2-I: Identity and integrity (implemented).** DTMF step-up requires an approved OTP verifier and fails closed without one. Carryover tokens need a configured key and expire. The call lobby enforces first-claim-wins and keeps tombstones for ended calls.
2. **R2-J: Truthful gates and records (implemented).** A governed per-language WER record with no approved languages until evidence exists. Benchmarks label speech scenarios as simulated. Officer briefs and transfer summaries state only what happened. Retention is pending OQ-009. The TTS cache covers fixed prompts only.
3. **R2-K: What the caller hears and receives.** A spoken AI disclosure and a route to a person at call start (interim wording pending OQ-009). Barge-in cancels both playback and generation. SMS and IVR output never split a figure, and respect GSM-7 and UCS-2 segment limits. The spoken-figure guard also detects spelled-out numbers.
4. **Platform decision (R3).** Bind the Core API and model servers to loopback, pin or remove Orpheus, and route model calls through `agentgateway`.

Live telephony needs separate decisions: carrier and SIP provider (OQ-007), identity and OTP provider (OQ-005), contact-centre hours and queues (OQ-010), retention and disclosure wording (OQ-009), and measured WER per language (OQ-008).

## Standards and research checked on 2026-10-24

These sources are mostly practitioner and vendor guidance, not formal standards, and are used as design targets only.

- **Turn-taking and barge-in.** A full round trip under about 700 ms is a common target. A barge-in should stop TTS and cancel generation together, because cancelling only one leaves stale audio or stale work ([FutureAGI, 2026](https://futureagi.com/blog/voice-ai-barge-in-turn-taking-2026/); [AI Engineer World's Fair 2026](https://www.ai.engineer/talks/hMlLw1LeIK8-designing-voice-agents-real-conversations)). Silence-only VAD truncates callers who pause mid-thought.
- **Keypad secrets.** Payment-card guidance prefers DTMF masking to pause-and-resume recording, and notes that DTMF events, transcripts, and QA exports can also capture digits ([Call Centre Helper](https://www.callcentrehelper.com/new-guidance-secure-telephone-payments-140960.htm); [OneUptime, 2026](https://oneuptime.com/blog/post/2026-09-24-pci-dss-call-recordings-dtmf-voip-scope/view)). The same reasoning applies to TINs and OTPs.
- **Voice-specific attacks.** Audio prompt injection, voice cloning, caller-ID spoofing, and tool-call abuse affect the audio leg; a transcript-only review can miss them ([arXiv 2607.28165](https://arxiv.org/pdf/2607.28165); [Hamming](https://hamming.ai/resources/voice-agent-prompt-injection-testing-guide)). OWASP has no voice-specific list; LLM01 (prompt injection) applies.
- **Disclosure.** EU AI Act Article 50(1) applies from 2 August 2026. Commission guidance (20 July 2026, non-binding) calls for a spoken disclosure at the first interaction ([Famulor](https://www.famulor.io/blog/eu-ai-act-article-50-what-your-ai-phone-agent-must-say)). South Sudan is not bound by it, and the statutory wording is OQ-009 item 2.
