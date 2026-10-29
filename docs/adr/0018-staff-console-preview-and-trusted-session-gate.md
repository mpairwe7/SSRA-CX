# ADR-018: Staff Console Preview & Trusted Session Gate

**Status:** Accepted
**Date:** 2026-10-21
**Decision owners:** SSRA ICT, SecOps, Operations
**Related:** OQ-005, OQ-010, OQ-013, OQ-014, OQ-015; ADR-012, ADR-019

## Context

The server-rendered staff console selected a role from browser `localStorage`, generated a staff ID in the browser, and sent that ID in `X-SSRA-Staff-Id`. The page also displayed static sample cases, metrics, and service health as live, and some buttons displayed success without performing an audited operation. The BFF checked the caller-selected ID against static allowlists, which did not authenticate the caller.

The staff identity provider, role mapping, and audit requirements are still open (OQ-014). The analytics warehouse and metric provenance are also open (OQ-013); analytics and live-status endpoints return 503, while staff, admin, and knowledge-release data/action routes return 403 in reference mode. Production mode blocks the Core API and agent runtime with 503. Enabling operational dashboards would imply authorization, durability, and freshness that the server cannot establish.

## Options considered

1. Keep the UI visible and label the fabricated metrics as examples.
2. Keep navigation as a non-operational preview, remove client-supplied identity/actions, and deny staff data APIs until server-verified sessions exist.
3. Hide the console completely until identity and analytics decisions are approved.

## Decision

Use option 2. The staff console is a persistent preview with no taxpayer, case, operational or live telemetry data. Browser persona choice controls navigation presentation only and is not treated as authorization. Staff API routes return `403 NOT_AUTHORIZED`. The public taxpayer BFF blocks direct `/v1/*` proxy access except the explicit feedback submission route; chat turns go through the sanitizer-backed `/api/turns` route.

Before operational screens return, a server-side integration must validate the configured staff issuer, audience, signature, expiry/revocation and role claims, enforce action permissions server-side, and record auditable outcomes. Each live metric must carry a trusted source and observation timestamp. Missing, stale, and synthetic data must be labeled distinctly. No role or synthetic telemetry decision is made by the browser.

## Consequences

- Public and staff-facing interfaces no longer imply account identity, current service health, or successful staff actions without server evidence.
- The preview is useful for navigation and layout review, but operational workflows remain unavailable until SSRA resolves OQ-014 and OQ-013.
- Core API staff inbox, conversation, case approval, knowledge-release, admin, and JIT routes fail closed with 403; public health-status data fails closed with 503 until trusted telemetry is available.
- User testing must not use the preview to make taxpayer decisions or operate production systems.

## Reversal cost

Medium. Re-enable live console functionality only after an approved identity and role model, server-side authorization, audit trail, provenance-bearing APIs, and end-to-end security review are delivered together.

## Update (2026-10-23)

