# ADR-004: Stateless MCP Revision 2026-07-28 and `agentgateway` Single Egress

- **Status:** Proposed
- **Date:** 2026-10-16
- **Deciders:** Founding Principal Architect / Staff Engineer, SSRA Technical Lead, SSRA SecOps
- **Reversal Cost:** High
- **References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 4, 5, 8, 12.1–12.3, Appendix A

---

## 1. Problem Statement

How do we expose SSRA domain capabilities to the agent runtime and govern every LLM and tool invocation with per-call zero-trust authorization, subject binding, spend limits, auditability, and horizontal load balancing?

## 2. Context

In an agentic government tax platform, the boundary between probabilistic LLM reasoning and deterministic business capabilities is the primary attack surface (OWASP Agentic Top 10 2026 ASI02/ASI03, OWASP MCP Top 10, NSA May 2026 MCP Security Guidance). Earlier MCP revisions relied on stateful `initialize` sessions and stdio/SSE session affinity, complicating horizontal scaling and per-request authorization. Additionally, allowing the agent runtime to call LLMs or internal services directly bypasses centralized policy enforcement, tool-description drift detection, and token/spend governance.

## 3. Options Considered

1. **In-Process Python Function Tools inside `services/agent-runtime`:** Zero network hop, but couples the runtime's security context with database and upstream credentials. A prompt injection or runtime vulnerability could access any tool without an independent policy enforcement point.
2. **Legacy Stateful MCP (2024-11-05 / 2025-03-26) with Direct Runtime-to-Server Connections:** Requires sticky sessions for `initialize` state, lacks header-based gateway routing, and scatters authorization across individual servers.
3. **Stateless MCP Revision `2026-07-28` over Streamable HTTP behind `agentgateway` 1.x as Single Egress (Selected):** Every tool server speaks stateless MCP `2026-07-28`, and `agentgateway` mediates 100% of LLM, MCP, and future A2A traffic.

## 4. Decision

We adopt Option 3 with the following mandatory controls:

1. **MCP Revision `2026-07-28` Baseline (`mcp` Python SDK `2.3.0` + `libs/ssra_mcp`):**
   - **Stateless requests:** No `initialize` handshake session; every request is self-contained and carries protocol version `2026-07-28` and client capabilities in `_meta`.
   - **Header-based routing:** `agentgateway` routes requests using `Mcp-Method` and `Mcp-Name` HTTP headers, allowing `mcp-servers/*` pods to scale behind standard stateless round-robin Kubernetes Services.
   - **Schema & discovery:** Tool input/output schemas use JSON Schema `2020-12` with `structuredContent` and are validated in CI. `tools/list` responses declare `ttlMs` for gateway caching.
   - **Streamable HTTP only:** No `stdio` transports in deployed environments; deprecated MCP `Roots`, `Sampling`, and `Logging` features are prohibited in favour of W3C `traceparent` / OpenTelemetry trace context.
2. **`agentgateway` 1.x as the Single Governed Egress:**
   - Network policies (`infra/policies/`) block `services/agent-runtime` from initiating egress to any LLM provider, MCP server, or upstream except through `agentgateway` over mTLS.
   - **Per-invocation authorization (OPA/CEL):** Every `tools/call` is authorised against `(calling_workload, subject_ref, auth_level, tool_name, tier, argument_shape, tool_annotations)`.
   - **OAuth 2.1 & RFC 8693 Token Exchange:** Each MCP server is an OAuth 2.1 resource server validating short-lived, audience-bound JWTs issued by Keycloak. For `T1`–`T3` calls, `agentgateway` performs RFC 8693 token exchange to bind the verified taxpayer `subject_ref`—no user token passthrough and no trust in model-supplied identity fields.
   - **Confirmation & Idempotency Enforcement:** State-changing tools (`T2`/`T3`, `readOnlyHint: false`) require both `idempotency_key` and a single-use, short-TTL `confirmation_token` bound to `sha256(canonical_args)`.
   - **Tool Description Hash Pinning:** Tool descriptions are reviewed as code; `agentgateway` pins their SHA-256 hashes to block rug-pull or description-injection attacks.

## 5. Consequences

- **Positive:**
  - Satisfies NSA May 2026 MCP guidance and OWASP Agentic/MCP Top 10 controls with a single choke point for kill switches, spend caps, SIEM logging, and hash-chained `AuditEvent` emission.
  - Stateless `2026-07-28` protocol enables simple round-robin load balancing and zero session-stickiness failures during pod rollouts.
- **Negative / Trade-offs:**
  - Adds an extra internal mTLS hop (`agent-runtime` → `agentgateway` → `mcp-server`), typically adding 2–5 ms of in-cluster latency, well within our 8 s p95 tool-backed SLO.

## 6. Reversal Cost & Migration Path

- **Reversal Cost:** High. All 11 domain tool servers and the runtime client depend on the MCP `2026-07-28` contract and `libs/ssra_mcp`. However, because each MCP tool wraps an anti-corruption port in `libs/ssra_adapters` or a service in `services/api`, the underlying business logic remains independent of the MCP transport layer.
