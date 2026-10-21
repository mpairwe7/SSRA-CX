# SSRA Assist — AI Incident Playbook & Severity Matrix (`docs/runbooks/ai-incident-playbook.md`)

**Status:** v2.0 (Docker Compose 2026 Standardization)  
**Date:** 2026-10-17  
**References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 12.3, 12.5, 13, 16

---

## 1. AI & Security Incident Severity Matrix (`SEV-1` to `SEV-4`)

| Severity | Trigger Condition | Target Response / Containment SLA | Mandatory Immediate Action |
|---|---|---|---|
| **SEV-1 (Critical)** | Any cross-taxpayer PII/TIN leakage; any unverified payment account output; `audit_events` hash-chain integrity failure; active supply-chain compromise | **≤ 15 minutes** | 1. Use the separately approved SSRA incident procedure to isolate or stop affected services; the reference runtime's in-process `set_kill_switches(...)` and staff API are not production controls.<br>2. Revoke affected credentials through the approved identity/secret-management procedure.<br>3. Notify SSRA CISO/SecOps, Legal, and Commissioner General. |
| **SEV-2 (High)** | Repeated `numeric_provenance` guardrail triggers; suspected faulty `KnowledgeSnapshot`; upstream e-Tax adapter authentication failure | **≤ 30 minutes** | 1. Keep content publication and rollback on hold; `/v1/knowledge-admin/*` is disabled with 403 until OQ-014/OQ-015 are closed.<br>2. Open an authorized incident ticket and run `task eval` on the reference build. |
| **SEV-3 (Medium)** | Sovereign GPU container degradation (TTFT p95 > 1.5s); analytics drift status unavailable while OQ-013 is open | **≤ 2 hours** | 1. Use approved infrastructure/model telemetry for service health; `/v1/analytics/drift-monitors` is intentionally 503 and is not a live monitor.<br>2. Route low-confidence intents through the SSRA-approved staff process; the console preview is not an operational inbox. |
| **SEV-4 (Low)** | New content gap identified in `out_of_scope` / abstention logs; minor UI layout issue | **Next business day (`Africa/Juba`)** | 1. Log content gap for SSRA Policy/Legal team to author a new `KnowledgeSnapshot` draft. |

---

## 2. Change Advisory Review Checklist (Prompts, Models, Knowledge)

No change to `ai/prompts/`, `ai/policies/`, `ai/routing/`, or `knowledge/` may be promoted to production without:
1. Codeowners sign-off from SSRA Legal (for knowledge/`TaxFact` changes) and SSRA SecOps (for policy/routing changes);
2. Passing `task lint`, `task test`, and the full 600-item `task eval` + `ASI01`–`ASI10` red-team suite;
3. Verified recovery and rollback controls in the SSRA-approved operational system. Local feature-flag and snapshot workflow helpers are reference-only; their HTTP control routes return 403.
