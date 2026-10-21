# SSRA Assist — Operational Runbooks: Docker Compose Deployment, Incident Response, Rollback & DR (`docs/runbooks/README.md`)

**Status:** v2.0 (Docker Compose 2026 Standardization — Kubernetes Decommissioned)  
**Date:** 2026-10-17  
**References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 7, 11, 12.3, 12.5, 13, 15

> **2026 Containerization Standard:** All local, staging, production, and disaster-recovery (DR) operations standardize on **Docker Compose (`docker compose` v2.39+ / Compose Specification 2026)** using [`infra/compose/docker-compose.yml`](../../infra/compose/docker-compose.yml) and [`infra/compose/docker-compose.prod.yml`](../../infra/compose/docker-compose.prod.yml). Legacy Kubernetes deployment instructions are decommissioned across operational runbooks to eliminate multi-cluster control-plane overhead at the National Communication Authority (NCA) data centre while enforcing `read_only: true` root filesystems, `cap_drop: ["ALL"]`, `no-new-privileges:true`, `pids_limit`, and `sovereign_internal_net` (`internal: true`) network segmentation.

---

## 1. Developer, CI & Production Docker Compose Operations (`Taskfile.yml`)

| Command | Action |
|---|---|
| `task up` | Start local hardened Docker Compose stack (`infra/compose/docker-compose.yml`) and run end-to-end AG-UI smoke test (`tools/smoke_test_stack.py`) |
| `docker compose -f infra/compose/docker-compose.gpu.yml up -d --build --wait` | Start local sovereign GPU + local HF cache (`Sunflower-Qwen3.5-9B`, `Sunflower-Qwen3.8-27B`, `SunflowerASR`) + Qdrant + Valkey + PostgreSQL 18 + `ssra-frontend` (`:3033`) + `ssra-console` (`:3034`) stack (`127.0.0.1:18000` API, `127.0.0.1:18001` Runtime) and run `uv run python tools/run_20000_complex_ngrok_benchmark.py` |
| `task down` | Stop local Docker Compose stack cleanly (`--remove-orphans`) |
| `docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.prod.yml --profile prod up -d --wait` | Deploy production NCA Sovereign stack (including pre-built `keycloak` `--optimized` on port `8080`/`9000`, offline `vllm-sovereign` GPU container, and `postgres-wal-archiver`) |
| `task gen` | Regenerate Pydantic v2 models, TypeScript types, Zod 4 schemas, OpenAPI 3.1 client, and CycloneDX 1.6 SBOM + ML-BOM |
| `task lint` | Run Ruff check/format, `basedpyright` strict, `import-linter`, JSON Schema 2020-12 validator (33 MCP tools), `gitleaks`, Biome, and TypeScript `tsc` |
| `task test` | Run Python (`pytest` + Hypothesis, `>= 98%` coverage gate) and TypeScript (`vitest`) unit and contract test suites |
| `task eval` | Run the 600-item Phase 1 golden dataset (`300 en`, `150 ar`, `150 pga`) and OWASP Agentic `ASI01`–`ASI10` red-team suite |

---

## 2. Emergency Kill Switches (Model, Tool, Channel)

> **Staff console access gate (2026-10-21):** `apps/console` currently serves a non-operational preview. Its scorecard, feature-flag, kill-switch, and runtime-status browser APIs deliberately return `403 AUTHENTICATED_STAFF_SESSION_REQUIRED` until OQ-014 is resolved and server-verified staff authorization is implemented. Do not use the preview to inspect taxpayer work or issue operational commands. Follow the SSRA-approved incident procedure and authenticated control-plane access method for live interventions.

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
   curl -X POST http://127.0.0.1:8000/v1/knowledge-admin/snapshots/rollback
   ```
   Atomically restores the previous `PUBLISHED` snapshot version and marks the faulty release `ROLLED_BACK`.

---

## 4. Disaster Recovery (RPO ≤ 5 min, RTO ≤ 1 h) & Next.js 72-Hour Patching

- **PostgreSQL 18 PITR via Docker Compose (`postgres-wal-archiver`):** The `postgres-wal-archiver` service in `infra/compose/docker-compose.prod.yml` continuously ships WAL segments to S3-compatible storage (`s3://ssra-nca-backups/postgres18-wal`); quarterly restore drills verify recovery within RTO ≤ 1 h and RPO ≤ 5 min.
- **Scheduled Security Patching:** Subscribe to Next.js 16, FastAPI, Keycloak, and Linux kernel security advisories. Reviewed CVE patches bypass the 7-day dependency cooldown and must be deployed within 72 hours via `docker compose pull && docker compose up -d --wait`.
