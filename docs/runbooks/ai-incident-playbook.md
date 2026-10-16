# SSRA Assist — AI Incident Playbook & Severity Matrix (`docs/runbooks/ai-incident-playbook.md`)

**Status:** v1.0  
**Date:** 2026-10-16  
**References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 12.3, 12.5, 13, 16

---

## 1. AI & Security Incident Severity Matrix (`SEV-1` to `SEV-4`)

| Severity | Trigger Condition | Target Response / Containment SLA | Mandatory Immediate Action |
|---|---|---|---|
| **SEV-1 (Critical)** | Any cross-taxpayer PII/TIN leakage; any unverified payment account output; `audit_events` hash-chain integrity failure; active supply-chain compromise | **≤ 15 minutes** | 1. Set `degradation_level = 5` (`POST /v1/admin/kill-switches`) or disable affected tool/channel.<br>2. Isolate affected pod/credential via OpenBao & Keycloak.<br>3. Notify SSRA CISO/SecOps, Legal, and Commissioner General. |
| **SEV-2 (High)** | Repeated `numeric_provenance` guardrail triggers; faulty `KnowledgeSnapshot` published; upstream e-Tax adapter authentication failure | **≤ 30 minutes** | 1. Execute 1-step snapshot rollback (`POST /v1/knowledge-admin/snapshots/rollback`) or set `degradation_level = 4` (Retrieval-Only Cards).<br>2. Open incident ticket and run `task eval`. |
| **SEV-3 (Medium)** | Sovereign GPU replica degradation (TTFT p95 > 1.5s); Tier B language parity drift alert (`GET /v1/analytics/drift-monitors`) | **≤ 2 hours** | 1. Fail over to secondary model (`degradation_level = 2` or `3`).<br>2. Route low-confidence intents to Staff Console inbox. |
| **SEV-4 (Low)** | New content gap identified in `out_of_scope` / abstention logs; minor UI layout issue | **Next business day (`Africa/Juba`)** | 1. Log content gap for SSRA Policy/Legal team to author a new `KnowledgeSnapshot` draft. |

---

## 2. Change Advisory Review Checklist (Prompts, Models, Knowledge)

No change to `ai/prompts/`, `ai/policies/`, `ai/routing/`, or `knowledge/` may be promoted to production without:
1. Codeowners sign-off from SSRA Legal (for knowledge/`TaxFact` changes) and SSRA SecOps (for policy/routing changes);
2. Passing `task lint`, `task test`, and the full 600-item `task eval` + `ASI01`–`ASI10` red-team suite;
3. Verified 1-step rollback target (`previous_published_version`).
