# Phase R1-A Report — CI, Dependency, and Runtime-Declaration Remediation

**Status:** Source remediation implemented and verified. **Gate R1 is approved for non-production R2 reference remediation only.**

**Date:** 2026-10-22
**Scope:** AUD-006, the repository-policy portion of AUD-007, and AUD-008. This report covers only the repository and local reference environment. It does not represent a production deployment, artifact signing decision, or a decision to load a new artifact. The approval scope is recorded in [the Gate R1 approval record](./phase-R1-approval.md).

## Changes and evidence

| Area | Implemented control | Local evidence |
|---|---|---|
| Workflow integrity | Empty workflow-token default, minimal job scopes, immutable action SHAs, non-persisted checkout credentials, `pull_request_target` prohibition in every valid trigger form, SecOps ownership, full-reachable-history Gitleaks, and pinned zizmor with online audits enabled. | `tools/verify_supply_chain_and_signatures.py`; adversarial policy tests reject tag-pinned Actions, missing permission defaults, all `pull_request_target` forms, and `.yaml` workflow bypasses. |
| Dependency intake | pnpm 10.33.0 integrity pin, seven-day pnpm/uv cooldowns, pnpm provenance/exotic-subdependency/build-script restrictions, and seven-day Dependabot version-update cooldowns for pnpm, uv, and GitHub Actions. | `pnpm-workspace.yaml`, `package.json`, `pyproject.toml`, `uv.lock`, `.github/dependabot.yml`, and the repository verifier. |
| Security-fix exceptions | DEP-EXC-001 bounds the reviewed `uv` 0.13.4 resolver fix. DEP-EXC-002 admits only the Critical-advisory `certifi` 2026.10.19 release through a fixed, hash-verified package cutoff while the rolling cooldown remains in force for every other package. | [`dependency-security-exceptions.md`](../runbooks/dependency-security-exceptions.md) and verifier assertions. |
| Frontend runtime declaration | Containers directly run the current Node BFF servers; stale Next.js configuration and telemetry settings were removed; future framework adoption has an explicit ADR boundary. | [ADR-020](../adr/0020-node-bff-reference-runtime-and-deferred-nextjs-adoption.md), Dockerfiles, and verifier assertions. |
| Local reproducibility | Taskfile validates the bounded Node 24 Corepack-compatible engine, invokes pnpm through Corepack, and directs pytest to an owner-safe local temporary root. | `tools/verify_node_runtime.mjs`, `Taskfile.yml`, and canonical task runs below. |

## Verification run

All commands ran on 2026-10-22 using Node.js 24, pnpm 10.33.0, and uv 0.13.4. Test data remained synthetic and no production credentials or taxpayer data were accessed.

| Command | Result |
|---|---|
| `task gen` | Passed; contracts, OpenAPI, corpus manifest, SBOM, and provenance regenerated without unreviewed source drift. |
| `task lint` | Passed: Ruff, formatting, strict basedpyright, import boundaries, schema/OpenAPI checks, frontend WCAG/budget check, supply-chain verifier, Gitleaks working-tree scan, Biome, and TypeScript type checks. |
| `task test` | Passed: Python suite, 4/4 rules-engine mutants killed, 100.0% domain and 98.0% overall coverage gates, and all nine TypeScript workspaces. |
| `task eval` | Passed: eval/red-team suite, evaluation report, ASGI p50 4.46 ms and p95 5.21 ms (within the 1,500 ms SLO), synthetic DR restore drill, and non-advancing phase audit. |
| Local `zizmor` 1.30.1 | Passed for `.github/workflows`; PR CI will run the pinned equivalent. |
| Local full-history Gitleaks | Passed: 144 reachable commits and 5.81 MB scanned with redacted output and no findings. Pull-request CI must provide the new workflow evidence. |
| Merged PR #71 CI | Passed: full lint/typecheck/unit/contract/schema/eval slice, full reachable-history secret scan, workflow-security scan, and GitGuardian check. All six actionable review threads were resolved before merge. |

## Gate R1 disposition

| Gate condition | Disposition |
|---|---|
| Mutable Action tags rejected; workflow permissions default-deny; Gitleaks and zizmor controls defined | Met in source and verified by merged PR #71 CI. |
| GitHub branch protection requires CODEOWNERS review and all new jobs | Pending external repository-settings evidence; no branch-protection rule was changed. |
| Long-lived publishing or registry credentials replaced with approved OIDC/short-lived identity | Not established. No publishing workflow is introduced here, and repository secrets/settings were not inspected or changed. |
| Unsigned or retagged image/model fails before deployment | Blocked by OQ-018; the registry, signing identity, trust roots, revocation procedure, and verification point require SSRA approval. |
| Portability proof on SSRA-approved GitLab or Forgejo runner | Not established. Taskfile remains the portable command boundary, but no approved external runner was available. |

## Approval scope and remaining decision

The active-session user approved Gate R1 on 2026-10-22 after the PR evidence was merged. The approval authorizes non-production R2 source and reference remediation only. It does not close OQ-018, authorize production deployment or artifact publication, establish artifact/model trust, or advance a later phase gate. See [the Gate R1 approval record](./phase-R1-approval.md) for the retained controls.
