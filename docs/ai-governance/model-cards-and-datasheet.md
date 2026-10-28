# SSRA Assist — Model Cards & Knowledge Corpus Datasheet (`docs/ai-governance/model-cards-and-datasheet.md`)

**Status:** v1.1 (Phase 0–4 Governance Deliverable)  
**Date:** 2026-10-24  
**References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 6.4, 7, 11, 12.5, [`ADR-027`](../adr/0027-voice-multiturn-continuity-echo-guard-and-barge-in.md), [`ADR-028`](../adr/0028-multiturn-continuity-and-toolathlon-orchestration-hardening.md)

---

## 1. Sovereign Model Cards

### 1.1 Model Card 1: Fast Guard & Intent Router (`ssra-sovereign/sunflower-qwen3.5-9b` / `Sunbird/Sunflower-Qwen3.5-9B`)
- **Role in Graph:** Nodes 3 (`input_guard`) and 4 (`understand`).
- **Hosting:** In-country NCA Docker Compose GPU host via vLLM (`ADR-007`, offline cache `/home/developer/huggingface_cache`, revision `c56081c5024b1c11186a69898f5f6a7a2dabe454`).
- **Inputs & Outputs:** Receives Presidio-redacted user input; emits strictly validated `Intent` JSON Schema (`intent`, `slots`, `language`, `confidence`). Supports deterministic multi-turn anaphoric slot carry-over (`_resolve_multiturn_followup` in `en`, `ar`, and `pga`), CIF-isolated SSP amount extraction, and `_STEP_CONTINUATION_ELIGIBLE` guided-journey progression (`ADR-028`).
- **Safety Constraint:** Never assigns risk tiers; risk tiers are resolved deterministically from `ai/policies/risk-tiers.yaml`.
- **Target Latency:** p95 ≤ 300 ms.

### 1.2 Model Card 2: Multilingual Grounded Composer & Thinking Reasoner (`ssra-sovereign/sunflower-qwen3.5-9b` / `Sunbird/Sunflower-Qwen3.5-9B` & `Qwen/Qwen3.8-27B-FP8`)
- **Role in Graph:** Node 8 (`compose`).
- **Hosting:** In-country NCA Docker Compose GPU host (`Sunbird/Sunflower-Qwen3.5-9B` @ `c56081c5024b1c11186a69898f5f6a7a2dabe454` and `Qwen/Qwen3.8-27B-FP8` @ `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a` with `enable_thinking: true` / `--reasoning-parser qwen3`; secondary fallback: `ssra-sovereign/qwen3-8b`; CPU emergency fallback: `ssra-sovereign/qwen2.5-3b-cpu-gguf`).
- **Inputs & Outputs:** Receives layered prompt `L0`–`L5` with spotlighted data-only delimiters (`<untrusted_retrieved_evidence>`, `<untrusted_tool_artifacts>`) and `ai/termbase/glossary.yaml`; emits structured `Answer` (`segments[]`, `citations[]`, `numbers[]`, `ui_component`), synthesizing compound multi-tool turns across PAYE, Withholding Tax, Customs Duty/Tariff, and authenticated T1 Ledger/TCC records (`ADR-028`).
- **Safety Constraint:** Every output passes Stage 9 quiet-fault verification (`_detect_quiet_tool_fault` / `QUIET_FAULT_DETECTED` abstention gate) and Node 9 (`output_guard`: `numeric_provenance` 100% gate, `grounding`, `pii`, `neutrality`) before reaching any user.

### 1.3 Model Card 3: Multilingual Embedding & Reranker (`BGE-M3` / `Qwen3-Embedding` + `Qwen3-Reranker`)
- **Role:** Hybrid lexical + dense vector retrieval (`pgvector` 0.8+ HNSW iterative scans) and cross-encoder reranking across English (`en`), Arabic (`ar`), Juba Arabic (`pga`), and Tier C national languages (`din`, `nus`, `bfa`, `zne`, `shk`).

