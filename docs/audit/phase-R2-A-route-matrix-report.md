# Phase R2-A Report — Core API Route-Matrix Assurance

**Date:** 2026-10-22
**Status:** Source remediation implemented; Gate R2 has not been evaluated or approved.
**Scope:** AUD-009 Core API fail-closed route-matrix assurance only.

## Scope and evidence boundary

Gate R1 approval permits non-production R2 reference remediation. This report records a source and reference-mode assurance change. It provides no deployment, production-readiness, or later-phase approval claim.

## Implemented controls

- `services/api/tests/test_route_matrix.py` derives all callable Core API operations from OpenAPI and requires a consciously reviewed, safe synthetic request fixture for each one.
- The current contract has 35 operations across 32 paths. Missing fixtures or undocumented operation changes fail the matrix before requests are sent.
- Missing, blank, `production`, and unknown `SSRA_RUNTIME_MODE` values return RFC 9457 `503 UPSTREAM_UNAVAILABLE` for every covered operation.
- An independently governed status policy assigns the expected `reference`-mode result for each operation: available routes return `200`, staff routes return `403`, and unapproved providers return `503`. The matrix separately requires that this policy remains declared by OpenAPI, so a contract edit cannot redefine its expected runtime outcome.
- API middleware now creates ETags and stores idempotency responses only for successful responses. RFC 9457 denial envelopes are not entity-cached.
- `ssra_testing.AsgiTestClient` uses an ASGI transport for Core API, MCP, runtime, channel, evaluation, readiness, benchmark, and smoke paths so the test harness observes real fail-closed responses rather than blocking in a synchronous adapter.
- The synthetic-test package declares the existing lock-pinned `httpx==0.28.1` dependency. The lock refresh records the package relationship without changing a component version.

## Validation

| Check | Result |
|---|---|
| Focused Core API matrix and API regression tests | Passed: 18 tests |
| `task gen` | Passed |
| `task lint` | Passed: strict Python and TypeScript checks, OpenAPI compatibility, frontend budget/WCAG gate, supply-chain traceability, and secret scan |
| `task test` | Passed: Python, 4/4 rules mutants killed, domain 100.0% and overall 98.0% coverage, and nine TypeScript package suites |
| `task eval` | Passed: 24 evaluation/red-team tests, reference evaluation report, ASGI benchmark p50 3.25 ms / p95 3.49 ms, DR restore drill, and phase verifier with no gate advancement |

## Retained AUD-009 gaps

- Rendered browser tests for public chat, conversation rail/sidebar, and staff dashboard preview.
- WCAG 2.2 AA evidence for keyboard, focus return, reflow, reduced data, and Arabic RTL flows.
- BFF identity-stripping and encoded-path assurance, 2G and offline-queue tests, and accessibility traces/screenshots.
- Schemathesis/API fuzzing, supported mutation testing, and five uncached runs for flake evidence.

## Gate disposition

R2 remains unapproved. The retained gaps, other R2 findings, and approval evidence must be completed and reviewed under the phase-gate process before any advancement.
