# ADR-015: Supply-Chain Hardening, 7-Day Cooldown, and Deferred Artifact Trust

- **Status:** Accepted as a repository safety baseline; deployment artifact trust deferred to OQ-018
- **Date:** 2026-10-16
- **Deciders:** Founding Principal Architect / Staff Engineer, SSRA SecOps, SSRA ICT
- **Reversal Cost:** Medium
- **Linked Open Questions:** `OQ-003`, `OQ-012`, `OQ-018`
- **References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 12.1, 12.4, 15, 19

---

## 1. Problem Statement

How do we defend SSRA Assist's CI/CD pipeline, dependencies, and runtime artifacts against software supply-chain compromise while leaving production artifact trust decisions to SSRA?

## 2. Context

In March 2026, attackers compromised a mutable CI scanner reference in LiteLLM's build pipeline, exfiltrated its publishing credentials, and pushed malicious credential-stealing releases to PyPI. Government revenue platforms and AI gateways are high-value targets for nation-state and criminal supply-chain attacks. Any dependency update pulled immediately upon publication or any unpinned GitHub Action / container image tag creates an unacceptable compromise vector.

## 3. Options Considered

1. **Standard Floating Semver Ranges (`^` / `~`) + Tag-Pinned CI Actions (`@v4`) + Direct Pulls from Public Registries:** Vulnerable to typosquatting, compromised maintainer tokens, and mutable Git tags. Rejected.
2. **Rolling cooldown + immutable CI actions + lockfiles + explicit deferred artifact trust (Selected):** Enforce the controls the repository can verify today, and keep registry, signing, and pre-run verification decisions open until SSRA approves OQ-018.

## 4. Decision

We adopt Option 2 as a repository safety baseline:

1. **Mandatory 7-Day Dependency Cooldown:**
   - Configure `minimumReleaseAge: 10080` (7 days in minutes), `trustPolicy: no-downgrade`, `blockExoticSubdeps: true`, and an empty `allowBuilds` review allow-list in `pnpm-workspace.yaml`.
   - Configure `exclude-newer = "1 week"` and an exact `uv` version in root `pyproject.toml`; preserve the rolling span in `uv.lock`.
   - Configure Dependabot for the `npm` (pnpm), `uv`, and `github-actions` ecosystems with `cooldown.default-days: 7`; version-update cooldowns do not defer security updates.
   - Record a security-fix exception in [`docs/runbooks/dependency-security-exceptions.md`](../runbooks/dependency-security-exceptions.md) with an advisory, exact artifact checksum, bounded scope, and expiry. Do not add a broad cooldown exclusion.
2. **Exact Version & Cryptographic Hash Pinning:**
   - Commit hash-locked `pnpm-lock.yaml` and `uv.lock`; CI runs `pnpm install --frozen-lockfile` and `uv sync --locked`. Until a reviewed package-manager provisioner is introduced, Taskfile JavaScript gates require the bounded Node 24 Corepack-compatible engine and then invoke the exact `packageManager` pin through Corepack.
   - Pin every GitHub Action by full 40-character commit SHA, deny workflow token scopes by default, and declare only job-level scopes needed by each CI job.
   - Reject `pull_request_target`, require checkout without persisted credentials, run a full-reachable-history Gitleaks gate, and run the pinned zizmor workflow audit.
3. **Artifact Provenance and SBOM:**
   - Generate the existing CycloneDX SBOM and provenance evidence as repository artifacts, while treating them as evidence targets rather than verified production attestations.
   - Do not claim image, model, or knowledge-manifest signing; do not select a registry, trust root, or pre-run verification point until OQ-018 is decided.
4. **Portable CI:**
   - Keep CI pipeline logic in `Taskfile.yml` so `.github/workflows/ci.yml` remains a thin wrapper that can be reviewed and ported to an SSRA-approved runner environment.

## 5. Consequences

- **Positive:** Reduces exposure to newly published dependency compromises, mutable workflow actions, workflow token overreach, and reachable-history secrets before code can merge.
- **Negative / Trade-offs:** Routine dependency upgrades via Dependabot wait at least 7 days after upstream release and are reviewed in small PRs.
- **Open limitation:** This repository control does not prove that a production image, model, or deployment artifact is signed or verified. OQ-018 remains a release blocker for that claim.

## 6. Reversal Cost & Migration Path

- **Reversal Cost:** Medium. Because all CI steps invoke `task <target>`, migrating between GitHub Actions, GitLab CI, or Forgejo requires changing only the thin pipeline YAML wrapper.
