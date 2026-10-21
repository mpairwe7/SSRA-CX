# Architecture and ADR Claims Matrix

**Method:** Each row assesses the central decision or deployment assertion, rather than every explanatory sentence. A claim is Proven only where R0 reproduced it from source, configuration, or a passing local check. Contradicted means the current source/configuration conflicts with it. Unverified means source intent exists but no deployable or end-to-end proof was available.

## Architecture overview

| Claim | Status | Evidence | Finding |
|---|---|---|---|
| Public chat runs through a Node BFF and strips browser identity before forwarding turns. | Proven | apps/web/server.js sanitizes public turn bodies and permits only feedback under direct v1 routes. | AUD-009 has remaining fuzz coverage work |
| Staff console is preview-only and denies staff data/actions without trusted identity. | Proven | Console/source documentation and fail-closed routes; targeted tests pass. | AUD-004, AUD-009 |
| Core API is unavailable outside explicit reference mode. | Proven | API middleware returns RFC 9457 503; unset and unknown-mode tests pass. | AUD-009 for empty/mixed-case matrix |
| Agent runtime has durable governed conversation state. | Contradicted | InMemorySaver and process-local dictionaries are used. | AUD-001 |
| All runtime model and MCP egress is governed. | Contradicted | GPU profile points runtime directly at model/TTS URLs and omits agentgateway. | AUD-002 |
| Eleven MCP servers are available through deployable gateway topology. | Unverified | Routes list eleven hosts, but Compose does not run all eleven and tests are in-process. | AUD-010 |
| API state and outbox events are durable. | Contradicted | InMemoryOutboxBuffer and process-local consent/case stores are active reference implementation. | AUD-003, AUD-004 |
| GPU profile is an equivalent secure deployment path. | Contradicted | Direct egress, tag/default image values, env file use, and hardening gaps differ from general profile. | AUD-005 |
| Runtime trace context and audit flow span the full path. | Unverified | Source propagates traceparent; no full stack trace evidence. | AUD-012 |
| PWA offline statutory experience is governed by approved, current facts. | Unverified | Client literals are partly compared to registry but no signed, revocable generated snapshot exists. | AUD-011 |

## Architecture decision records

| ADR | Central decision | Status | Evidence | Finding |
|---|---|---|---|---|
| ADR-001 | Record decisions in versioned ADRs. | Proven | Twenty ADRs are present and indexed. | — |
| ADR-002 | Modular-monolith context boundaries. | Proven | import-linter passed with two protected contracts. | — |
| ADR-003 | LangGraph plus durable Temporal workflows. | Contradicted | LangGraph exists; in-memory checkpoint and absent Compose Temporal do not prove durable orchestration. | AUD-001 |
| ADR-004 | Stateless MCP and agentgateway-only egress. | Contradicted | General profile declares gateway; GPU profile bypasses it. | AUD-002, AUD-010 |
| ADR-005 | AG-UI and closed generative UI registry. | Proven | Registry/schema tests and source checks passed locally. | AUD-009 for rendered browser validation |
| ADR-006 | PostgreSQL plus pgvector hybrid retrieval. | Unverified | Schema/configuration exists; durable runtime repository adoption was not demonstrated. | AUD-003, AUD-004 |
| ADR-007 | Sovereign open-weight routing. | Unverified | GPU model services are configured; artifact/model signature and live sovereign-host proof are absent. | AUD-007 |
| ADR-008 | Risk tiers, subject binding, and OPA. | Proven in reference tests | Policy/runtime code and red-team tests pass; durable identity binding remains gated. | AUD-004 |
| ADR-009 | Tax facts and numeric provenance. | Proven for runtime; Unverified for offline pack | Runtime output guard/evals pass; browser statutory literals are not generated and signed. | AUD-011 |
| ADR-010 | Next.js 16 frontend stack. | Superseded | ADR-020 records the actual Node BFF runtime; ADR-010 is retained only as a historical design proposal. | AUD-008 |
| ADR-011 | Low-bandwidth PWA and service worker. | Unverified | Source/unit tests exist; no rendered 2G/offline browser evidence. | AUD-009, AUD-011 |
| ADR-012 | BFF auth, Keycloak, passkeys, server sessions. | Proven for public BFF; Unverified for staff session | Identity stripping is tested; staff access is intentionally disabled. | AUD-004, AUD-009 |
| ADR-013 | Python/FastAPI runtime selection. | Proven in source | FastAPI services and pinned main service bases exist; supported environment consistency is incomplete. | AUD-013 |
| ADR-014 | Future A2A boundary is disabled. | Proven | Gateway config has a2a enabled false. | — |
| ADR-015 | Supply-chain source controls and deferred artifact trust. | Partially proven | R1-A adds rolling cooldowns, immutable workflow policy, full-history scan, and a bounded exception record. Dockerfile tag remediation and signed image/model verification remain OQ-018 work. | AUD-006, AUD-007 |
| ADR-016 | Hardened Docker Compose operational standard. | Contradicted | General profile is hardened; GPU profile parity is absent. | AUD-005 |
| ADR-017 | Four-tier memory and durable goal continuation. | Contradicted | Preference, replay, and graph state are process-local or not restart-proven. | AUD-001, AUD-004 |
| ADR-018 | Preview-only staff console until trusted session. | Proven | Console behavior is guarded and documented as preview. | AUD-009 |
| ADR-019 | Fail-closed reference runtime mode. | Proven, with coverage gap | Default/unknown modes fail closed; empty/mixed-case matrix is not automated. | AUD-009 |
| ADR-020 | Node BFF runtime and deferred framework adoption. | Implemented in source | Both containers start their Node BFF entry points; stale Next configuration is removed and policy checks enforce the decision. | AUD-008 |
