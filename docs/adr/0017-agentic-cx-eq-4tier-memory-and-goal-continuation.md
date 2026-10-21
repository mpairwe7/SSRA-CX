# ADR-017: October 2026 SSRA Agentic CX Enhancements — Autonomous Goal Planner, Multimodal EQ, 4-Tier Cognitive Memory, `HandoffEnvelope` v2, and Temporal Goal Continuation

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Founding Principal Architect / Staff Engineer, SSRA Technical Lead, SSRA SecOps
- **Reversal Cost:** Low–Medium
- **Linked Open Questions:** `OQ-001`, `OQ-002`, `OQ-003`
- **References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 3, 4, 6, 11, 12, 14

---

## 1. Problem Statement

How do we evolve SSRA Assist from single-turn Q&A and 1-shot tool execution into an October 2026 goal-driven agentic CX platform with real-time Emotional Intelligence (EQ), longitudinal 4-tier cognitive memory, structured `HandoffEnvelope` v2 officer collaboration, and post-interaction Temporal goal continuation—while preserving 100% statutory figure provenance, OPA `T0`–`T4` boundaries, and on-premises NCA sovereignty?

## 2. Context

1. **Goal-Driven Autonomous Execution:** Taxpayers frequently express compound requests in a single turn (e.g., checking both their e-Tax balance and TCC or filing status) or ask clarifying questions mid-way through a guided journey.
2. **Continuous Relationships & 4-Tier Memory:** Taxpayers switch across Web PWA, WhatsApp, SMS, USSD, and Voice (`en`, `pga`, `ar`, `din`, `nus`, `bfa`, `zne`, `shk`). Without consent-gated Episodic (Tier 2) and Procedural Goal (Tier 4) memory, context is lost across sessions.
3. **Real-Time Emotional Intelligence (EQ):** High-emotion cases (detained consignments at Nimule, frozen accounts, collector scams) require sub-5ms emotion/frustration-velocity detection, calm tone/prosody adaptation, and pre-emptive officer escalation—without allowing emotional manipulation to bypass `T0`–`T4` OPA policy gates.
4. **Cohort Feature Flagging (`flags.py`):** Agentic capabilities use deterministic HMAC-SHA256 percentage/cohort feature flags (`ai/policies/feature-flags.yaml`). The admin HTTP control plane is reference-only and returns 403 until OQ-014 staff authorization and OQ-015 durable audit state are implemented.

## 3. Options Considered

1. **External LLM Agent Frameworks & Unbounded Autonomous Loops:** Violates NCA sovereignty, introduces numeric hallucination risks, and breaks deterministic latency budgets.
2. **Feature-Flagged 12-Stage Deterministic Extensions Inside `ssra_core`, `ssra_runtime`, `ssra_workers`, and `ssra_api` (Selected):** Extends the existing 11-node LangGraph supervisor shell with bounded multi-step `Plan` execution (`max_plan_steps=4`), post-tool `verify_plan_outcomes`, CPU-native `eq_detector.py`, 2-turn hysteretic `language_state.py` (`EnglishRouterEnvelope`), consent-gated 4-tier memory (`memory.py` with figure stripping), `HandoffEnvelope` v2 + `OfficerResolutionArtifact` warm return, and Temporal `continuation.py`.

## 4. Decision

We adopt Option 2:

1. **Cohort Feature-Flag Engine (`libs/ssra_core/src/ssra_core/flags.py`, `ai/policies/feature-flags.yaml`):** The engine supports local/reference evaluation. `GET/POST /v1/admin/feature-flags` return 403 until a server-verified staff session and durable audit path are available.
   - Evaluates `FF_AUTONOMOUS_GOAL_PLANNER`, `FF_COGNITIVE_MEMORY_4TIER`, `FF_REALTIME_EQ_TONE_AND_ESCALATION`, `FF_ENGLISH_ROUTER_CANONICAL`, `FF_HANDOFF_ENVELOPE_V2_AND_WARM_RETURN`, and `FF_TEMPORAL_POST_INTERACTION_CONTINUATION` via deterministic HMAC-SHA256 bucketing.
   - A local shared override is re-read by content digest before HMAC validation, so same-timestamp writes cannot retain stale state. Each signed rule uses a strict typed schema with supported channel and locale scopes; non-finite numbers, missing, malformed, unsigned, or schema-invalid envelopes clear local overrides and restore the reviewed YAML rules. This reference file does not satisfy durable operational state requirements.
