# ADR-014: Future Agent-to-Agent (A2A v1.0) Interoperability Boundary

- **Status:** Proposed
- **Date:** 2026-10-16
- **Deciders:** Founding Principal Architect / Staff Engineer, SSRA Technical Lead
- **Reversal Cost:** Low
- **Linked Open Questions:** `OQ-001`, `OQ-005`
- **References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 2, 5, 8.5, Appendix A

---

## 1. Problem Statement

How do we reserve a governed, standards-compliant boundary for future multi-agency agent collaboration (such as South Sudan's National eServices single window) without expanding the MVP attack surface?

## 2. Context

SSRA participates in South Sudan's National eServices single window alongside the Ministry of Justice (business registration), Ministry of Humanitarian Services (NGO registration), civil registry, civil aviation, and trade/standards bodies. In the future, cross-agency workflows (e.g., verifying a business registration before TIN issuance) may use the **Agent-to-Agent (A2A) v1.0 protocol**, which introduces signed Agent Cards and multi-tenancy. However, Section 8.5 explicitly states that A2A is **not in the MVP**—only an ADR and a stub Agent Card should be produced now.

## 3. Options Considered

1. **Build Active A2A Endpoints in Phase 0/1:** Premature complexity and unneeded attack surface before National eServices exposes A2A peers.
2. **Reserve an A2A v1.0 Route & Policy Boundary in `agentgateway` + Commit a Disabled Stub Agent Card (Selected):** Prepares the architecture for A2A v1.0 behind the same single gateway without exposing any active A2A listener in MVP.

## 4. Decision

We adopt Option 2:

1. **Single Gateway Boundary:** All future inbound and outbound A2A v1.0 traffic must transit `agentgateway`, never directly to `services/agent-runtime`.
2. **Stub Agent Card (`infra/gateway/a2a-agent-card.stub.json`):**
   - Defines SSRA Assist's A2A v1.0 metadata (`protocolVersion: "1.0.0"`, `name: "ssra-assist"`, JWS signature placeholder, tenant scope `gov.ss.ssra`, and read-only public skills `verify_official_channel` and `tax_procedure_guidance`).
   - Marked `"enabled": false` in `infra/gateway/` until Phase 4+ and formal SSRA SecOps approval.
3. **Zero Trust for External Agents:** When enabled in a future phase, external government agents will be treated as untrusted inputs (`L4` data delimiters), authenticated via mTLS + JWS-signed Agent Cards, and restricted to `T0` or explicitly exchanged RFC 8693 scopes.

## 5. Consequences

- **Positive:** Satisfies Section 8.5 with zero runtime risk in Phase 0–3 while providing a clear integration contract for the National eServices technical working group.
- **Negative / Trade-offs:** None in MVP.

## 6. Reversal Cost & Migration Path

- **Reversal Cost:** Low (configuration-only stub).
