# Phase R2-B Report — Rendered Browser Flow Assurance

**Date:** 2026-10-22

**Status:** Source remediation implemented; Gate R2 has not been evaluated or approved.
**Scope:** AUD-009 rendered-browser, keyboard, focus, RTL, low-data/offline, BFF-boundary, and staff-preview assurance for reference code.

## Scope and evidence boundary

Gate R1 approval permits non-production R2 reference remediation. This report records local rendered Chromium evidence against synthetic loopback services. It provides no production-readiness, deployment, legal-content, staff-identity, or later-phase approval claim.

## Implemented controls

- Added exact, lockfile-integrity-pinned `@playwright/test@1.58.0` and a Playwright configuration with one worker, CI retries, retained failure traces/screenshots, Africa/Juba time zone, and reduced-motion emulation.
- Added a loopback-only synthetic runtime that records only the BFF-forwarded fields and emits a fixed non-factual response. It contains no credentials, taxpayer/staff data, tax numbers, provider calls, or production endpoints.
- Made rendered browser tests part of `task test`; CI installs Chromium from the lock-pinned Playwright package before running Taskfile gates.
- Verified the public BFF uses the canonical anonymous body, strips browser-supplied authorization/subject headers, and rejects direct, percent-encoded, and encoded-separator protected `/v1` route probes.
- Verified a 320 CSS-pixel public rail has usable targets, no horizontal overflow, reduced motion, correct inert-state synchronization, visible composer focus, and Escape focus restoration. The implementation keeps the drawer visible while it opens and delays only the hidden state while it closes so focus can move into the drawer after the state update.
- Verified Arabic language/direction, explicit low-data mode, offline safe abstention, and preservation of a typed draft.
- Verified the staff dashboard remains preview-only, its protected API returns `403` with `no-store`, and desktop/mobile rail navigation returns focus predictably.

## Standards and design references

- [WCAG 2.2](https://www.w3.org/TR/WCAG22/) informs the explicit 320 CSS-pixel reflow, keyboard-focus, non-obscured focus, reduced-motion, and target-size assertions. The tests provide targeted evidence only; they do not establish WCAG conformance.
- [Playwright accessibility testing guidance](https://playwright.dev/docs/next/accessibility-testing) distinguishes automated checks from manual and inclusive-user evaluation. The project uses browser assertions for this phase and retains manual accessibility work.
- `@playwright/test@1.58.0` was verified on 2026-10-22 from the [official Playwright repository](https://github.com/microsoft/playwright) and [release notes](https://playwright.dev/docs/release-notes), is older than the seven-day cooldown, and is Apache-2.0. Its exact package integrity is recorded in `pnpm-lock.yaml`.

## Validation

| Check | Result |
|---|---|
| Rendered browser suite | Passed: 5 tests against fresh loopback services |
| Flake evidence | Passed: five clean full-suite runs, 25 test executions total, 2026-10-22 |
| BFF forged identity / protected path checks | Passed in rendered public-chat flow |
| Public rail reflow, focus, RTL, low-data, offline checks | Passed in rendered public-chat flows |
| Staff preview denial and desktop/mobile focus checks | Passed in rendered staff-console flows |

## Threat-model delta

The change adds only local test processes and a development browser dependency. It does not add a browser-to-production egress path, change risk tiers, expose credentials, accept client identity claims, or enable staff data/actions. The new tests make regressions in the public BFF boundary and preview-denial UI visible before merge.

## Retained AUD-009 gaps

- Full WCAG 2.2 conformance evidence, assistive-technology/device review, and moderated testing with taxpayers and staff remain required.
- Real 2G throttling, low-end Android budgets, visual-regression baselines, and the shared offline-queue flow remain outside this synthetic suite.
- Schemathesis/API fuzzing and supported mutation evidence remain R2 work beyond the rendered browser scope.
- Automated axe scanning is not adopted because `@axe-core/playwright` is MPL-2.0 and OQ-012 requires SSRA Procurement and Legal approval for that license class.
- The signed, versioned offline statutory snapshot remains governed by OQ-019; this suite does not validate browser tax facts.

## Gate disposition

R2 remains unapproved. This report closes the listed rendered-browser assurance slice only. The retained gaps, other R2 findings, and formal approval evidence must be completed and reviewed under the phase-gate process before any advancement.