2. **Multimodal EQ & Hysteretic Language-State / English Router (`eq_detector.py`, `language_state.py`, `services/voice`):**
   - Computes `AffectiveSnapshot` (`primary_emotion`, `intensity`, `frustration_velocity`, `recommended_tone`), modulates TTS speaking rate (`0.92x`) and calm preambles, and blocks adversarial emotional policy-bypass attempts.
   - Normalizes South Sudanese vernacular queries (`pga`, `ar`, `din`, `nus`, `bfa`, `zne`, `shk`) into `EnglishRouterEnvelope` while preserving statutory tokens (TINs, section anchors, SSP/USD figures).
3. **Bounded Goal Planner & Outcome Verifier (`planner.py`, `verifier.py`, `self_service.py`, `compose.py`):**
   - Executes multi-step `Plan` DAGs within `TurnBudget` and verifies provenance and domain blockers (`OVERDUE_BALANCE_REQUIRES_SETTLEMENT`, `FILING_STATUS_NOT_CURRENT`) before composition.
4. **4-Tier Cognitive Memory, `HandoffEnvelope` v2 & Temporal Continuation (`memory.py`, `handoff.py`, `continuation.py`, `conversations` API, `database.py`):**
   - Adds consent-gated `EpisodicMemoryRecord` (Tier 2) and `ActiveGoalRecord` (Tier 4) with mandatory `strip_financial_figures_for_memory`, `EpisodicMemoryORM`/`ActiveGoalORM` DDL, and instant single-call Right-to-Erasure.
   - Emits `HandoffEnvelope` v2 on officer escalations, supports `OfficerResolutionArtifact` on `POST /v1/conversations/{id}/handback` + `apply_officer_handback_resolution`, supports mid-journey `workflow_stack` delegation and Cross-Tier Read -> Stage-Write planning, and dispatches consent-checked post-interaction goal continuations (`run_post_interaction_goal_continuation`, `build_continuation_candidates_from_outbox_events`).
5. **Hybrid Speech Architecture, Semantic Endpointing & Offline Statutory Resilience Pack (`services/voice`, `packages/chat-ui/src/voice-notes.ts`, `offline-resilience.ts`, `offline-outbox.ts`, `tools/validate_schemas.py`, `apps/web/public/sw.js`):**
   - Implements `select_hybrid_voice_execution_mode` (`S2S_FAST_ACK_CACHED` `<250ms` TTFA tool-wait fillers + `CASCADED_GOVERNED_STT_LLM_TTS`), `normalize_statutory_text_for_speech`, `verify_spoken_figure_fidelity` (with `strict_no_extra_numbers=True` rejecting unclaimed numeric tokens), `verbalize_statutory_figures_for_tts`, statutory abbreviation protection in `split_tts_sentences` (`Sec.`, `Reg.`, `Art.`), spoken `ClarifyGate`, `sync_affective_state_to_call_lobby`, `build_call_to_web_carryover`, `resume_after_network_drop`, `evaluateSemanticEndpointing` (`420ms..1100ms`), `calculateOfflinePayeEstimate` & `calculateOfflineWithholdingEstimate` (using `roundHalfUpTwoDecimals` and verified against `knowledge/tax-facts/seed-2026.10.1.yaml` in `tools/validate_schemas.py`), `enqueueVoiceNote` (`<=64KB`, `<=30s`, `T0`-only), `verifyOfflineOfficialChannel`, and `resolveAdaptiveVoiceNetworkProfile` (`12 kbps` Opus on 2G).

## 5. Consequences

- **Positive:** Higher quality-adjusted autonomous resolution on compound flows, zero context repetition on officer handoffs, real-time empathetic de-escalation, and full backward compatibility with all existing contracts and guardrails. Verified under live Docker GPU + Local HF Cache + Qdrant + Valkey + PostgreSQL 18 + `ssra-frontend` (`:3033`) / `ssra-console` (`:3034`) (`infra/compose/docker-compose.gpu.yml`) and Ngrok HTTPS load via `tools/run_20000_complex_ngrok_benchmark.py` (`20,000/20,000` scenarios / `20,120` turns passed across `en`, `ar`/`pga`, `din` and `TTT`/`STT`/`TTS`, `265.51 turns/sec` / `15,930.4 turns/min`, `p50=56.35ms`, `40` Qdrant episodic points capped at `MAX_EPISODES_PER_SUBJECT=20` per subject at peak & `0` residual points after Right-to-Erasure, with `QA2-G1`..`QA2-G7` and `BE-G1`..`BE-G6` backend setup/flow hardening).
- **Negative / Trade-offs:** Additional state fields in `ConversationGraphState` and `RuntimeTurnResponse`, governed by strict Pydantic/Zod schemas and feature flags.

## 6. Reversal Cost & Migration Path

- **Reversal Cost:** Low for locally evaluated feature configuration. No live admin HTTP control is available; staff-controlled rollout and emergency disablement require OQ-014/OQ-015 implementations and an approved operational procedure.
