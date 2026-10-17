# ADR-016: Docker Compose 2026 Standardization, `Sunbird/Sunflower-Qwen3.5-9B` Local HF Cache, and Omnichannel Workbench/Dashboards

- **Status:** Accepted
- **Date:** 2026-10-17
- **Deciders:** Founding Principal Architect / Staff Engineer, SSRA Technical Lead, SSRA SecOps
- **Reversal Cost:** Low–Medium
- **Linked Open Questions:** `OQ-003`, `OQ-004`, `OQ-008`
- **References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 6.4, 9, 11, 12.4, 13, 15

---

## 1. Problem Statement

How do we simplify sovereign container operations at the National Communication Authority (NCA) data centre without sacrificing zero-trust isolation, while running our African-multilingual LLM (`Sunbird/Sunflower-Qwen3.5-9B`) from the local HuggingFace cache (`/home/developer/huggingface_cache`) and providing unified Taxpayer Chat/Voice/Document workbenches and 3 Role-Based Dashboards (`ssra_staff`, `ssra_admin`, `ssra_auditor`)?

## 2. Context

1. **Containerization Simplification:** Operating multi-cluster Kubernetes (`kubectl`, `kustomize`, `CloudNativePG`, `Kyverno`) introduces unnecessary control-plane overhead for on-premise NCA sovereign hosts (`OQ-003`), whereas **Docker Compose (`docker compose` v2.39+ / Compose Specification 2026)** supports `read_only: true` root filesystems, `cap_drop: ["ALL"]`, `security_opt: ["no-new-privileges:true"]`, `pids_limit`, `sovereign_internal_net` (`internal: true`), NVIDIA GPU reservations, and continuous PostgreSQL 18 WAL shipping (`pg_receivewal --synchronous`).
2. **African-Multilingual Sovereign LLM:** The local HuggingFace cache (`/home/developer/huggingface_cache`) hosts **`Sunbird/Sunflower-Qwen3.5-9B`** (revision `c56081c5024b1c11186a69898f5f6a7a2dabe454`), purpose-trained for East African and South Sudanese multilingual workflows, alongside **`Qwen/Qwen3-8B`** as secondary fallback.
3. **Unified Taxpayer & Staff/Admin/Auditor Experience:** Taxpayers require a low-bandwidth `chatv2` workbench (word-boundary reveal queue, single-toggle voice mode, AI Call Receptionist with pre-call consent and `CallOrb`, G122 chat-to-call carryover, and Document/Screenshot Inspection Modal), while SSRA personnel require role-separated dashboards (`ssra_staff` -> `/agent` & `/calls`, `ssra_admin` -> `/admin`, `ssra_auditor` -> `/analytics` & `/admin/audit`) with HITL document uncertainty routing.

## 3. Options Considered

1. **Retain Kubernetes-First Runbooks and Generic `Qwen2.5-14B` Defaults:** Leaves operational runbooks coupled to `kubectl`/`CloudNativePG` and ignores the locally cached `Sunbird/Sunflower-Qwen3.5-9B` checkpoint.
2. **Standardize Runbooks on Hardened Docker Compose 2026 + `Sunbird/Sunflower-Qwen3.5-9B` Local HF Cache + Role-Separated Workbenches (Selected):** Decommissions Kubernetes in operational runbooks (`docs/runbooks/*.md`), binds `vLLM` and `ai/routing/model-routing.yaml` to `Sunbird/Sunflower-Qwen3.5-9B` (`c56081c5024b1c11186a69898f5f6a7a2dabe454`), and enforces CycloneDX 1.6 (`ECMA-424`) ML-BOM and living-documentation traceability in CI.

## 4. Decision

We adopt Option 2:

1. **Hardened Docker Compose 2026 & Non-Root OCI Containers (`infra/compose/docker-compose.yml`, `docker-compose.prod.yml`, `infra/policies/seccomp-sovereign-default.json`, `.dockerignore`):**
   - All operational runbooks (`docs/runbooks/README.md`, `dr-restore-drill.md`, `ai-incident-playbook.md`) standardize on Docker Compose (`--profile prod` and `--profile dr`), enforcing `sovereign_internal_net` (`internal: true`), `cap_drop: ["ALL"]`, `no-new-privileges:true`, `read_only: true`, non-root `USER 10001:10001` across all 4 `Dockerfile`s, `seccomp-sovereign-default.json`, `vllm-sovereign`, and `postgres-wal-archiver` (`pg_receivewal --synchronous`). Legacy `infra/k8s` and `infra/helm` directories have been removed.
2. **Sovereign Local HF Cache LLM (`Sunbird/Sunflower-Qwen3.5-9B`):**
   - `ai/routing/model-routing.yaml` and `libs/ssra_llm/src/ssra_llm/router.py` route `input_guard`, `understand`, and `compose` to `ssra-sovereign/sunflower-qwen3.5-9b` (`Sunbird/Sunflower-Qwen3.5-9B` @ `c56081c5024b1c11186a69898f5f6a7a2dabe454` in `/home/developer/huggingface_cache`), with `Qwen/Qwen3-8B` as Level 2 fallback.
3. **Chatv2, AI Call Receptionist, Document/Screenshot Analysis & 3 Role-Based Dashboards:**
   - Taxpayer Web PWA (`packages/chat-ui`) provides word-boundary reveal pacing (`reveal-queue.ts`), `chat-workbench.ts`, `call-receptionist.ts`, and `document-analysis.ts` (`POST /v1/identity-link/documents/analyze` with HITL uncertainty routing).
   - Staff Console (`apps/console`) provides role-separated dashboards (`ssra_staff`, `ssra_admin`, `ssra_auditor`), `CallConsoleBar`, 4-section Call Desk queue, and WORM Audit Trail Merkle seal inspection.

## 5. Consequences

- **Positive:** Zero Kubernetes control-plane overhead on NCA hosts, full offline reproducibility from `/home/developer/huggingface_cache`, and automated CI verification of living docs, ADRs, runbooks, and CycloneDX 1.6 ML-BOM (`tools/verify_supply_chain_and_signatures.py`).
- **Negative / Trade-offs:** Host-level multi-node scheduling is managed via Compose profiles and load-balanced NCA reverse proxies rather than Kubernetes controllers.

## 6. Reversal Cost & Migration Path

- **Reversal Cost:** Low–Medium. Container images, `ModelPort` contracts, and stateless MCP `2026-07-28` services remain 100% OCI-standard.
