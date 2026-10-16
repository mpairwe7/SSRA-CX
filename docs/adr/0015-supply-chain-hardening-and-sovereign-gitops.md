# ADR-015: Supply-Chain Hardening (SLSA Level 3, 7-Day Cooldown) and Sovereign GitOps Delivery

- **Status:** Proposed
- **Date:** 2026-10-16
- **Deciders:** Founding Principal Architect / Staff Engineer, SSRA SecOps, SSRA ICT
- **Reversal Cost:** Medium
- **Linked Open Questions:** `OQ-003`, `OQ-012`
- **References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 12.1, 12.4, 15, 19

---

## 1. Problem Statement

How do we defend SSRA Assist's CI/CD pipeline, dependencies, AI gateways, and NCA Kubernetes cluster against 2026-class software supply-chain compromises (such as the March 2026 LiteLLM/Trivy CI credential-theft attack)?

## 2. Context

In March 2026, attackers compromised a mutable CI scanner reference in LiteLLM's build pipeline, exfiltrated its publishing credentials, and pushed malicious credential-stealing releases to PyPI. Government revenue platforms and AI gateways are high-value targets for nation-state and criminal supply-chain attacks. Any dependency update pulled immediately upon publication or any unpinned GitHub Action / container image tag creates an unacceptable compromise vector.

## 3. Options Considered

1. **Standard Floating Semver Ranges (`^` / `~`) + Tag-Pinned CI Actions (`@v4`) + Direct Pulls from Public Registries:** Vulnerable to typosquatting, compromised maintainer tokens, and mutable Git tags. Rejected.
2. **7-Day Dependency Cooldown + Hash-Pinned Lockfiles + SHA-Pinned CI Actions + Internal Registry Mirror + CycloneDX SBOM + Cosign Signing + Kyverno Admission Verification + Argo CD GitOps (Selected):** Defence-in-depth aligned with SLSA v1 Build Level 3 and NIST SSDF (SP 800-218 / 218A).

## 4. Decision

We adopt Option 2 and enforce it in repository configuration and CI:

1. **Mandatory 7-Day Dependency Cooldown:**
   - Configure `minimumReleaseAge: 10080` (7 days in minutes) in `pnpm-workspace.yaml`.
   - Configure `exclude-newer = "2026-10-09T23:59:59Z"` (rolling ≥7 days before check date) in root `pyproject.toml` (`[tool.uv]`).
   - Only reviewed security advisories (CVEs) documented in `docs/PROGRESS.md` may bypass the cooldown via explicit allow-list.
2. **Exact Version & Cryptographic Hash Pinning:**
   - Commit hash-locked `pnpm-lock.yaml` and `uv.lock`; CI runs `pnpm install --frozen-lockfile` and `uv sync --locked`.
   - Pin every GitHub Action and CI tool by full 40-character commit SHA (never mutable `@vX` tags).
3. **Artifact Provenance, SBOM & Admission Control:**
   - Generate a CycloneDX SBOM for every container image and scan with digest-pinned vulnerability/SAST/secret scanners (`Semgrep`, `gitleaks`).
   - Sign container images and model/knowledge manifests with **Cosign**; enforce signature and SBOM attestation verification at Kubernetes admission using **Kyverno** (`infra/policies/kyverno/`).
4. **Portable CI & Sovereign GitOps Delivery:**
   - Keep CI pipeline logic in `Taskfile.yml` so `.github/workflows/ci.yml` is a thin wrapper portable to self-hosted GitLab CI or Forgejo inside NCA (`OQ-003`).
   - Deploy exclusively via **Argo CD** with **Argo Rollouts** progressive canary analysis gated on SLO burn rates and eval regression metrics.

## 5. Consequences

- **Positive:** Blocks zero-day malicious package publications (like the LiteLLM incident) before they can enter developer workstations or CI, and guarantees only signed, audited artifacts run in NCA Kubernetes.
- **Negative / Trade-offs:** Routine dependency upgrades via Renovate wait at least 7 days after upstream release and are reviewed in small, grouped PRs.

## 6. Reversal Cost & Migration Path

- **Reversal Cost:** Medium. Because all CI steps invoke `task <target>`, migrating between GitHub Actions, GitLab CI, or Forgejo requires changing only the thin pipeline YAML wrapper.
