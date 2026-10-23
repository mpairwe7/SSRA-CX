# DevSecOps SAST, DAST, Trivy, TruffleHog & CI/CD Modelling Pipeline Runbook

**Status:** Active repository assurance procedure  
**Date:** 2026-10-23  
**Related:** [ADR-015](../adr/0015-supply-chain-hardening-and-sovereign-gitops.md), [ADR-021](../adr/0021-rendered-browser-assurance-and-synthetic-runtime.md), [ADR-022](../adr/0022-sast-dast-trivy-trufflehog-cicd-modelling-pipeline.md), [`infra/security/cicd-pipeline-model.yaml`](../../infra/security/cicd-pipeline-model.yaml)

## Purpose

Execute and verify the 6-stage DevSecOps CI/CD security pipeline locally and in CI across:

1. **CI/CD Workflow & Pipeline Modelling (`workflow-security`):** `zizmor v1.30.1` online workflow audit + declarative DAG parity against `infra/security/cicd-pipeline-model.yaml` and OWASP `CICD-SEC-01`..`CICD-SEC-10`.
2. **Dual-Engine Secret Scanning (`secret-history`):** SHA-256 verified **Gitleaks v8.21.2** (`5bc41815076e6ed6ef8fbecc9d9b75bcae31f39029ceb55da08086315316e3ba`) + SHA-256 verified **TruffleHog v3.88.15** (`ed6d5c585f1e589c192c450369afb029050f76fe16e86a0cf58ee0658a67f86d`) scanning full reachable Git history (`--no-update`).
3. **Hardened Trivy SCA, Container, IaC & SBOM Scanning (`trivy-security`):** SHA-256 verified pre-compromise **Trivy v0.69.3** (`1816b632dfe529869c740c0913e36bd1629cb7688bd5634f4a858c1d57c88b75`; explicitly denylisting the March 2026 compromised `v0.69.4` binary) scanning `pnpm-lock.yaml`, `uv.lock`, all 19 non-root `Dockerfile`s, `infra/tofu` OpenTofu modules, and `infra/observability/cyclonedx-sbom.json`.
4. **Polyglot SAST & Live In-Process ASGI + Node BFF DAST (`sast-dast`):** Ruff Bandit (`S`) rules, strict `basedpyright`, `import-linter`, import-aware Python AST security & Agentic MCP tool schema SAST (`SAST-PY-01`..`05`), Frontend/BFF SAST (`SAST-FE-01`..`05`), and 10 live ASGI & Node BFF DAST probe suites (`DAST-01`..`10`), emitting deterministic OASIS SARIF v2.1.0 Errata 01 telemetry (`infra/observability/sast-dast-sarif-v2.1.0.json`).
5. **Frontend Security, Accessibility & Rendered Browser Assurance (`frontend-security`):** `corepack pnpm audit --audit-level=high`, Biome lint, TypeScript `tsc`, `tools/verify_frontend_budgets_and_a11y.py`, and Playwright Chromium rendered-browser tests.
6. **Canonical Polyglot Verification (`verify`):** `task gen`, `git diff --exit-code`, `task lint`, `task test`, and `task eval`.

## Local Execution Commands

| Command | Scope |
|---|---|
| `task gen` | Regenerate contracts, OpenAPI, corpus manifest, CycloneDX 1.6 SBOM/ML-BOM, SLSA v1.0 provenance, and deterministic SARIF v2.1.0 (`infra/observability/sast-dast-sarif-v2.1.0.json`) |
| `task sec` | Run the full local SAST, Live ASGI DAST, Gitleaks, TruffleHog v3, Trivy (`fs` + `sbom`), Frontend SAST, and `pnpm audit` pipeline |
| `uv run python tools/run_sast_dast_sec_pipeline.py --ci-sast-dast` | Run CI/CD pipeline model verification, Python/Agentic SAST, Frontend SAST, Live ASGI DAST, and SARIF parity check |
| `task lint` | Run all static analyzers, supply-chain verifier, SAST/DAST/model verifier, Gitleaks working-tree scan, Biome, and TypeScript `tsc` |

## Triage and Maintenance Rules

1. **Never weaken a scanner or add a mutable tag:** Every scanner archive URL and SHA-256 digest in `.github/workflows/ci.yml` must match `infra/security/cicd-pipeline-model.yaml` and `tools/verify_supply_chain_and_signatures.py`.
2. **Adding or modifying a CI job:** Update both `.github/workflows/ci.yml` and `infra/security/cicd-pipeline-model.yaml` in the same commit, then run `task gen && task lint`.
3. **TruffleHog secondary pass exclusions (`.trufflehog-exclude-paths.txt`):** Pass 1 (`--results=verified`) runs with zero exclusions. Pass 2 (`--results=verified,unknown`) excludes only synthetic test fixtures with unresolvable placeholder hostnames and requires `@ssra-org/secops` `CODEOWNERS` review for any modification.