R2-F renders the preview card, heading, and page title on the server for every route, so the non-operational state is visible without JavaScript. Destination descriptions that implied live capabilities were removed. The preview status uses the warning colour, not the success colour. See [AUD-023](../audit/findings.md#aud-023--s3--dashboard-truthfulness--preview-navigation-describes-unavailable-capabilities-as-current) and the [R2-F report](../audit/phase-R2-F-staff-console-report.md). The preview gate itself is unchanged.

## Update (2026-10-25): Hercules UX/UI Design System, OWASP API5:2023 BFLA Route Governance & Keycloak OIDC Preview Flows

1. **Hercules UX/UI Design System Alignment (`packages/ui/ops-console.js`):**
   - Enforces the two-voice typographic hierarchy (`IBM Plex Sans` 400/500/600 UI + `IBM Plex Mono Light 300` metadata/figures with `font-variant-numeric: tabular-nums` and OpenType `font-feature-settings: "tnum" 1, "zero" 1, "cv01" 1`), `.woff2` font preloads and dynamic `<meta name="theme-color">`, `--rail-w-expanded: 220px`, ink-only `.ops-chip` and `.ops-delta` readings (zero background fill pills), `0.6em` stat units (`splitMeasureParts`), `28px` brand mark, `26px` circular account avatar with role-type initials (`AD`/`ST`/`AU`), `aria-labelledby` sidebar group landmarks (`Work`, `Audit`, `Configure`, `Observe`), `320px` mobile drawer label/account overrides (`staffGuard.css`), `@media (forced-colors: active)`, `@media print`, and `@media (prefers-reduced-transparency: reduce)` solid-surface fallbacks.
2. **Server-Rendered Route Governance Specification & Navigation Landmarks (`ROUTE_SPECS`, `renderPreviewCard`, & `renderServerRailGroups`):**
   - Every dashboard route (`/admin`, `/admin/audit`, `/admin/replay`, `/admin/quality`, `/admin/knowledge`, `/admin/flags`, `/admin/overrides`, `/admin/outbox`, `/agent`, `/supervisor`, `/analytics`) renders its exact `ROUTE_SPECS` governance metadata (`#spec-roles`, `#spec-standard`, `#spec-surface`, `#spec-gate`) and `#staff-rail-groups` (`aria-current="page"`) on the server for no-JS and initial SSR parity, and applies persona-scoped preview navigation filtering and preview-route redirection (browser-selected personas are preview presentation only and never grant staff authorization; server-side APIs enforce the trusted session gate).
3. **Keycloak 26.4.11 OIDC Sign-In (`/signin`), Sign-Up (`/signup`) & Callback (`/signin/callback`) Preview Flows:**
   - Adds `/signin`, `/signup` (`prompt=create`), and `/signin/callback` routes to the Operations Console with Web Crypto PKCE `S256` generation, `CWE-208` constant-time `state` and RFC 9207 `iss` verification, URL query scrubbing (`history.replaceState`), and explicit fail-closed messaging (`OQ-005` / `OQ-014`) while keeping all `/api/*` and `/v1/*` routes on `ssra-console` denied with `403 AUTHENTICATED_STAFF_SESSION_REQUIRED`.
4. **MainChat Sign-In/Register Linking & Role-Scoped Reference Workbenches (`apps/web/server.js`, `packages/ui/ops-console.js`, `apps/console/src/oidc-keycloak.ts`):**
   - Links `#rail-signin-btn` and `#rail-register-btn` in the MainChat sidebar footer to `/signin` and `/signup`, provides a non-authoritative reference/demo sign-in flow (`CONSOLE_ACCOUNT_DIRECTORY` / `verifyConsoleCredentialDigest`) that routes `ssra_admin` -> `/admin`, `ssra_staff` -> `/agent`, `ssra_auditor` -> `/analytics` (with read-only Separation of Duties), and `verified_taxpayer` -> `/en`, does not grant server-side authorization, and leaves the fail-closed preview gate (`403 AUTHENTICATED_STAFF_SESSION_REQUIRED` on `/api/*` and `/v1/*`) in full effect.
5. **Shared visual language with the public assistant (2026-10-28):**
   - The console uses the main chat page's tokens: light canvas with the indigo top glow, `#1E40AF` rail, IBM Plex Sans, pill buttons, and white cards. Light is the default theme; dark and high contrast are opt-in.
   - Non-interactive readings (session state, preview state, priority, status) render as plain text in text-safe inks rather than capsules, and no component carries a leading-edge colour bar. Provenance text ("Preview only", `ILLUSTRATIVE_FALLBACK telemetry`) stays visible in the top bar on every route, so restyling never makes reference data look live.
6. **One theme choice shared with the public assistant (2026-10-28):**
   - `packages/ui/theme.js` owns the palette for both surfaces: Gemini-style dark (`#0F1011` canvas, `#1F1F1F` rail) and GitHub-style high contrast (`#0A0C10`).
   - It also owns the `ssra-theme` storage key (`system`, `light`, `dark`, `high-contrast`) and a pre-paint bootstrap script.
   - The console's Appearance menu offers System, Light, Dark and High contrast. A theme is presentation state only and never affects authorization.
7. **Dedicated sign-in and sign-up pages; the role comes from the credentials (2026-10-29):**
   - `/signin`, `/signup` and `/signin/callback` use an auth layout (`data-layout="auth"`) with no sidebar, top bar or command palette, themed through the shared tokens.
   - The sign-in page offers no role choice. The role, and with it the landing workspace, is resolved from the account the credentials match (later, from the Keycloak token's roles). It is never chosen in the browser.
   - The passkey shortcut that signed in as a selected role without credentials is removed.
   - Single sign-on stays a disclosed, unconnected preview (OQ-005/OQ-014).



