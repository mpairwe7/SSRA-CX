# ADR-007: Sovereign Open-Weight Model Hosting and Tiered Routing

- **Status:** Proposed
- **Date:** 2026-10-16
- **Deciders:** Founding Principal Architect / Staff Engineer, SSRA Technical Lead, SSRA SecOps
- **Reversal Cost:** Medium
- **Linked Open Questions:** `OQ-003`, `OQ-004`
- **References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 4, 5, 6.4, 12.3, 13

---

## 1. Problem Statement

How do we run LLM inference in-country on NCA infrastructure with bounded latency and cost, a deterministic degradation ladder, and strictly governed optional routing to external providers?

## 2. Context

Principle 7 requires SSRA Assist to run fully in-country on open-weight models by default so taxpayer data never leaves South Sudan without explicit approval. Different nodes in the 11-node conversation graph have distinct compute profiles:
- `input_guard` and `understand` need sub-300 ms structured classification;
- `compose` needs strong multilingual instruction following and citation formatting (`en`, `pga`, `ar`);
- Complex multi-step reasoning is rarely needed because calculations and rules live in deterministic MCP tools.

Furthermore, GPU hardware at NCA may experience maintenance or power interruptions (`OQ-003`), requiring a deterministic degradation ladder that keeps public tax assistance available even when LLM inference is degraded.

## 3. Options Considered

1. **External Cloud LLM APIs Only:** Violates data sovereignty (Principle 7) and fails completely during international link outages.
2. **Single Large Open-Weight Model for Every Node:** Excessive VRAM footprint and violates our 1.5 s p95 Web TTFT target on routine routing and guard turns.
3. **Provider-Agnostic `ModelPort` via `agentgateway` + Node-Tiered Open-Weight Models (vLLM/SGLang) + 5-Step Degradation Ladder (Selected):** Routes each graph node to the smallest capable sovereign model, with policy-gated external plug-ins (`OQ-004`) and graceful fallback to retrieval-only cards and static FAQs.

## 4. Decision

We adopt Option 3:

1. **Provider-Agnostic `ModelPort` (`libs/ssra_llm`):**
   - `services/agent-runtime` never imports vendor SDKs directly in graph nodes; it calls `ModelPort` configured in `ai/routing/model-routing.yaml`, which sends OpenAI-compatible requests with JSON Schema structured outputs through `agentgateway`.
2. **Node-Specific Model Tiers:**
   - **Fast / Guard Tier (`input_guard`, `understand`):** Small open-weight instruction model (e.g., 3B–8B class from Qwen / Llama / Gemma / Ministral families) served on vLLM/SGLang with prefix caching.
   - **Compose Tier (`compose`, `output_guard`):** Mid-size multilingual open-weight model (e.g., 14B–32B class) validated via bake-off on SSRA's English, Arabic, and Juba Arabic eval sets.
   - **External Frontier Plug-in (Disabled by Default):** May only be enabled per data class (`T0` anonymous public queries only) if SSRA signs off on `OQ-004` with Zero-Data-Retention (ZDR) terms; `agentgateway` blocks any `T1`+ or PII-tagged request from routing externally.
3. **Five-Step Deterministic Degradation Ladder:**
   1. **Primary sovereign model** (vLLM/SGLang primary replica)
   2. **Secondary smaller sovereign model** (fallback replica)
   3. **CPU-quantized emergency local model**
   4. **Retrieval-only Answer Cards** (published `KnowledgeSnapshot` sections + deterministic `TaxFact` table cards without LLM prose)
   5. **Static FAQ + Callback Request Intake**

## 5. Consequences

- **Positive:** Full sovereignty, predictable latency and VRAM usage, zero vendor lock-in, and continuous availability even during GPU outages.
- **Negative / Trade-offs:** Requires model bake-off evaluation (`evals/`) and publishing a model card (`docs/ai-governance/`) before promoting any model version.

## 6. Reversal Cost & Migration Path

- **Reversal Cost:** Medium. Swapping model families or inference engines requires only updating `ai/routing/model-routing.yaml` and `agentgateway` upstream definitions, followed by running `task eval` to verify launch gates.
