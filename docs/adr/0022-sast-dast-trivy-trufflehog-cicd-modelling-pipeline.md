# ADR-022: 6-Stage DevSecOps CI/CD Modelling Pipeline, Polyglot SAST, Live In-Process ASGI DAST, Trivy SCA/IaC/SBOM & Dual-Engine Secret Scanning

- **Status:** Accepted (repository safety baseline)
- **Date:** 2026-10-23
- **Deciders:** Founding Principal Architect / Staff Engineer, SSRA SecOps, SSRA QA & DevSecOps
- **Reversal Cost:** Low–Medium
- **Linked Open Questions:** `OQ-012`, `OQ-018`
- **References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 12.1–12.5, 15; [ADR-015](./0015-supply-chain-hardening-and-sovereign-gitops.md); [ADR-021](./0021-rendered-browser-assurance-and-synthetic-runtime.md)

---

## 1. Problem Statement

How do we model and enforce a high-assurance, fast, deterministic DevSecOps CI/CD pipeline covering SAST, DAST, Trivy SCA/IaC/Dockerfile/SBOM scanning, Frontend CSP/Trusted-Types/Browser security, and dual-engine Gitleaks + TruffleHog v3 secret scanning without exposing the pipeline to 2026-class scanner supply-chain compromises?

## 2. Context

In March 2026, attackers compromised 75 of 76 version tags in `aquasecurity/trivy-action`, `setup-trivy`, and the Trivy `v0.69.4` binary via a `pull_request_target` exploit. In October 2026, the GhostAction campaign injected malicious security-audit workflows to exfiltrate CI secrets. At the same time, a sovereign government revenue and agentic AI system requires continuous verification against OWASP ASVS 5.0 (L2/L3), OWASP Top 10 for Agentic Applications 2026 (`ASI01`–`ASI10`), OWASP MCP Top 10 (`MCP01`–`MCP10`), OWASP Top 10 CI/CD Security Risks (`CICD-SEC-01`–`CICD-SEC-10`), and NIST SP 800-218 v1.1 / v1.2 Draft (`PO.3`, `PW.4`, `PW.7`, `PW.8`, `RV.1`) + SP 800-218A.

## 3. Options Considered

1. **Third-Party Composite Scanner GitHub Actions + Heavy External JVM DAST Containers:** Vulnerable to mutable sub-action downloads, slow startup (5–10 minutes), and network flakiness. Rejected.
2. **Declarative 6-Stage CI/CD Security Model + SHA-256 Verified Scanner Binaries + Polyglot AST/Agentic SAST + Live In-Process ASGI DAST + OASIS SARIF v2.1.0 Telemetry (Selected):** Model the entire pipeline in `infra/security/cicd-pipeline-model.yaml`, verify external scanner archives (`Gitleaks v8.21.2`, `TruffleHog v3.88.15`, `Trivy v0.69.3`) by hardcoded SHA-256 digest before execution, run deterministic AST/Agentic/Frontend SAST and live in-process ASGI DAST (`DAST-01`–`DAST-08`), and enforce bidirectional parity between the model and `.github/workflows/ci.yml`.

## 4. Decision

We adopt Option 2:

1. **Declarative CI/CD Pipeline & Threat Modelling (`infra/security/cicd-pipeline-model.yaml`):**
   - Formally specify all 6 blocking CI stages (`workflow-security`, `secret-history`, `trivy-security`, `sast-dast`, `frontend-security`, `verify`), their minimal token scopes (`permissions: { contents: read }`), timeouts, pinned tool SHA-256 digests, and OWASP `CICD-SEC-01` through `CICD-SEC-10` controls.
   - Enforce bidirectional parity between `infra/security/cicd-pipeline-model.yaml` and `.github/workflows/ci.yml` in `tools/run_sast_dast_sec_pipeline.py` and `tools/verify_supply_chain_and_signatures.py`.
2. **Dual-Engine Secret Scanning (Gitleaks v8.21.2 + TruffleHog v3.88.15):**
   - Verify both release archives via `sha256sum --check` before extraction.
   - Run Gitleaks on the working tree (`gitleaks detect --no-git`) and full reachable Git history (`gitleaks detect --redact --log-opts="--all"`).
   - Run TruffleHog v3 with `--no-update` across full Git history in two passes: Pass 1 (`--results=verified --fail --no-update`) with zero exclusions, and Pass 2 (`--results=verified,unknown --exclude-detectors=JDBC --exclude-paths=.trufflehog-exclude-paths.txt --fail --no-update`).
3. **Supply-Chain Hardened Trivy Scanning (`Trivy v0.69.3`):**
   - Pin Trivy to the verified pre-compromise `v0.69.3` Linux archive (`sha256:1816b632dfe529869c740c0913e36bd1629cb7688bd5634f4a858c1d57c88b75`) and explicitly denylist the compromised March 2026 `v0.69.4` version and digest.
   - Scan `pnpm-lock.yaml` and `uv.lock` (including devDependencies, with `basic-ftp` pinned to `6.2.3` via `pnpm-workspace.yaml` `overrides` to remediate `CVE-2026-102990` / `GHSA-c475-qrg2-pj4r`), all 19 CIS-hardened non-root `Dockerfile`s, all OpenTofu modules (`infra/tofu`), and `infra/observability/cyclonedx-sbom.json`.
4. **Polyglot SAST & Live In-Process ASGI DAST (`tools/run_sast_dast_sec_pipeline.py`):**
   - **SAST:** Enforce Ruff Bandit (`S`) rules, strict `basedpyright`, `import-linter`, Python AST sink checks (`SAST-PY-01`–`05` including `T1`–`T3` MCP tool zero-TIN validation), and Frontend/BFF SAST (`SAST-FE-01`–`04` covering DOM-XSS, W3C Trusted Types, CSP Level 3 `strict-dynamic`, Service Worker `SSRA_LOGOUT_PURGE`, and fail-closed BFF boundaries).
   - **DAST:** Execute 8 live in-process ASGI attack suites (`DAST-01`–`08`) against `services/api`, `services/agent-runtime`, `services/channel-gateway`, and `agentgateway`, emitting deterministic OASIS SARIF v2.1.0 telemetry (`infra/observability/sast-dast-sarif-v2.1.0.json`).

## 5. Consequences

- **Positive:** Catches static, dynamic, secret, dependency, container, IaC, and workflow vulnerabilities in parallel CI jobs (< 3 minutes wall time) with zero mutable third-party scanner Actions.
- **Negative / Trade-offs:** Any change to `.github/workflows/ci.yml` stages or scanner versions requires updating `infra/security/cicd-pipeline-model.yaml` and regenerating `infra/observability/sast-dast-sarif-v2.1.0.json` via `task gen`.
- **Open limitation:** Production image/model signing and deployment-time verification remain governed by `OQ-018`.

## 6. Reversal Cost

- **Low–Medium:** All checks invoke portable `Taskfile.yml` targets (`task gen`, `task lint`, `task sec`, `task test`, `task eval`) and standard CLI binaries.
