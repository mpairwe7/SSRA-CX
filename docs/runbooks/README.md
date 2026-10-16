# SSRA Assist — Operational Runbooks: Incident Response, Rollback & DR (`docs/runbooks/README.md`)

**Status:** v1.1 (Phases 0–4 Reference Implementation)  
**Date:** 2026-10-16  
**References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 7, 11, 12.3, 12.5, 13, 15

---

## 1. Developer & CI Operations (`Taskfile.yml`)

| Command | Action |
|---|---|
| `task up` | Start local Docker Compose stack (`infra/compose/docker-compose.yml`) and run end-to-end AG-UI smoke test (`tools/smoke_test_stack.py`) |
| `task down` | Stop local Docker Compose stack cleanly |
| `task gen` | Regenerate Pydantic v2 models, TypeScript types, Zod 4 schemas, and OpenAPI 3.1 client (`services/api/openapi.json` → `@ssra/api-client`) |
| `task lint` | Run Ruff check/format, `basedpyright` strict, `import-linter`, JSON Schema 2020-12 validator (33 MCP tools), `gitleaks`, Biome, and TypeScript `tsc` |
| `task test` | Run Python (`pytest` + Hypothesis) and TypeScript (`vitest`) unit and contract test suites |
| `task eval` | Run the 600-item Phase 1 golden dataset (`300 en`, `150 ar`, `150 pga`) and OWASP Agentic `ASI01`–`ASI10` red-team suite |

---

## 2. Emergency Kill Switches (Model, Tool, Channel)

1. **Model Kill Switch / Force Degradation Ladder (`GET /v1/admin/kill-switches`):**
   - Setting `SSRA_FORCE_DEGRADATION_LEVEL=4` in `services/agent-runtime` bypasses LLM generation and serves **Retrieval-Only Cited Answer Cards + Deterministic Calculators** (Degradation Step 4).
   - Setting `SSRA_FORCE_DEGRADATION_LEVEL=5` serves **Static Approved FAQs + Callback Intake** (Degradation Step 5).
2. **Upstream T3 Feature Flags (`OQ-001`, `OQ-006`):**
   - `SSRA_ENABLE_UPSTREAM_T3_PAYMENT_REF=0` (default) keeps `payments-info.generate_payment_reference` disabled until SSRA Finance & ICT sign off on `OQ-006`.
   - `SSRA_ENABLE_UPSTREAM_T3_TCC=0` (default) keeps `tcc.request_tcc` disabled until SSRA Domestic Tax & ICT sign off on `OQ-001`.
3. **Per-Channel Kill Switch:**
   - Pause `whatsapp`, `sms`, `ussd`, or `voice` ingress in `services/channel-gateway` while keeping the public status banner active.

---

## 3. 6-Step Knowledge Release & One-Step Snapshot Rollback

Only immutable snapshots with `status = 'PUBLISHED'` are served to taxpayers:
1. Create draft: `POST /v1/knowledge-admin/snapshots`
2. Submit for legal review: `POST /v1/knowledge-admin/snapshots/{version}/submit-review`
3. Legal approval: `POST /v1/knowledge-admin/snapshots/{version}/approve`
4. Publish (with automated eval regression check): `POST /v1/knowledge-admin/snapshots/{version}/publish`
5. **Emergency 1-Step Rollback:**
   ```bash
   curl -X POST http://localhost:8000/v1/knowledge-admin/snapshots/rollback
   ```
   Atomically restores the previous `PUBLISHED` snapshot version and marks the faulty release `ROLLED_BACK`.

---

## 4. Disaster Recovery (RPO ≤ 5 min, RTO ≤ 1 h) & Next.js 72-Hour Patching

- **PostgreSQL 18 PITR:** CloudNativePG continuously archives WAL segments to S3-compatible storage; quarterly restore drills verify recovery within RTO ≤ 1 h and RPO ≤ 5 min.
- **Scheduled Security Patching:** Subscribe to Next.js 16, FastAPI, Keycloak, and Linux kernel security advisories. Reviewed CVE patches bypass the 7-day dependency cooldown and must be deployed within 72 hours.
