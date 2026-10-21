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
