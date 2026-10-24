# Call Receptionist Audit — October 2026

**Review date:** 2026-10-24 (Africa/Juba)
**Commit:** `70a6d1a`
**Scope:** `services/voice` (`ssra_voice`), `packages/chat-ui/src/call-receptionist.ts`, the `VoiceIvrChannelAdapter`, the web voice-input dialog, the staff "Calls" preview, and the voice services in the GPU Compose profile.

## What exists

The master prompt specifies Voice/IVR as a Phase 4 channel. It requires a SIP trunk into LiveKit SIP or Asterisk/FreeSWITCH, streaming ASR → runtime → TTS, barge-in, a DTMF fallback, a language menu, recording consent, and warm transfer with an AI summary. A language may launch on voice only after its word-error rate on SSRA test sets meets the gate.

| Component | State at `70a6d1a` |
|---|---|
| Telephony (SIP, RTP, voice WebSocket) | **Not present.** No trunk, media server, or voice endpoint is deployed |
| `ssra_voice` | A library of routing, step-up, brief, lobby, caching, speech-formatting, and `FinalYearProject` Call Receptionist & Voice/Speech backend helpers (`VoiceCallSession` in-call controls & interrupted-offer guard, `is_spoken_officer_request`, `is_tax_dispute`, `classify_spoken_call_review`, `split_receptionist_spoken_sentences`, `should_drop_ai_frame_when_bridged`, `compute_transfer_queue_position`, `evaluate_live_call_risk`, 2G/3G `negotiate_low_bandwidth_voice_profile` + G.711 mu-law transcoding + single-use `mint_call_resume_ticket` / `verify_call_resume_ticket`, `clean_text_for_speech`, `detect_ssra_entity_mishear`, `repair_ssra_asr_entities`, `assess_spoken_clarification`, and `CallLanguagePolicy`). `python -m ssra_voice` prints a status object and exits. It is called only by unit tests, evaluation suites, and benchmark tools |
| `call-receptionist.ts` | View-model helpers (consent gate, language chip, orb animation, caption pinning). Not imported by the served pages |
| `VoiceIvrChannelAdapter` | Joins answer segments and cuts at 1,000 characters |
| Web voice-input dialog | Browser speech recognition for `en` and `ar`, with the R2-D accessibility fixes; upgraded in ADR-027 with the `FinalYearProject` Call Receptionist sheet (`CallOrb`, `CallLanguageChip`, live caption thread, Mute/Officer dock) and main-composer `NarrationBar`, `.composer-active-recording` bar, and `#composer-voicemode-btn` toggle |
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
| AUD-041 | S2 | SMS and IVR output can cut figures and drop the citation; "SSRA OFFICIAL" label; spelled-out numbers and Arabic-Indic digits defeat the figure guard | R2-K (fixed) |
| AUD-042 | S2 | No spoken AI disclosure at call start; barge-in not implemented | R2-K (fixed; wording pending OQ-009) |
| AUD-043 | S2 | Core API, Sunflower vLLM, and Orpheus TTS published on all interfaces; Orpheus not digest-pinned | Decision needed (R3) |
| AUD-044 | S2 | Text an ASR model invents on silence or noise could reach the runtime | R2-K (fixed) |
| AUD-045 | S3 | Call view model hid who had the floor under reduced motion; no AI or recording indicator | R2-K (fixed) |
| AUD-046 | S2 | Official CMS snapshot says TCCs are "valid for twelve (3) months" | SSRA decision needed |
| AUD-047 | S3 | `ssra-voice` does not declare its `ssra-security` dependency | R3 |

