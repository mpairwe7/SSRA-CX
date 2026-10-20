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
4. **Cohort Feature Flagging (`flags.py`):** All new agentic capabilities require deterministic HMAC-SHA256 percentage/cohort feature flags (`ai/policies/feature-flags.yaml`) manageable via the Admin control plane.

## 3. Options Considered

1. **External LLM Agent Frameworks & Unbounded Autonomous Loops:** Violates NCA sovereignty, introduces numeric hallucination risks, and breaks deterministic latency budgets.
2. **Feature-Flagged 12-Stage Deterministic Extensions Inside `ssra_core`, `ssra_runtime`, `ssra_workers`, and `ssra_api` (Selected):** Extends the existing 11-node LangGraph supervisor shell with bounded multi-step `Plan` execution (`max_plan_steps=4`), post-tool `verify_plan_outcomes`, CPU-native `eq_detector.py`, 2-turn hysteretic `language_state.py` (`EnglishRouterEnvelope`), consent-gated 4-tier memory (`memory.py` with figure stripping), `HandoffEnvelope` v2 + `OfficerResolutionArtifact` warm return, and Temporal `continuation.py`.

## 4. Decision

We adopt Option 2:

1. **Cohort Feature-Flag Engine (`libs/ssra_core/src/ssra_core/flags.py`, `ai/policies/feature-flags.yaml`, `GET/POST /v1/admin/feature-flags`):**
   - Evaluates `FF_AUTONOMOUS_GOAL_PLANNER`, `FF_COGNITIVE_MEMORY_4TIER`, `FF_REALTIME_EQ_TONE_AND_ESCALATION`, `FF_ENGLISH_ROUTER_CANONICAL`, `FF_HANDOFF_ENVELOPE_V2_AND_WARM_RETURN`, and `FF_TEMPORAL_POST_INTERACTION_CONTINUATION` via deterministic HMAC-SHA256 bucketing.
2. **Multimodal EQ & Hysteretic Language-State / English Router (`eq_detector.py`, `language_state.py`, `services/voice`):**
   - Computes `AffectiveSnapshot` (`primary_emotion`, `intensity`, `frustration_velocity`, `recommended_tone`), modulates TTS speaking rate (`0.92x`) and calm preambles, and blocks adversarial emotional policy-bypass attempts.
   - Normalizes South Sudanese vernacular queries (`pga`, `ar`, `din`, `nus`, `bfa`, `zne`, `shk`) into `EnglishRouterEnvelope` while preserving statutory tokens (TINs, section anchors, SSP/USD figures).
3. **Bounded Goal Planner & Outcome Verifier (`planner.py`, `verifier.py`, `self_service.py`, `compose.py`):**
   - Executes multi-step `Plan` DAGs within `TurnBudget` and verifies provenance and domain blockers (`OVERDUE_BALANCE_REQUIRES_SETTLEMENT`, `FILING_STATUS_NOT_CURRENT`) before composition.
4. **4-Tier Cognitive Memory, `HandoffEnvelope` v2 & Temporal Continuation (`memory.py`, `handoff.py`, `continuation.py`, `conversations` API):**
   - Adds consent-gated `EpisodicMemoryRecord` (Tier 2) and `ActiveGoalRecord` (Tier 4) with mandatory `strip_financial_figures_for_memory` and instant single-call Right-to-Erasure.
   - Emits `HandoffEnvelope` v2 on officer escalations, supports `OfficerResolutionArtifact` on `POST /v1/conversations/{id}/handback`, and dispatches consent-checked post-interaction goal continuations (`run_post_interaction_goal_continuation`).

## 5. Consequences

- **Positive:** Higher quality-adjusted autonomous resolution on compound flows, zero context repetition on officer handoffs, real-time empathetic de-escalation, and full backward compatibility with all existing contracts and guardrails.
- **Negative / Trade-offs:** Additional state fields in `ConversationGraphState` and `RuntimeTurnResponse`, governed by strict Pydantic/Zod schemas and feature flags.

## 6. Reversal Cost & Migration Path

- **Reversal Cost:** Low. Any capability can be disabled instantaneously via `POST /v1/admin/feature-flags` (`enabled: false`, `rollout_pct: 0`) without code rollback.
