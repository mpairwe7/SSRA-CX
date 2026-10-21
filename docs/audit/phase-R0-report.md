# Phase R0 Report — Baseline and Triage

**Status:** Complete evidence collection; Gate R0 not approved.

**Baseline commit:** 7ca1f26e83b08decf64eacf02af059b537e69db7

**No remediation performed:** This phase changed documentation only. It did not alter code, CI, secrets, policy, risk tiers, branch protection, deployments, or production data.

## Gate result

| Gate condition | Result |
|---|---|
| Baseline and evidence pack recorded | Met |
| Findings register created with reproducible location, evidence, impact, fix, verification, phase, owner, and status | Met |
| Architecture and ADR claims assessed | Met |
| Standards checked against primary sources | Met |
| S0 incident owner assigned | Not applicable: no S0 was found |
| SSRA technical-lead approval | Pending |

## Material result

R0 found three S1 blockers:

1. Conversation and confirmation state is process-local.
2. The GPU profile bypasses the governed egress architecture.
3. The API has no transactional outbox or durable event delivery.

Nine S2 items and one S3 reproducibility item are recorded in the findings register. The current fail-closed production behavior reduces immediate external exposure but does not close the structural gaps.

## Prioritized remediation backlog

| Phase | Findings | Work item | Owner | Estimated PR size |
|---|---|---|---|---|
| R1 | AUD-006 | Add workflow ownership, full-history/PR secret scanning, zizmor, and negative CI fixtures. | DevSecOps | 2 PRs, each under 400 changed lines |
| R1 | AUD-007 | Pin every base image, define dependency exception governance, add SBOM/signature/provenance verification. | DevSecOps and Platform | 3 PRs |
| R1 | AUD-008 | Make the frontend runtime decision explicit and enforce the selected dependency posture. | Frontend | 1 PR |
| R2 | AUD-009 | Add browser tests for chat, rail/sidebar, and dashboard flows; route matrix, API fuzzing, mutation, and flake gate. | QA and Frontend | 3–4 PRs |
| R2 | AUD-011 | Replace hand-maintained offline statutory values with a generated, signed, expiring snapshot. | Frontend, Tax Facts, Legal | 2 PRs |
| R2 | AUD-013 | Provide reproducible graph/profile/toolchain preflight. | Developer Experience | 1 PR |
| R3 | AUD-001 | Add durable checkpointer and restart/resume proof. | Agent Runtime | 2 PRs |
| R3 | AUD-003 | Implement transactional outbox with idempotent durable consumers. | Core API and Platform | 2–3 PRs |
| R3 | AUD-004 | Persist consent and subject-scoped state behind verified identity and RLS. | Core API and Identity | 2 PRs |
| R3 | AUD-002, AUD-010 | Make GPU egress and all MCP services deployable and testable through the gateway. | Platform and MCP Engineering | 2–3 PRs |
| R4 | AUD-005 | Apply platform hardening and secret handling consistently to every profile. | Platform Security | 2 PRs |
| R4 | AUD-012 | Prove full-path telemetry, load, chaos, and recovery behavior. | SRE and Security Observability | 2 PRs |
| R5 | All | Schedule independent rechecks, release evidence packs, and a monthly standards delta. | QA and DevSecOps | 2 PRs plus operating procedure |

## Decisions required before R1–R5

1. The SSRA technical lead must approve the severity and phase assignment of this R0 register.
2. OQ-015 owners must choose the authoritative PostgreSQL, checkpoint, outbox, RLS, retention, and recovery design before R3 implementation.
3. OQ-018 owners must approve the artifact registry, signing identity, trust roots, and deployment verification mechanism before R1/R4 supply-chain work.
4. OQ-019 owners must approve the lifecycle and expiry model for any offline statutory snapshot before AUD-011 remediation.

## Exit statement

Gate R0 remains blocked pending explicit technical-lead approval. No later phase should start from this branch until that approval is recorded.
