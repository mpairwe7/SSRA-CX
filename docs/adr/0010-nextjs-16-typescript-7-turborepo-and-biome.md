# ADR-010: Frontend Stack — Next.js 16.3.x, TypeScript 7, Turborepo, and Biome

- **Status:** Proposed
- **Date:** 2026-10-16
- **Deciders:** Founding Principal Architect / Staff Engineer, SSRA Technical Lead
- **Reversal Cost:** Medium
- **References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 9.1–9.6, 15, 16, Appendix A

---

## 1. Problem Statement

How do we architect, type-check, lint, and bundle two self-hosted Next.js 16 applications (`apps/web` and `apps/console`) sharing one RTL-ready design system and low-bandwidth chat client?

## 2. Context

SSRA Assist requires two web applications:
- `apps/web`: Public taxpayer PWA and chat, engineered for low-end Android devices and 2G/3G networks (first-load JS ≤ 150 KB gzip max, targeting ≤ 120 KB; LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1) with full English (`en`), Juba Arabic (`pga`), and RTL Arabic (`ar`) support.
- `apps/console`: High-security staff console (OWASP ASVS 5.0 Level 3) for omnichannel inbox handling, agent-assist review, Knowledge & Tax Facts release workflows, and supervisor QA dashboards.

In 2026, Next.js 16.3.x is the stable release line with `proxy.ts` (replacing legacy `middleware.ts`), Cache Components (`cacheComponents: true` with `"use cache"`), React 19.2+, Turbopack, and React Compiler. TypeScript 7 (`7.0.2`) ships native `tsc` for fast type-checking, while Biome (`2.5.15`) replaces slow ESLint/Prettier chains for 95%+ of lint and formatting rules.

## 3. Options Considered

1. **Separate Repositories for `web` and `console` with Classic Webpack + ESLint + Prettier:** Duplicated UI components, slow CI lint/type-check times, and drift in AG-UI and OpenAPI client types.
2. **pnpm Workspace + Turborepo + Next.js `16.3.8` (`output: "standalone"`) + TypeScript `7.0.2` + Biome `2.5.15` with Targeted ESLint Only Where Needed (Selected):** Unified monorepo sharing `packages/ui`, `packages/chat-ui`, `packages/api-client`, `packages/contracts`, `packages/i18n`, `packages/telemetry`, and `packages/config`.

## 4. Decision

We adopt Option 2:

1. **Framework & Runtime Pinning (7-Day Cooldown Verified 2026-10-16):**
   - Pin `next@16.3.8` (released 2026-09-30, latest in the `16.3.x` baseline line specified in Section 9.1; note `16.4.0` from 2026-10-06 is tracked for scheduled upgrade after Gate 0 review) and `react@19.3.0` / `react-dom@19.3.0`.
   - Use `output: "standalone"` for self-hosted container deployment on NCA Kubernetes with a shared Valkey cache handler—zero Vercel or cloud-vendor lock-in.
   - Use `src/proxy.ts` in both apps for per-request cryptographic CSP nonces, `Trusted-Types`, locale negotiation (`en`, `pga`, `ar`), and route authentication gating.
   - Enable `cacheComponents: true` (`"use cache"`) on public `T0` pages to minimise server compute and TTFB.
2. **Type-Checking (`typescript@7.0.2`):**
   - Enforce strict TypeScript (`strict: true`, `noUncheckedIndexedAccess: true`, `exactOptionalPropertyTypes: true`). Keep a TypeScript 6.x peer configuration only if a specific build plugin requires the legacy compiler API before TypeScript 7.1.
3. **Linting & Formatting (`@biomejs/biome@2.5.15`):**
   - Use Biome as the single fast formatter and primary linter across all TypeScript/JSON files, including a11y rules (`useAltText`, `useButtonType`, `useValidAriaProps`).
   - Retain a minimal ESLint flat config solely for Next.js-specific compiler/navigation rules not yet covered by Biome.
4. **Design System & RTL (`packages/ui`):**
   - Tailwind CSS `4.3.3` with CSS logical properties (`ms-*`, `me-*`, `ps-*`, `pe-*`, `text-start`, `text-end`) so Arabic (`dir="rtl"`) and English/Juba Arabic (`dir="ltr"`) share one stylesheet without layout bugs.
   - Self-host subsetted `Noto Sans` and `Noto Naskh Arabic` fonts via `next/font/local` (zero requests to Google Fonts).

## 5. Consequences

- **Positive:** Sub-second lint/format runs via Biome, fast incremental builds via Turborepo, strict CSP security via `proxy.ts`, and zero third-party network calls from taxpayer browsers.
- **Negative / Trade-offs:** Next.js 16 scheduled security releases require monitoring and patching within 72 hours (documented in `docs/runbooks/incident-and-rollback.md`).

## 6. Reversal Cost & Migration Path

- **Reversal Cost:** Medium. Because business state and AI orchestration reside in `services/api` and `services/agent-runtime` behind OpenAPI 3.1 and AG-UI SSE contracts, the frontend apps remain thin experience layers.
