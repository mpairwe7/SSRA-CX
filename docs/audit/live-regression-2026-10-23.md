# Live Regression Record: Frontend Re-Audit Merges

**Date:** 2026-10-23 (run between 15:20 and 15:45 UTC; 2026-10-24 in Africa/Juba)
**Commit:** `f9c8861` (main after #85, #91, #87, and #90)
**Stack:** GPU Compose profile in reference mode. All ten services were healthy: two vLLM models, Orpheus TTS, agent runtime, Core API, frontend, staff preview, PostgreSQL, Qdrant, and Valkey. The deployed `apps/web/server.js`, `apps/console/server.js`, and `packages/ui/ops-console.js` matched the commit by SHA-256.

## Results

| Layer | Target | Result |
|---|---|---|
| 1. Public BFF and staff preview | Public tunnel to `ssra-frontend`; staff preview on loopback | 55 of 55 checks passed, with no network retries |
| 2. Core API and runtime | `127.0.0.1:18000`, `127.0.0.1:18001`, Qdrant | Passed once the two stale expectations were corrected (AUD-031): four long-horizon turns, memory tiers and erasure, EQ escalation and handoff v2, `en`/`pga`/`din`, five security blocks, and staff routes failing closed |
| 3. 1,000-scenario benchmark | Runtime on `127.0.0.1:18001`, direct | 1,000 of 1,000 passed; p50 113.6 ms, p95 270.7 ms, p99 893.9 ms; 6.9 s wall-clock (2026-10-21 baseline: p50 326.9 ms, p95 663.3 ms, 21.2 s) |

## Layer 1 detail

- Security headers: nonce plus `strict-dynamic` CSP, `frame-ancestors 'none'`, HSTS, COOP `same-origin`, `nosniff`, `no-store`. `/healthz` returns only `status` and `service`.
- Boundary: `/v1/admin/*` and `/v1/turns` return `403`, and `/admin` returns `404` on the public BFF. A malformed thread identifier and an array body return `400`. Forged `Authorization`, `X-Subject-Ref`, `auth_level: "STAFF"`, and `subject_ref` still produce a T0 answer.
- Answers, between 337 and 557 ms through the tunnel:
  - TIN steps rendered the Steps card.
  - PAYE and WHT rendered estimate cards with "Estimate only. It is not an official assessment." and one approved source.
  - `https://etax.nra.gov.ss@evil.example/` rendered "Not a confirmed SSRA channel".
  - The official portal rendered "Official SSRA channel".
  - A personal-balance question returned FAQ guidance with no figures.
  - Juba Arabic returned the Steps card.
  - No answer contained an invented default or internal telemetry label.
- Interface: the announcer read "Answer received. …", the thread identifier was 32 hex characters, `/ar` rendered RTL in a fresh context, the staff preview showed its server-rendered heading with no capability claims, the combobox set `aria-activedescendant`, and `/api/scorecard` returned `403` with `no-store`.

## Observations

- **AUD-031.** `tools/smoke_test_stack.py` expected `200` from `/v1/admin/public-status` and from staff takeover, hand-back, and feature flags. The live stack correctly returned `503` and `403`, including for a forged `X-SSRA-Staff-Id: secops_admin`, matching the governed route matrix. The tool was corrected; the controls were not changed. The benchmark generator also hard-coded "Date: 2026-10-21" and labelled direct runtime calls "over Ngrok". The report it produced was not committed, and the generators now record the real date and transport.
- **AUD-032.** In a context that had already visited `/en`, `/ar` rendered English and left-to-right because the saved locale overrides the URL.
- **AUD-033.** "Can you book me a flight to Nairobi?" returned unrelated e-Tax filing guidance with a citation instead of an out-of-scope response.
- **Shared infrastructure.** Another session took the stack down with `docker compose down` about 30 minutes after this run. Later lab measurements used isolated loopback servers instead.

## Boundary

This record covers reference behaviour on a local GPU profile with synthetic, public questions. It is not production-readiness, load-capacity, or field-performance evidence.
