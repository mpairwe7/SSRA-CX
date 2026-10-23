# Phase R2-G Report: Adaptive Layout, Reflow, and Saved History

**Date:** 2026-10-24

**Status:** Source remediation implemented. Gate R2 has not been evaluated or approved.
**Scope:** AUD-025 to AUD-028 in `apps/web/server.js` and `packages/ui/ops-console.js`. AUD-029 to AUD-033 are recorded for later phases.

## Method and evidence boundary

1. **Lighthouse 12.8.2**, mobile and desktop presets, run against the live GPU profile (`:3033` public web, `:3034` staff preview) at `f9c8861`. Lighthouse ran from a local npm cache: Apache-2.0, installed 2026-05-25 from `registry.npmjs.org` with an integrity hash. It was attached to Playwright Chromium 145 through a CDP port and was not added as a repository dependency. Lighthouse 13 (2025-10-10) moved performance audits to insights; the metrics, and the accessibility, best-practice, and SEO audits used here, are unchanged.
2. **Playwright lab audit** against loopback copies of the same merged servers with the synthetic runtime. It covered ten viewports (320×568 to 1920×1080, including two landscape phones); WCAG 1.4.12 text spacing and 200 % text, both applied as user styles; pointer targets under 24×24 px; Event Timing under 4× and 6× CPU slowdown with 6 and 80 synthetic turns; emulated 2G (250 kb/s, 800 ms RTT) and 3G loads; and back/forward cache with Chrome's `Page.backForwardCacheNotUsed` reasons. The live stack was taken down by another session mid-run, so the lab audit used isolated loopback servers. Layout and interaction behaviour are client-side and unaffected.

Automated checks do not establish WCAG conformance. Screen-reader testing, real-device keyboard behaviour, and low-end Android field data are still required.

## Baseline results

| Check | Result at `f9c8861` |
|---|---|
| Lighthouse, public `/en` and `/ar` mobile, `/en` desktop, staff mobile and desktop | 100 / 100 / 100 / 100 on every page; mobile LCP 0.8–0.9 s, TBT 0 ms, CLS 0 |
| Lighthouse unweighted audits | Staff `label-content-name-mismatch` = 0 (AUD-027); `trusted-types-xss` severity High (AUD-030); one 64 ms long task at load |
| 2G with 4× CPU | One 25 KB request; FCP 1.12 s, LCP 1.15 s, DOM interactive 1.68 s |
| 3G with 4× CPU | FCP 0.45 s, LCP 0.50 s |
| Back/forward cache | Only blocker reported: `Circumstantial:BrowsingInstanceNotSwapped`, a test-harness artifact. No page-attributable blocker, and `Cache-Control: no-store` is not listed (Chrome allows no-store pages into the bfcache) |
| Interaction latency, 80 turns | Worst 272 ms at 4× and 344 ms at 6× CPU; above the 200 ms INP threshold (AUD-029) |
| Responsive and text adaptation | See AUD-025 and AUD-026 |

## Implemented controls

- **Saved history on load (AUD-025).** One `renderApp()` call at the end of start-up.
- **Cascade order (AUD-026).** The phone and short-screen rules now follow the base rules, so they take effect. Before this, most of the 640 px overrides, including an intended status-badge rule, never applied.
- **Phone header.** At 640 px or less, a two-row grid: rail toggle, title (ellipsis), voice and theme icons; then the connection status and a compact language selector. Header button text collapses to icons, and each button keeps its accessible name.
- **Short screens (500 px tall or less).** The whole column scrolls. The transcript is no longer a nested scroller squeezed between the header and the composer, and new replies scroll into view in whichever container scrolls.
- **Wrapping.** Long URLs and references wrap in bubbles, sample prompts, citations, cards, and notices.
- **Keyboard and browser UI (AUD-028).** `interactive-widget=resizes-content` and light and dark `theme-color` metas that follow the chosen theme.
- **Label in Name (AUD-027).** The staff mobile "Menu" button's accessible name is its visible text.

## After the fix

| Viewport | Transcript area before → after | Header before → after |
|---|---|---|
| 320×568 | 157 px (28 %) → 248 px (44 %) | 173 → 107 px |
| 360×740 | 346 px (47 %) → 420 px (57 %) | 173 → 107 px |
| 568×320 | 40 px (13 %) → full-height scrolling column | 121 → 107 px |
| 740×360 | 105 px (29 %) → full-height scrolling column | 69 px |

The lab audit now reports no off-screen controls, text-spacing failures, or 200 %-text failures on either surface. Lighthouse still scores 100 in every category, and the staff Label-in-Name audit no longer finds a mismatched control.

## Standards and research (checked 2026-10-23 and 2026-10-24)

- [WCAG 2.2](https://www.w3.org/TR/WCAG22/) SC 1.4.4, 1.4.10, 1.4.12, 2.5.3, 2.5.8, and 3.2.4.
- [web.dev Core Web Vitals](https://web.dev/articles/vitals): LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1 at the 75th percentile. No change is documented for 2025–2026.
- [Lighthouse 13](https://developer.chrome.com/blog/lighthouse-13-0): performance audits replaced by insights; accessibility, SEO, and best practices unaffected.
- [Chrome: viewport resize behaviour](https://developer.chrome.com/blog/viewport-resize-behavior) and [MDN viewport meta](https://developer.mozilla.org/en-US/docs/Web/HTML/Guides/Viewport_meta_element): `interactive-widget=resizes-content` (Chrome 108+).
- [Chrome: bfcache for `Cache-Control: no-store`](https://developer.chrome.com/docs/web-platform/bfcache-ccns): allowed unless cookies change.
- [web.dev Trusted Types](https://web.dev/articles/trusted-types): supported in Chrome 83, Firefox 148, and Safari 26 (AUD-030, R2-H).

## Validation

| Check | Result |
|---|---|
| New `tests/browser/responsive-adaptive.spec.ts` on `f9c8861` | 7 of 9 failed; the two 360×740 and 568×320 reachability tests passed before and remain as guards |
| Full browser suite after R2-G | 40 of 40 passed |
| Lighthouse after R2-G (web mobile and desktop, staff mobile) | 100 / 100 / 100 / 100 |
| Biome, frontend verifier, SAST/DAST pipeline | Passed |

## Decision needed from a human

Lighthouse suggests adding `'unsafe-inline' https:` to `script-src` as a fallback for browsers without nonce support. That is Google's strict-CSP compatibility pattern, but it relaxes CSP in those browsers. AGENTS.md requires a human decision before any security control is relaxed, so this was not changed.

## Residual work

- R2-H: AUD-029 (long-conversation interaction latency) and AUD-030 (Trusted Types enforcement).
- Tooling pull request: AUD-031 (stale smoke expectations and benchmark report labels).
- Open: AUD-032 (URL locale versus saved locale) and AUD-033 (runtime relevance on out-of-scope questions).
- Real-device keyboard and assistive-technology testing.