### 1.4 Model Card 4: Speech Pipeline (`Whisper-large-v3-turbo`, `Sunbird/SunflowerASR-51-african-languages` & `Sunbird/orpheus-3b-tts-multilingual`)
- **Role:** Phase 4 Voice/IVR & Streaming Speech (`services/voice` & `packages/chat-ui/src/voice-notes.ts`).
- **Hosting:** Offline HuggingFace cache `/home/developer/huggingface_cache` (`Sunbird/SunflowerASR-51-african-languages` @ `4583c9dd251c422a4325fb0a0a509a3828097be2`, `Sunbird/orpheus-3b-tts-multilingual` @ `c44496fdfa162c4ecd15c846fcbcac15bba28951`, and `facebook/mms-tts-*` VITS checkpoints).
- **Launch Gate & Controls:** A language is enabled on Voice/IVR only when governed evidence (`APPROVED_VOICE_WER_EVIDENCE`: language, WER, SSRA test set, date, utterance count) shows a Word Error Rate `<= 0.12` (`MAX_VOICE_WER_GATE`). As of 2026-10-24 no language has such evidence (OQ-008), so every voice caller is transferred to an officer. Benchmark speech scenarios are simulated and are not WER evidence. Every call opens with an AI disclosure that speech cannot interrupt and an opt-in recording request (`build_call_opening_prompts`; interim English wording pending OQ-009). Whisper segments marked as silence or unreliable by the decoder's default thresholds never reach the runtime (`assess_whisper_segment`). Includes stateful multi-turn `VoiceCallSession` (`ADR-027`), 450 ms post-TTS acoustic echo guard (`POST_TTS_ECHO_COOLDOWN_MS`, `is_likely_tts_echo`), listener backchannel immunity (`is_backchannel_utterance`), locale-scoped speaker catalog resolution (`resolve_tts_voice`), sentence-chunked TTS + barge-in that stops playback and cancels generation together and ignores speech shorter than the VAD minimum (`VoiceStreamSession`, `BargeInDirective`), adaptive room-floor end-of-turn detection (`EndOfTurnDetector`), WCAG 2.2 SC 1.4.2 `NarrationBar` (`buildNarrationBarView`), and privacy-preserving SHA-256 voice consent auditing (`build_voice_consent_audit_entry`, `store_raw_audio=False`).

### 1.5 Model/UI deployment boundary
- The October 2026 frontend audit did not change model weights, prompts, retrieval, or output-guard behavior. UI status labels and local role selections are not model evidence or authorization.
- The staff console remains a non-operational preview until OQ-014 is approved. Do not interpret browser-rendered case examples, historical sample metrics, or local preview personas as real taxpayer records, current service state, or authenticated roles.
- Public chat fallback text does not claim a KnowledgeSnapshot citation while offline. A response can claim source support only when the runtime supplies the approved citation metadata.
- The runtime uses process-local `InMemorySaver` and therefore returns 503 outside explicit local/test reference mode. Chat completion, checkpoint continuity, identity verification, document guidance, appointments, staff inbox/actions, knowledge publication, service status, and operational analytics must not be represented as production capabilities until their providers, trusted authorization, provenance, and persistence are approved (OQ-005, OQ-013–OQ-017).
- Model revisions recorded here identify reference artifacts only. OQ-018 remains open for the registry, signing identity, trust root, revocation process, and verification point required before a model can be treated as a production-approved artifact.

---

## 2. Datasheet for the SSRA Knowledge Corpus (`knowledge/`)

1. **Motivation:** Provide an authoritative, auditable, versioned legal and procedural corpus for SSRA Assist so that zero unverified claims or numbers ever reach taxpayers.
2. **Composition:** Public statutory instruments enacted by the Republic of South Sudan and circulars issued by SSRA:
   - South Sudan Revenue Authority Act, 2016 (as amended October 2023)
   - Taxation Act, 2009 (as amended)
   - Customs Service Act, 2013
   - Financial Act 2024/2025 & SSRA Implementation Circulars
   - March 2026 Cash-Free Bank Remittance Directive
   - Official e-Tax Portal (`https://etax.nra.gov.ss/`) Registration, Filing & TCC Procedures
3. **Collection & Ingestion Process:** Parsed by legal hierarchy (`Part`, `Chapter`, `Section`, `Subsection`), assigned immutable `section_anchor` IDs and SHA-256 checksums, and aligned with the multilingual tax termbase (`ai/termbase/glossary.yaml`).
4. **Release & Maintenance:** The six-step Knowledge Release state machine is a reference implementation in `services/api` (`knowledge_admin`) and `apps/console`. Its API routes return 403 until server-verified staff authorization and durable audit/storage exist; no operational publication or rollback is exposed (OQ-014/OQ-015).
5. **Privacy & Confidentiality:** Contains `PUBLIC` statutory and procedural guidance only; zero taxpayer records or confidential drafts are stored in the corpus (`knowledge/sources.yaml`).
