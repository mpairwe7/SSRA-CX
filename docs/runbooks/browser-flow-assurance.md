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

`task test` sets `TMPDIR=/tmp` for this command. Chromium stores its temporary profile under `TMPDIR`, and a network-mounted `TMPDIR` (for example CIFS) caused intermittent `Target page, context or browser has been closed` and `net::ERR_ABORTED` failures: 1 in 264 trivial page loads on a CIFS `TMPDIR`, against 0 in 3,508 on local disk (2026-10-23). When running the command directly, use a local `TMPDIR` as well.

The Playwright configuration starts only these loopback services:

| Service | Default loopback address | Purpose |
|---|---:|---|
| Synthetic runtime | `127.0.0.1:3101` | Records only sanitized synthetic turn bodies. It returns a fixed synthetic response, or a named synthetic scenario (for example a `503`, a `429` with `Retry-After`, a dropped connection, or a card with missing props). |
| Public web BFF | `127.0.0.1:3100` | Serves the actual `apps/web/server.js` browser shell. |
| Staff preview | `127.0.0.1:3102` | Serves the actual `apps/console/server.js` preview shell. |

To run a second, isolated copy (for example from another git worktree while the default ports are busy), set a different loopback port base. The runtime, staff preview, and unused API ports follow at `+1`, `+2`, and `+3`:

```bash
SSRA_BROWSER_TEST_PORT_BASE=3400 corepack pnpm exec playwright test
```

Do not stop a process that owns the default ports unless you started it; another local session may be running the suite.

The test harness must not use credentials, live taxpayer/staff data, real tax figures, or live upstream endpoints.

## Current test matrix

| Flow | Assertions |
|---|---|
| Public chat through BFF | A visible synthetic answer; canonical anonymous request body; client-supplied authorization and subject headers never reach the synthetic runtime. |
| Public answer rendering | Cards never fill missing values; personal and action cards show a sign-in notice; unregistered components render nothing; no confirmation control; estimates need an approved source; no internal telemetry labels. |
| Public failure states | `503`, `429` with `Retry-After`, HTML `500`, and a dropped upstream each show a specific plain-language state with no raw body; the draft is restored; `Try again` resends; malformed BFF bodies and thread identifiers return `400`. |
| Public client integrity | A rejected clipboard write reports failure; new thread identifiers are 128-bit random hex; an in-progress reply is never saved to the device. |
| Public inclusion and low bandwidth | Unreviewed locales use English interface text with `lang="en"` and a notice; the composer shows the AI, accuracy, and identifier disclosure; device history can be turned off; low-data mode removes blur, backgrounds, and motion; the no-script note points to the official portal; `/healthz` exposes no internal addresses. |
| Public accessibility semantics | Replies are announced through a separate status region, not the transcript; the composer status is visible on phones; the account panel is a disclosure that Escape closes; Settings tabs follow the APG keyboard model; dialogs make the page inert and return focus; rename, delete, and clear use in-page dialogs with Cancel focused; only working shortcuts are shown; light-theme offline status reaches 4.5:1; speech uses the interface language. |
| Direct protected routes | Direct, percent-encoded, and encoded-separator `/v1` paths remain denied or rejected. |
| Public mobile rail | 320 CSS-pixel reflow, minimum target size, reduced motion, inert-state synchronization, visible focus, and Escape focus return. |
| Arabic and constrained network | `lang=ar` and RTL layout, explicit low-data mode, offline safe fallback, and preserved composer draft. |
| Staff preview dashboard | Persistent preview state, command-palette visible focus, client-side navigation focus return, and `403`/`no-store` API denial. |
| Staff console semantics | The command palette follows the APG combobox pattern and makes the shell inert; the account menu supports arrow keys, Home/End, and Escape; the light-theme preview chip reaches 4.5:1 and the status pill uses the warning colour; the preview renders without JavaScript and claims no live capability. |
| Staff mobile rail | Drawer focus enters the first navigation item and returns to its trigger after Escape. |

## Artifacts and triage

- Playwright keeps screenshots and traces on failure under `test-results/playwright-artifacts/`; a failed CI job uploads those paths and the HTML report under `playwright-report/`. Both paths are ignored by Git.
- A failed assertion should be repaired at the source, then rerun with the focused spec and the full suite. Do not weaken an assertion merely to make the suite pass.
- If a prior interrupted run of yours owns a loopback port, stop only that process, then rerun. If another session owns it, use `SSRA_BROWSER_TEST_PORT_BASE` instead. Do not point test URLs at a shared environment.
- Record five clean suite runs when collecting flake evidence. The R2-B report records the initial five-run evidence for this suite.

## Evidence limits

This suite supplies rendered Chromium evidence for the matrix above. It does not establish full WCAG conformance, assistive-technology compatibility, low-end Android performance, 2G throttling behavior, signed offline statutory-data governance, a real staff session, or production readiness. Manual accessibility assessment and inclusive user testing remain required.

Automated axe scanning is not currently included because the `@axe-core/playwright` package has an MPL-2.0 license. OQ-012 requires SSRA Procurement and Legal approval before such a dependency can be adopted.
