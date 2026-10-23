# Phase R2-H Report: Long-Conversation Performance and Trusted Types

**Date:** 2026-10-24

**Status:** Source remediation implemented. Gate R2 has not been evaluated or approved.
**Scope:** AUD-029 (interaction latency in long conversations) and AUD-030 (Trusted Types enforcement) in `apps/web/server.js` and `apps/console/server.js`.

## Method

Interaction latency was measured with the Event Timing API (`PerformanceObserver`, `type: "event"`, entries with an `interactionId`). Each run used a loopback copy of the public chat, a 360×740 touch viewport, and Chrome DevTools Protocol CPU throttling at 4× and 6×. The scripted interactions were: open the rail, open a seeded synthetic conversation of 6 or 80 turns, type and send a question, and change the theme. "Worst" is the longest interaction duration in the run, the lab counterpart of INP's high percentile. A separate script timed each click on its own. These are lab measurements; field INP needs CrUX or real-user monitoring.

## Results

| Scenario | Before (R2-G) | After (R2-H) |
|---|---:|---:|
| 80 turns, 4× CPU, worst interaction | 256 ms | 120 ms |
| 80 turns, 6× CPU, worst interaction | 368 ms | 144 ms |
| 80 turns, 6× CPU, open the conversation | 240 ms | 152 ms |
| 80 turns, 6× CPU, send to rendered answer | 708 ms | 161 ms |
| 6 turns, 4× and 6× CPU, worst interaction | 72–88 ms | 56–128 ms (run-to-run noise; all under 100 ms at p75) |
| Lighthouse, public and staff mobile | 100 / 100 / 100 / 100 | 100 / 100 / 100 / 100 |
| Lighthouse `trusted-types-xss` | Severity High: no Trusted Types directive | No items |
| Served `/en` | 24,442 B Brotli | 25,812 B Brotli (budget 150 KB) |

The Core Web Vitals "good" INP threshold is 200 ms at the 75th percentile ([web.dev](https://web.dev/articles/vitals)).

## Implemented controls

- **Incremental transcript.** `renderTranscript()` keeps the HTML string of each rendered turn. It removes and rebuilds only from the first turn that changed, so a new reply no longer re-parses and re-lays-out the whole conversation. DOM-level state, such as a "Copied" label, also survives unrelated updates.
- **Progressive opening.** A long conversation paints its latest 30 turns first, then prepends older turns in 20-turn chunks between tasks. Before each chunk the latest turn's position is measured, and the scroll offset is corrected by any difference afterwards. Where the browser's scroll anchoring already held the position, the correction is zero.
- **`content-visibility: auto`** on message rows, with `contain-intrinsic-size: auto 160px`, so off-screen rows skip layout and paint and remember their last size. Content stays in the DOM and accessibility tree. `innerText` is empty for skipped rows, so tests read `textContent`, and the app's copy and speech features read state rather than `innerText`.
- **Rail.** Rewritten only when its HTML changes.
- **Trusted Types.** The CSP now ends with `require-trusted-types-for 'script'; trusted-types ssra-web-html ssra-web-script-url` on the public chat and `… trusted-types ssra-ops-html` on the staff preview. A sink inventory found only `innerHTML` through `setSafeHtml` and the service-worker registration. The `ssra-web-script-url` policy accepts only `/sw.js`. Trusted Types is supported in Chrome 83, Firefox 148, and Safari 26 ([web.dev](https://web.dev/articles/trusted-types)). Older browsers ignore the directive.

## Validation

| Check | Result |
|---|---|
| New `tests/browser/performance-hardening.spec.ts` on the R2-G code | 4 of 5 failed. Service-worker registration passed before and remains as a guard that enforcement does not break it |
| Full browser suite after R2-H | 45 of 45 passed, with no console errors under enforced Trusted Types |
| Biome, frontend verifier, SAST/DAST pipeline, `apps/web` and `apps/console` Vitest | Passed |

## Threat-model delta

- **Tightened:** DOM XSS. A string reaching any HTML or script-URL sink now throws in supporting browsers, and only the two named policies may create trusted values.
- **Unchanged:** the CSP nonce and `strict-dynamic`. The suggested `'unsafe-inline' https:` legacy fallback was not added, because it relaxes CSP and needs a human decision.

## Residual work

- Field INP and LCP from real devices (CrUX or RUM) once there is a deployment.
- AUD-031 (stale live smoke expectations), AUD-032 (URL locale versus saved locale), and AUD-033 (runtime relevance).
