# ADR-011: Low-Bandwidth Taxpayer PWA and Service Worker Strategy

- **Status:** Deferred pending a future frontend-runtime decision
- **Date:** 2026-10-16
- **Deciders:** Founding Principal Architect / Staff Engineer, SSRA Technical Lead
- **Reversal Cost:** Low–Medium
- **References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 2, 9.2, 9.5

> **Implementation status:** `apps/web` currently runs a Node BFF and does not declare Next.js. The Next.js and Turbopack assumptions in this document are deferred design inputs, not a statement about the served runtime. See ADR-020.

---

## 1. Problem Statement

How can a future installable, offline-capable, 2G-resilient Progressive Web App (`apps/web`) meet a strict 150 KB gzip first-load JavaScript budget?

## 2. Context

In South Sudan, intermittent mobile connectivity, expensive data bundles, and power interruptions are the primary operating reality—not edge cases. Taxpayers need to read core tax procedures, verify official SSRA payment channels, run offline-capable PAYE estimates, and queue chat questions when connectivity drops. However, traditional Workbox/Webpack service-worker wrappers often conflict with Next.js 16's Turbopack bundler, inflate client bundles, or accidentally cache authenticated `T1` personal responses on shared devices.

## 3. Options Considered

1. **Third-Party Workbox/Serwist Webpack Plugin Wrapper:** Adds build-time coupling that can lag behind Next.js 16.3.x + Turbopack releases and injects extra runtime KB into the client bundle.
2. **Hand-Written, Audited Service Worker (`public/sw.js` + `app/manifest.ts`) per Official Next.js 16 PWA Guide with Strict T0-Only Cache Policy (Future implementation option):** Zero bundler coupling under Turbopack, zero third-party SW runtime bloat, and explicit security boundaries so personal (`T1`–`T3`) data is never written to browser Cache Storage or IndexedDB.

## 4. Decision

Option 2 remains a future implementation option; it is not adopted in the current Node BFF runtime:

1. **Hand-Written Service Worker (`apps/web/public/sw.js`) & Web App Manifest (`apps/web/src/app/manifest.ts`):**
   - Pre-caches the minimal offline app shell, localized static assets (`en`, `pga`, `ar`), and the published `T0` FAQ / Official-Channel Verification cards.
   - Implements a **Queued Outbox** (`IndexedDB` encrypted/ephemeral queue for anonymous `T0` questions only) using Background Sync / online-event replay when connectivity returns.
   - **Hard Security Rule:** Never cache `/api/*` authenticated responses or `T1`–`T3` turns; clear ephemeral client state immediately on logout or session expiry.
2. **2G Low-Data / Text-Only Mode (`shouldEnableLowDataMode`):**
   - Automatic detection via `Save-Data` header and `navigator.connection.effectiveType` (`slow-2g`, `2g`, `downlink < 0.5`, `rtt > 1000`), plus a persistent user toggle in the top header.
   - In Low-Data Mode, generative UI cards render as compact semantic HTML tables/lists, avatars/illustrations are suppressed, and the full interactive chat bundle loads only on interaction.
   - Offline Outbox (`OfflineOutboxQueue`) rejects any `T1`–`T4` query or message containing unmasked TINs, `+211` phone numbers, South Sudan National IDs (`[RP]\d{7,8}`), or email addresses.
3. **Performance Budget Enforcement in CI:**
   - First-load JS ≤ 150 KB gzip (target ≤ 120 KB) checked on every PR; Lighthouse CI checks LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1 on a throttled low-end Android profile.

## 5. Consequences

- **Positive:** Full Turbopack compatibility, tiny footprint (< 4 KB gzipped for `sw.js`), deterministic offline behaviour on 2G, and zero risk of caching sensitive taxpayer records on shared phones.
- **Negative / Trade-offs:** Pre-cache manifest revisions must be bumped via the build script (`tools/`) rather than a magic Webpack plugin.

## 6. Reversal Cost & Migration Path

- **Reversal Cost:** Low–Medium. If Serwist's native Turbopack integration offers measurable benefits later, `public/sw.js` can be replaced via standard Service Worker registration update semantics.
