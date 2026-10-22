# ADR-021: Rendered Browser Assurance and Synthetic Runtime

- **Status:** Accepted as a repository safety baseline; not production authorization
- **Date:** 2026-10-22
- **Deciders:** SSRA Assist engineering maintainers
- **Reversal Cost:** Medium
- **Related:** [ADR-011](./0011-low-bandwidth-taxpayer-pwa-and-service-worker.md), [ADR-012](./0012-bff-authentication-keycloak-passkeys-and-sessions.md), [ADR-018](./0018-staff-console-preview-and-trusted-session-gate.md), [AUD-009](../audit/findings.md#aud-009--s2--quality-and-ux-assurance--browser-flow-and-flake-gates-remain-partially-implemented), [R2-B report](../audit/phase-R2-B-browser-flow-report.md)

## Context

The public chat and staff console previously had source and unit-level checks, but no rendered browser evidence for their most safety-critical paths. That left regressions possible in BFF subject stripping, denial of direct protected routes, mobile rail focus, Arabic direction, offline recovery, and staff-preview denial behavior.

These applications are Node HTTP servers that render browser shells. The rendered tests therefore need to run those actual servers while keeping all test traffic local, synthetic, and independent from any taxpayer, staff, or production provider data.

## Options Considered

1. Retain source and unit tests only.
2. Add a manual-only release checklist.
3. Add a lock-pinned rendered browser suite that runs against local synthetic services and keep manual accessibility and user research as separate evidence.

## Decision

1. Use the exact, lockfile-integrity-pinned `@playwright/test@1.58.0` package for rendered browser assurance. It is an Apache-2.0 development dependency, verified on 2026-10-22 against its official release and repository after the seven-day adoption cooldown.
2. Start the public Node BFF, staff-preview Node server, and a synthetic runtime only on loopback ports for the suite. The synthetic runtime accepts no credentials, emits no tax figures, and returns only a fixed synthetic answer.
3. Make the suite a `task test` gate. CI installs Chromium from the lock-pinned Playwright package before executing the Taskfile gates. Failure artifacts are retained locally or by CI and excluded from source control.
4. Assert rendered public-chat/BFF, protected-path, mobile reflow/focus/reduced-motion, Arabic RTL, low-data/offline, and staff-preview flows. Each test must make a claim only about the rendered reference behavior it observes.
5. Keep production authorization, staff authentication, factual tax advice, live upstreams, visual-regression baselines, assistive-technology testing, and moderated user research outside this synthetic suite.

## Consequences

- A browser regression in the covered flows now blocks the repository test gate before merge.
- The mobile drawer keeps visibility available while it opens, delays only its hidden state while it closes, and moves keyboard focus after the inert state is synchronized. This prevents focus from being lost to the document body during a natural drawer transition.
- CI requires Chromium system dependencies, adding a bounded test-runtime dependency to the pipeline.
- Automated accessibility scanning remains deliberately unadopted pending OQ-012. The commonly used `@axe-core/playwright` package is MPL-2.0, which is outside the current permissive-license policy until SSRA Procurement and Legal approve it. This does not remove the manual accessibility evidence requirement.

## Reversal Cost

Removing or replacing the suite changes the CI runtime, local developer workflow, evidence format, and the regression boundary for public and staff UI behavior. The decision is therefore medium-cost to reverse.

## Verification

`tests/browser/` contains the rendered tests and `playwright.config.ts` defines the synthetic loopback topology. The R2-B report records five clean suite runs of the five browser tests on 2026-10-22. `task test` and CI execute the normal browser gate; retained R2 evidence gaps remain documented in AUD-009.
