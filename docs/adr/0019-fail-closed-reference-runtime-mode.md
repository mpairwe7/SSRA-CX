# ADR-019: Fail-Closed Reference Runtime Mode

- **Status:** Accepted as a repository safety baseline; not production authorization
- **Date:** 2026-10-21
- **Deciders:** SSRA Assist engineering maintainers
- **Reversal Cost:** Medium
- **References:** [OQ-005](../open-questions.md), [OQ-013](../open-questions.md), [OQ-014](../open-questions.md), [OQ-015](../open-questions.md), [OQ-016](../open-questions.md), [OQ-017](../open-questions.md), [Reference Mode and Readiness](../runbooks/reference-mode-readiness.md)

## Context

The Core API and agent runtime contain process-local repositories and LangGraph `InMemorySaver`. Several routes and attachment helpers also returned synthetic identity, document-scan, OCR, portal-instruction, tax-calculation, appointment, or analytics results. These behaviors did not establish identity, malware scanning, current inventory, trusted measurements, durable state, or delivery.

Production deployment requires SSRA decisions and verified implementations for identity, analytics, persistence, appointments, and document processing. Existing Compose files and schema declarations do not prove those integrations are active. The Phase Exit Gates remain open.

## Decision

1. `SSRA_RUNTIME_MODE` defaults to `production`. Missing or unrecognized values fail closed.
2. Core API and agent-runtime return RFC 9457 `503 UPSTREAM_UNAVAILABLE`, including health checks, unless the process is explicitly configured as `reference`.
3. Only local and test Compose profiles select `reference`; responses carry `X-SSRA-Runtime-Mode: reference`.
4. Identity verification, document scanning/analysis, appointment availability, and operational analytics return 503 in both modes until their specific approved providers and provenance controls exist.
5. Identity-link application/domain fixtures and generated attachment-analysis prompts are removed. The attachment view reports analysis unavailable and does not assume a portal URL, tax rule, deadline, or verified identity.
6. Staff inbox, copilot, takeover/handback, QA, maker-checker, knowledge-release, admin, and JIT API routes return 403 until a server-verified staff-session and role provider exists. Public status returns 503 until trusted monitoring is configured.
7. The in-process event buffer is named `InMemoryOutboxBuffer`; it never marks an event as published, never evicts old staged events, and refuses JetStream flush without a publisher.
8. No external dependency or production integration is introduced by this decision. Durable persistence, RLS/session binding, backup/restore proof, broker delivery, staff identity, and external-provider approvals remain open work.

## Consequences

- Production and DR API/runtime health checks remain unavailable until the listed implementations and readiness evidence are complete. This intentionally prevents the reference implementation from presenting itself as an operational government service.
- Local reference flows remain available where the underlying endpoint is not itself blocked for lack of an authoritative provider.
- Historical feature-completion notes describe reference code only; they do not authorize production use or close a Phase Gate.
- A future production-enablement change requires the relevant SSRA-approved ADR/OQ decisions, implemented integrations, and verification evidence. Changing the environment variable alone is not an acceptance test.

## Verification

Unit and API tests cover the production-default and invalid-mode 503 responses, provider-specific fail-closed endpoints, explicit reference-mode labeling, unavailable attachment-analysis state, denied staff routes, untrusted staff-ID rejection, and outbox non-publication/overflow behavior.