Details and evidence are in [the findings register](../audit/findings.md#call-receptionist-audit-2026-10-24).

## Phased remediation

1. **R2-I: Identity and integrity (implemented).** DTMF step-up requires an approved OTP verifier and fails closed without one. Carryover tokens need a configured key and expire. The call lobby enforces first-claim-wins and keeps tombstones for ended calls.
2. **R2-J: Truthful gates and records (implemented).** A governed per-language WER record with no approved languages until evidence exists. Benchmarks label speech scenarios as simulated. Officer briefs and transfer summaries state only what happened. Retention is pending OQ-009. The TTS cache covers fixed prompts only.
3. **R2-K: What the caller hears and receives (implemented).** A spoken AI disclosure and a route to a person at call start, then opt-in recording consent (interim wording pending OQ-009). Barge-in stops playback and cancels generation together, and ignores short noises and the disclosure. SMS and IVR output keep whole sentences, never split a figure, keep the citation, and report their real GSM-7 or UCS-2 segment count. The spoken-figure guard also reads spelled-out English numbers and Arabic-Indic digits. Whisper output on silence or in a repetition loop never reaches the runtime. The call view model keeps who-has-the-floor under reduced motion and says whether the caller is talking to the AI or an officer, and whether recording is on.
4. **Platform decision (R3).** Bind the Core API and model servers to loopback, pin or remove Orpheus, and route model calls through `agentgateway`.

Live telephony needs separate decisions: carrier and SIP provider (OQ-007), identity and OTP provider (OQ-005), contact-centre hours and queues (OQ-010), retention and disclosure wording (OQ-009), and measured WER per language (OQ-008).

## Standards and research checked on 2026-10-24

These sources are mostly practitioner and vendor guidance, not formal standards, and are used as design targets only.

- **Turn-taking and barge-in.** A full round trip under about 700 ms is a common target. A barge-in should stop TTS and cancel generation together, because cancelling only one leaves stale audio or stale work ([FutureAGI, 2026](https://futureagi.com/blog/voice-ai-barge-in-turn-taking-2026/); [AI Engineer World's Fair 2026](https://www.ai.engineer/talks/hMlLw1LeIK8-designing-voice-agents-real-conversations)). Silence-only VAD truncates callers who pause mid-thought. Short listener backchannels ("mm-hm", "okay", "نعم") should not cancel an in-flight answer, and after a real interruption only the sentences actually played should remain in heard conversation context ([Speko Benchmarks, Aug 2026](https://benchmarks.speko.ai/blog/turn-taking-for-voice-agents/); [Reson8, 2026](https://www.reson8.dev/wiki/turn-taking-and-barge-in)).
- **Browser Web Speech API echo suppression and continuous turn-taking.** Combining `SpeechRecognition` and `SpeechSynthesis` without pausing recognition during TTS and waiting 450–500 ms after `utterance.onend` causes the microphone to transcribe the tail of the assistant's own speech ([MARIA OS, Feb 2026](https://os.maria-code.ai/en/blog/sentence-level-streaming-vui-architecture); [semicolonweb, Oct 2026](https://semicolonweb.com/blog/speech-transcription-voice-web)). Implemented in [ADR-027](../adr/0027-voice-multiturn-continuity-echo-guard-and-barge-in.md).
- **Keypad secrets.** Payment-card guidance prefers DTMF masking to pause-and-resume recording, and notes that DTMF events, transcripts, and QA exports can also capture digits ([Call Centre Helper](https://www.callcentrehelper.com/new-guidance-secure-telephone-payments-140960.htm); [OneUptime, 2026](https://oneuptime.com/blog/post/2026-09-24-pci-dss-call-recordings-dtmf-voip-scope/view)). The same reasoning applies to TINs and OTPs.
- **Voice-specific attacks.** Audio prompt injection, voice cloning, caller-ID spoofing, and tool-call abuse affect the audio leg; a transcript-only review can miss them ([arXiv 2607.28165](https://arxiv.org/pdf/2607.28165); [Hamming](https://hamming.ai/resources/voice-agent-prompt-injection-testing-guide)). OWASP has no voice-specific list; LLM01 (prompt injection) applies.
- **Recording consent.** Practitioner checklists treat the AI disclosure and recording consent as separate steps, ask for an explicit action (saying yes or pressing a key) before recording starts, and offer a real alternative to callers who decline ([Retell AI checklist](https://www.retellai.com/learn/call-consent-and-disclosure-checklist-for-deploying-ai-voice-agents); [AI Front Desk, 2026](https://www.myaifrontdesk.com/blogs/ai-communication-compliance-checklist-2026)). R2-K follows that order: disclosure, then keypad 1 to allow recording, with the call continuing either way.
- **ASR hallucination.** Whisper can produce fluent text on silence. VAD gating before inference is the primary fix, and the decoder's `no_speech_prob`, `avg_logprob`, and `compression_ratio` thresholds (defaults 0.6, -1.0, and 2.4) are a second layer ([Dograh](https://www.dograh.com/feeds/blog/whisper-hallucination-silence); [arXiv 2609.04561](https://arxiv.org/pdf/2609.04561); [openai/whisper fallback fix](https://app.semanticdiff.com/gh/openai/whisper/commit/90db0de1896c23cbfaf0c58bc2d30665f709f170)).
- **SMS segments.** One segment carries 140 octets: 160 GSM-7 characters or 70 UCS-2 code units, 153 and 67 per segment once concatenated, and one character outside GSM-7 switches the whole message to UCS-2 (3GPP TS 23.038 and TS 23.040, as summarised by [Bird](https://bird.com/en-gb/docs/guides/sms/character-limits.md) and [Messente](https://support.messente.com/message-length)).
- **Caller identity.** Caller ID can be spoofed, and cloned voices defeat commodity voiceprints, so neither is treated as identity; voice step-up relies on a keypad OTP checked by the identity provider (ADR-024) ([Matellio](https://matellio.com/blog/phone-caller-id-spoofing-prevention-banks/); [Seiright](https://seiright.com/blog/voice-cloning-deepfake-caller-verification-banks-phishing-resistant)).
- **Disclosure.** EU AI Act Article 50(1) applies from 2 August 2026. Commission guidance (20 July 2026, non-binding) calls for a spoken disclosure at the first interaction ([Famulor](https://www.famulor.io/blog/eu-ai-act-article-50-what-your-ai-phone-agent-must-say)). South Sudan is not bound by it, and the statutory wording is OQ-009 item 2.
