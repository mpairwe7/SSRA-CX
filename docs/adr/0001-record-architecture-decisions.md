# ADR-001: Record Architecture Decisions

- **Status:** Proposed
- **Date:** 2026-10-16
- **Deciders:** Founding Principal Architect / Staff Engineer, SSRA Technical Lead, SSRA SecOps & Legal (where applicable)
- **Reversal Cost:** Low
- **References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 1, 4, 16, 18, 19

---

## 1. Problem Statement

How do we govern, document, and evaluate the reversal cost of architectural decisions across SSRA Assist so that a local SSRA engineering team can operate, audit, and evolve the platform safely without institutional knowledge loss or silent drift from the master specification?

## 2. Context

SSRA Assist is a sovereign, high-stakes government revenue CX platform. Architectural choices regarding model routing, risk tiers (`T0`–`T4`), authentication, data residency at the National Communication Authority (NCA), and tool protocols have direct legal, security, and operational consequences. Furthermore, the platform must be maintainable long-term by SSRA's in-country ICT team. Silent deviations from [`docs/00-master-prompt.md`](../00-master-prompt.md) or undocumented technology trade-offs create operational fragility and audit failures.

## 3. Options Considered

1. **Ad-hoc documentation in PR descriptions or wiki pages:** Fast initially, but drifts from code, lacks version control alongside code changes, and fails auditability requirements.
2. **In-repo Markdown Architecture Decision Records (`docs/adr/NNNN-slug.md`) with mandatory Reversal Cost & Gate Review (Selected):** Version-controlled in Git, reviewed in the same pull request as architectural or policy changes, and explicitly tied to phase exit gates and `docs/open-questions.md`.
3. **Heavyweight external Architecture Review Board ticketing system:** Disconnected from the repository and inaccessible in offline or air-gapped NCA environments.

## 4. Decision

We will record every architectural decision that has a non-trivial reversal cost—or that resolves an open question (`OQ-###`) or proposes an improvement to [`docs/00-master-prompt.md`](../00-master-prompt.md)—as a sequentially numbered Markdown file in `docs/adr/NNNN-kebab-case-title.md`.

Every ADR must contain the following sections:
1. **Metadata Header:** Status (`Proposed` | `Accepted` | `Superseded by ADR-XXXX` | `Deprecated`), Date, Deciders, Reversal Cost (`Low` | `Medium` | `High`), and linked Open Questions (`OQ-###`).
2. **Problem Statement:** A concise one-line question answered by the ADR.
3. **Context:** Technical, legal, security, and South Sudan operational constraints (low bandwidth, NCA sovereignty, multilingual support).
4. **Options Considered:** At least two viable options with honest pros and cons.
5. **Decision:** The chosen approach and specific implementation rules or enforcement mechanisms (e.g., `import-linter`, OPA policies, CI checks).
6. **Consequences:** Positive outcomes, trade-offs/costs, and risk mitigations.
7. **Reversal Cost & Migration Path:** Concrete steps required to reverse or replace the decision later.

**Governance rules:**
- No change to `ai/policies/risk-tiers.yaml`, security/privacy controls, or repository layout may merge without an SSRA-approved ADR.
- When an ADR supersedes an earlier one, the original file is kept immutable except for updating its `Status` to `Superseded by ADR-XXXX`.

## 5. Consequences

- **Positive:** Complete, auditable history of why every technology and boundary was chosen; local SSRA engineers inherit clear rationale and migration paths.
- **Negative / Trade-offs:** Adds upfront writing and review discipline before scaffolding or changing major components.

## 6. Reversal Cost & Migration Path

- **Reversal Cost:** Low. Markdown files in `docs/adr/` are plain text and can be migrated to any documentation portal or compliance repository without tooling lock-in.
