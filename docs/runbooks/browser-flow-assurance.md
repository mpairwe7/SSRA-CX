# Rendered Browser Flow Assurance

## Purpose

Run the merge-blocking rendered browser checks for the taxpayer web shell, public BFF, and staff-console preview. This runbook applies to reference code only. It does not authorize a production deployment, access to taxpayer data, or staff operations.

## Preconditions

1. Use the Node version required by `package.json` and activate the lock-pinned pnpm through Corepack.
2. Install the frozen workspace dependencies.
3. Install the lock-pinned Playwright Chromium browser. CI uses `pnpm exec playwright install --with-deps chromium`; a local workstation may need the equivalent reviewed operating-system dependencies.
4. The suite has fixed loopback addresses. Do not change the configuration to target a production, staging, or data-bearing environment.

## Run the suite

```bash
corepack pnpm exec playwright test
```

`task test` invokes the same command after the Python and workspace TypeScript suites. In CI, Chromium is installed before `task test` runs.

The Playwright configuration starts only these loopback services:

| Service | Loopback address | Purpose |
|---|---:|---|
| Synthetic runtime | `127.0.0.1:3101` | Records only sanitized synthetic turn bodies and returns a fixed synthetic response. |
| Public web BFF | `127.0.0.1:3100` | Serves the actual `apps/web/server.js` browser shell. |
| Staff preview | `127.0.0.1:3102` | Serves the actual `apps/console/server.js` preview shell. |

The test harness must not use credentials, live taxpayer/staff data, real tax figures, or live upstream endpoints.

## Current test matrix

| Flow | Assertions |
|---|---|
| Public chat through BFF | A visible synthetic answer; canonical anonymous request body; client-supplied authorization and subject headers never reach the synthetic runtime. |
| Direct protected routes | Direct, percent-encoded, and encoded-separator `/v1` paths remain denied or rejected. |
| Public mobile rail | 320 CSS-pixel reflow, minimum target size, reduced motion, inert-state synchronization, visible focus, and Escape focus return. |
| Arabic and constrained network | `lang=ar` and RTL layout, explicit low-data mode, offline safe fallback, and preserved composer draft. |
| Staff preview dashboard | Persistent preview state, client-side navigation focus return, and `403`/`no-store` API denial. |
| Staff mobile rail | Drawer focus enters the first navigation item and returns to its trigger after Escape. |

## Artifacts and triage

- Playwright keeps screenshots and traces on failure under `test-results/playwright-artifacts/`; CI creates an HTML report under `playwright-report/`. Both paths are ignored by Git.
- A failed assertion should be repaired at the source, then rerun with the focused spec and the full suite. Do not weaken an assertion merely to make the suite pass.
- If a prior interrupted run owns a loopback port, stop only the local test process that owns it, then rerun. Do not change test URLs to a shared environment.
- Record five clean suite runs when collecting flake evidence. The R2-B report records the initial five-run evidence for this suite.

## Evidence limits

This suite supplies rendered Chromium evidence for the matrix above. It does not establish full WCAG conformance, assistive-technology compatibility, low-end Android performance, 2G throttling behavior, signed offline statutory-data governance, a real staff session, or production readiness. Manual accessibility assessment and inclusive user testing remain required.

Automated axe scanning is not currently included because the `@axe-core/playwright` package has an MPL-2.0 license. OQ-012 requires SSRA Procurement and Legal approval before such a dependency can be adopted.
