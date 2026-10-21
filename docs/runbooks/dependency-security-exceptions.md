# Dependency Security Exceptions

**Status:** Repository control record
**Date:** 2026-10-22
**Owner:** SSRA Assist engineering maintainers
**Related:** [ADR-015](../adr/0015-supply-chain-hardening-and-sovereign-gitops.md), [OQ-018](../open-questions.md#oq-018--artifact-and-model-trust)

## Purpose

The repository enforces a seven-day dependency release cooldown. A security fix may be used before that period only when this record identifies the exact tool or package, the upstream advisory, the verified release artifact, the bounded scope, and the expiry condition. This record does not select a production artifact registry, signing identity, or deployment verification point; those decisions remain open in OQ-018.

## Active records

### DEP-EXC-001 — uv 0.13.4

| Field | Record |
|---|---|
| Component | `uv` 0.13.4, used only to resolve the repository lock and in the CI setup step |
| Release date | 2026-10-20 |
| Security reason | The upstream release fixes [GHSA-hq85-5cpj-mr62](https://github.com/astral-sh/uv/security/advisories/GHSA-hq85-5cpj-mr62). |
| Evidence reviewed | The [official uv 0.13.4 release](https://github.com/astral-sh/uv/releases/tag/0.13.4) archive checksum is `2b428396f12572d4429cf210ca234dd599a33b3af0958a4d5ed569d63e3f344f`. |
| Verification date | 2026-10-22 |
| Bound | The exact version and checksum are asserted by `tools/verify_supply_chain_and_signatures.py`; this resolver exception does not add a package-specific cooldown exclusion. |
| Expiry | The record ceases to be an early-release exception after 2026-10-27, when the release reaches the normal seven-day age. |

### DEP-EXC-002 — certifi 2026.10.19

| Field | Record |
|---|---|
| Component | `certifi` 2026.10.19, a transitive runtime CA bundle used by the locked HTTP client dependency graph |
| Release date | 2026-10-20 |
| Security reason | GitHub classifies [GHSA-6q48-6c7w-9gw2](https://github.com/advisories/GHSA-6q48-6c7w-9gw2) as Critical and identifies 2026.10.19 as the first patched release. |
| Evidence reviewed | The [official certifi 2026.10.19 release](https://github.com/certifi/python-certifi/releases/tag/2026.10.19) and [PyPI release](https://pypi.org/project/certifi/2026.10.19/) publish wheel SHA-256 `42d35340cc5b9ba78e818ddbff0c5b1c2b779de448a340fd1b989f5fa8670e1b` and source SHA-256 `035c1e85572b141bf1c3a3eff0e33a8eb74917522f2559075ff8d2fea780a1ae`. |
| Verification date | 2026-10-22 |
| Bound | `exclude-newer-package = { certifi = "2026-10-21T00:00:00Z" }` permits only the reviewed release window before the regular seven-day holdback. The verifier requires that exact cutoff in both manifest and lockfile, exactly one `certifi` 2026.10.19 record, the PyPI registry source, the reviewed source hash, and exactly one reviewed wheel hash with no additional wheel record. |
| Expiry | Remove this package-specific cutoff and regenerate `uv.lock` no later than 2026-10-27, when 2026.10.19 reaches the normal seven-day age. |
| Scope | Source and reference-lock remediation only. Any deployed image must be independently rebuilt and verified under OQ-018; this record does not authorize image, model, or production deployment changes. |

These exceptions do not loosen `exclude-newer = "1 week"` for other packages or authorize deployment of any new image or model artifact.

## Future exception procedure

1. Record the affected component, exact version, upstream security advisory, release date, official artifact checksum, verification date, and the smallest affected CI or development scope.
2. Keep the exception time-bounded. Do not use a broad allow-list or a permanent cooldown exclusion.
3. Add a repository policy assertion and a regression test where the policy can be mechanically checked.
4. Obtain the required SSRA SecOps and procurement decision before an exception affects a deployment artifact, registry trust root, model load, or operational environment.
5. Remove or mark the record expired once the normal cooldown elapses, the security fix is replaced, or the relevant release is no longer used.

## Verification

`task lint` runs the repository supply-chain verifier. The verifier checks the exact CI setup version and checksum, the rolling uv cooldown, and the sole DEP-EXC-002 package-specific cutoff together with the patched `certifi` hashes.
