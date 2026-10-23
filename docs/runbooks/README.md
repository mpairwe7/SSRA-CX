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
| `docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.prod.yml --profile prod up -d --wait` | Validate/start the intended production/DR stack; API and runtime remain unready by design until approved providers and durable state are implemented |
| `task gen` | Regenerate Pydantic v2 models, TypeScript types, Zod 4 schemas, OpenAPI 3.1 client, CycloneDX 1.6 SBOM + ML-BOM, SLSA v1.0 provenance, and deterministic OASIS SARIF v2.1.0 security telemetry |
| `task lint` | Run Ruff check/format, `basedpyright` strict, `import-linter`, JSON Schema 2020-12 validator (33 MCP tools), supply-chain verifier, SAST/DAST/CI-model verifier, `gitleaks`, Biome, and TypeScript `tsc` |
| `task sec` | Run full DevSecOps SAST, Live In-Process ASGI DAST, Gitleaks, TruffleHog v3, Trivy (`fs` + `sbom`), Frontend SAST, and `pnpm audit`. See [DevSecOps SAST, DAST, Trivy, TruffleHog & CI/CD Modelling Pipeline](./devsecops-sast-dast-cicd-pipeline.md). |
| `task test` | Run Python (`pytest` + Hypothesis, `>= 98%` coverage gate), TypeScript (`vitest`) unit/contract suites, and the lock-pinned Playwright rendered-browser suite. See [Rendered Browser Flow Assurance](./browser-flow-assurance.md). |
| `task eval` | Run the 600-item reference golden dataset (`300 en`, `150 ar`, `150 pga`), OWASP Agentic `ASI01`–`ASI10` red-team suite, ASGI/DR drills, and a readiness audit that reports blockers without advancing Phase Exit Gates |

`SSRA_RUNTIME_MODE` defaults to `production`; API and agent-runtime requests fail closed until approved providers and durable stores are wired. Local Compose profiles explicitly select `reference` for synthetic development. See [Reference Mode and Readiness](./reference-mode-readiness.md). The production overlay selects `production` and is expected to remain unready until OQ-005 and OQ-013–OQ-017 have approved implementations.

The seven-day dependency cooldown and any narrowly bounded security-fix record are governed by [Dependency Security Exceptions](./dependency-security-exceptions.md). Dependabot applies the same holdback to version updates for pnpm, uv, and GitHub Actions; GitHub security updates are not delayed by that version-update control. The record does not replace the artifact and model trust decision required by OQ-018.

Taskfile JavaScript gates first check the bounded Node 24 engine declared in `package.json`, then invoke `pnpm` through Corepack and the exact `packageManager` pin. Node 25 and later need a separately reviewed Corepack provisioner or package-manager activation design before they can run these gates. All Taskfile pytest paths direct pytest to the local `/tmp` temporary root so shared mounted temp directories cannot break its owner checks. CI provides the same supported Node and pnpm versions before it invokes Taskfile.

---

## 2. Emergency Kill Switches (Model, Tool, Channel)

> **Staff console access gate (2026-10-21):** `apps/console` is a non-operational preview. Staff, admin, audit, kill-switch, feature-flag, and knowledge-release APIs return `403 NOT_AUTHORIZED` until OQ-014 is resolved and server-verified staff authorization is implemented. Do not use the preview or API to inspect taxpayer work or issue operational commands. Follow the SSRA-approved incident procedure and authenticated control-plane method for live interventions.

1. **Model Kill Switch / Force Degradation Ladder:**
   - No production HTTP or environment-variable kill switch is wired in this reference implementation. `SSRAConversationRuntime.set_kill_switches(...)` changes only that in-process runtime instance and is not a production control plane.
   - During an incident, use the separately approved SSRA infrastructure procedure to isolate or stop affected services, and record the action in the authorized incident system. Do not rely on a local reference-mode control.
2. **Upstream T3 Tools (`OQ-001`, `OQ-006`):** The documented environment-variable toggles are not wired as runtime controls. Do not use them to enable or disable tools; providers and controls remain subject to the relevant SSRA approvals.
3. **Per-Channel Kill Switch:** No operational channel-control API is available in this reference build. Use the separately approved infrastructure incident procedure to isolate channel services.

---

## 3. Reference Knowledge Release State Machine

The in-memory workflow engine supports unit tests for draft, legal review, approval, publication, and rollback state transitions. Its HTTP routes return `403 NOT_AUTHORIZED`; do not use them to publish or roll back content. OQ-014 and OQ-015 must be closed and the approved identity, maker-checker, durable audit, and snapshot storage integrations reviewed before any operational knowledge-release procedure is enabled.

---

## 4. Disaster Recovery (RPO ≤ 5 min, RTO ≤ 1 h) & Runtime Patching

- **PostgreSQL 18 PITR via Docker Compose (`postgres-wal-archiver`):** The production overlay describes the intended WAL archive topology; verify the configured backup target and restore evidence through approved infrastructure controls.
- **Scheduled Security Patching:** Subscribe to Node.js, FastAPI, Keycloak, and Linux kernel security advisories for the currently declared runtime. A future frontend framework requires its own reviewed runtime decision before it becomes a deployed dependency. A reviewed security fix that is younger than the cooldown must follow [Dependency Security Exceptions](./dependency-security-exceptions.md).
