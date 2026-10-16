---
name: living-docs-adr-runbooks-traceability
description: Mandatory October 2026 Living Documentation, ADR (MADR 4.0), Runbook, Model Card, and CycloneDX 1.6 ML-BOM traceability workflow (ISO/IEC 42001 Clause 7.5 & NIST AI RMF GOVERN 1.4). Trigger on EVERY code, config, model, knowledge, UI, or infrastructure change so docs/PROGRESS.md, docs/adr/, docs/runbooks/, docs/ai-governance/, docs/security/, and AGENTS.md never drift.
---

# Living Docs, ADRs & Runbooks Traceability Skill (October 2026 Standard)

Aligned with **ISO/IEC 42001:2023 Clause 7.5 (Documented Information)**, **NIST AI 600-1 (`GOVERN 1.4` & `MAP 4.2`)**, **MADR 4.0**, and **CycloneDX v1.6 (`ECMA-424`)**, every code, configuration, model, knowledge-base, UI/UX, or infrastructure change **must** update all affected documentation artifacts in the **same commit and Pull Request**.

---

## 1. Mandatory Same-PR Traceability Matrix

Whenever you modify any file in the repository, check and update the corresponding living documentation artifacts before committing:

| Change Category | Source Files Touched | Mandatory Documentation & Traceability Updates (Same PR) |
|---|---|---|
| **Architecture, Stack, Protocols, or Containerization** | `services/*`, `libs/*`, `mcp-servers/*`, `infra/compose/*` | 1. Author a new ADR (`docs/adr/00XX-*.md`) or update the superseded ADR.<br>2. Register the ADR in `docs/adr/README.md`.<br>3. Update `docs/architecture/overview.md` and `docs/PROGRESS.md`. |
| **AI Models, Routing, Prompts, Voice, or Corpus** | `ai/routing/model-routing.yaml`, `ai/prompts/*`, `knowledge/*`, `services/voice/*` | 1. Run `task gen` to regenerate `infra/observability/cyclonedx-sbom.json` (CycloneDX 1.6 ML-BOM + Data-BOM) and `knowledge/snapshot-manifest-2026.10.1.json`.<br>2. Update `docs/ai-governance/model-cards-and-datasheet.md`.<br>3. Update `docs/PROGRESS.md` and relevant ADR (`ADR-007` / `ADR-016`). |
| **Operations, Deployment, DR, Kill Switches, or Env Vars** | `infra/compose/*`, `Taskfile.yml`, `services/api/src/ssra_api/admin/*` | 1. Update `docs/runbooks/README.md`, `docs/runbooks/dr-restore-drill.md`, and `docs/runbooks/ai-incident-playbook.md`.<br>2. Verify zero decommissioned commands (`kubectl`, `kustomize`, `infra/k8s`, `CloudNativePG`) appear in `docs/runbooks/*.md`. |
| **Security, Auth, Privacy, Guardrails, or Supply Chain** | `libs/ssra_security/*`, `services/agent-runtime/src/ssra_runtime/guardrails/*`, `pyproject.toml`, `pnpm-workspace.yaml` | 1. Update `docs/security/threat-model.md` and `docs/security/controls-and-pentest-matrix.md`.<br>2. Record package/CVE verification dates in `docs/PROGRESS.md`. |
| **Open Questions or Upstream Port Assumptions** | `libs/ssra_adapters/*`, `mcp-servers/*` | 1. Log or update `OQ-###` in `docs/open-questions.md` with owner and safe runtime fallback. |
| **API Contracts, Schemas, or Frontend Dashboards** | `packages/contracts/*`, `services/api/*`, `apps/web/*`, `apps/console/*` | 1. Run `task gen` to synchronize `services/api/openapi.json` and `packages/api-client/src/index.ts`.<br>2. Update `docs/PROGRESS.md`. |

---

## 2. Verification Protocol Before Opening or Merging Any PR

1. **Regenerate Derived Artifacts (`task gen`)**:
   - Ensures `packages/contracts`, `services/api/openapi.json`, `packages/api-client`, `infra/observability/cyclonedx-sbom.json`, and `knowledge/snapshot-manifest-2026.10.1.json` are 100% in sync with source definitions.
2. **Grep for Stale Identifiers**:
   - Run `grep -rn "<old-model-or-command-or-path>" docs/ AGENTS.md` and update any stale reference.
3. **Run Automated Traceability & Quality Gates**:
   - Execute `task lint && task test && task eval` (which runs `tools/verify_supply_chain_and_signatures.py` to verify ADR catalog completeness, model-card parity, CycloneDX 1.6 ML-BOM parity, and runbook hygiene).
