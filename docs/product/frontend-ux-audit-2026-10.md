# Frontend UX, Trust & Robustness Audit — October 2026

**Review date:** 2026-10-21
**Scope:** Public main chat and conversation sidebar; staff navigation and dashboards; browser-to-BFF trust boundaries.
**Review stance:** High-stakes public revenue service. This is a code and rendered-markup review, not a claim of completed moderated user research or a formal WCAG conformance audit.

## Findings and phase 1 changes

| Priority | Gap found | Phase 1 response |
|---|---|---|
| P0 | Public chat exposed sample taxpayer identities and a client-selected subject path. | Removed the sample identity selector and client-selected subject fields. Public turns are explicitly anonymous through `/api/turns`; direct `/v1/*` proxy requests are denied except feedback submission. |
| P0 | Staff role selection lived in browser storage; caller-supplied staff IDs were accepted by the BFF. | Renamed it as a preview persona, removed staff ID generation and requests, and made scorecard, flags, kill-switch and stack-status routes fail closed. |
| P0 | Dashboard samples and no-op buttons were presented as live service/case status and successful staff actions. | Staff pages now show a persistent preview notice and a no-data/no-actions screen. Buttons cannot report an unperformed action as successful. |
| P1 | Chat displayed fixed snapshot versions and source assurances while offline or regardless of response provenance. | Removed the hardcoded snapshot label/citation from offline fallback; network status describes connection state only. Answers render a source version only when the response supplies one. |
| P1 | A dropped connection could be mistaken for a failed request; the composer cleared the draft. | The message now says completion status may be unknown, restores the draft if the user has not started another one, and warns users not to repeat a consequential request before checking. |
| P1 | Sidebar labeled all unpinned conversations “Today,” did not sort by activity, and could leave hidden rail controls in keyboard focus. | Added deterministic activity sorting and `Africa/Juba` date groups, active-row semantics, meaningful empty state, `inert` handling for collapsed/closed navigation, and keyboard/pointer recovery for the staff preview's hover rail. |
| P1 | Compact action controls and motion/focus feedback were inconsistent. | Main chat rail actions now meet the 44px design target, visible keyboard focus is explicit, reduced-motion preferences are honored, and focus follows sidebar open/close state. |
| P1 | The chat header labeled a sample-prompt modal as a toll-free AI receptionist, and browser speech recognition did not disclose processing limits. | Renamed it to voice input, disclosed browser processing and language limits, and warned against speaking private account details in public chat. |
| P0 | Attachment inspection could generate TIN verification, portal instructions, and tax-rate/deadline prompts without an approved scan, OCR, or legal source. | Removed generated analysis prompts and assumed portal links; the inspection view now exposes an explicit unavailable state until approved providers return cited results. |
| P2 | Analytics view-model helpers treated values without observation timestamps as live. | Added `LIVE`, `STALE`, `UNKNOWN`, `CI target` and `illustrative` provenance states. Unknown or stale evidence cannot claim that all gates pass. |

## Remaining gaps

- Staff dashboards are intentionally not operational; there is no verified staff-session integration in the server-rendered console. OQ-014 blocks release of staff data and actions.
- OQ-013 remains open for warehouse aggregation and metric provenance. Analytics summary, insight, drift, and scorecard endpoints now return 503, and the staff console continues to return 403 for operational data/actions.
- `SSRA_RUNTIME_MODE` defaults to `production`; Core API and agent-runtime return 503 unless explicit local/test `reference` mode is selected. The production/DR Compose overlay remains unready until providers and durable state are approved and verified.
- R2-B rendered Chromium checks now cover selected 320px reflow, keyboard focus return, reduced motion, Arabic RTL, low-data/offline fallback, public BFF, and staff-preview paths. They do not confirm all generated layouts, screen-reader/assistive-technology use, zoom, low-end Android, real 2G, or moderated user scenarios. Automated results must not be treated as a substitute for this review or inclusive testing.
- Language coverage beyond English, Juba Arabic, and Arabic needs qualified human review. Do not publish improvised translations for tax/legal concepts.
- Forms and consequential flows need an end-to-end error pattern: server-side validation, preserved inputs, linked field errors, a focused error summary, and clear recovery instructions.

## Phased remediation

### Phase 1 — Trustworthy baseline (implemented in this branch)

- Remove client-selected taxpayer/staff identities from access decisions.
- Fail closed on staff APIs and label the staff shell as a non-operational preview.
- Show actual connection and citation state; never turn offline fallback into a source citation.
- Preserve drafts after network loss and state clearly when the request may have reached the server.
- Make sidebar recency, empty/search states, focus management, hover-mode re-pinning, touch targets, and reduced-motion behavior predictable.
- Describe browser speech recognition accurately, limit it to supported UI languages, and avoid implying an operational phone call.
- Add freshness-aware provenance to analytics view models.

### Phase 2 — Authorized staff operation (blocked by SSRA decisions)

- Resolve OQ-014 and OQ-013 with SSRA ICT, SecOps, Operations and analytics owners.
- Integrate server-verified OIDC/session identity and approved role claims; enforce permissions and step-up on each action at the server.
- Return metric source, observation time, window, and synthetic-baseline marker from APIs; show explicit live/stale/unavailable states.
- Add confirmations, idempotency, result receipts, audit linkage, and retry-safe recovery for reply, takeover, flags, and kill-switch operations.
- Keep all taxpayer examples synthetic and labeled in development environments.

### Phase 3 — Journey validation and inclusive language

- Conduct moderated task testing with taxpayers and staff, including low-literacy, assistive-technology, low-end Android, intermittent 2G, and RTL users. Obtain SSRA approval and consent; collect only minimal research notes.
- Validate first-turn discovery, citation comprehension, correction/retry, human handoff, sidebar retrieval, and staff case review. Review whether call/voice entry points need to be prominent on constrained screens.
- Have qualified speakers and legal reviewers approve `en`, `pga`, and `ar` strings; expand to national languages only when reviewed translations are available.
- Verify keyboard order, visible/non-obscured focus, modal focus containment/restoration, 320px reflow, 200%/400% zoom, contrast, touch target spacing, and reduced motion with assistive technology.

### Phase 4 — Measured optimization and resilience

- Establish privacy-preserving service measures for task completion, abandonment, handoff success, error recovery, latency, offline recovery, and language-specific outcomes.
- Optimize from measured journeys: progressive disclosure, concise answer structure, context-preserving retries, progressive loading, and low-data mode.
- Exercise API timeouts, stale cache, reconnection, duplicate submit, interrupted stream, and unavailable handoff. Require truthful status, safe abstention for unverified tax facts, and an actionable recovery route.
- Re-run performance and accessibility budgets on representative low-end hardware and slow networks; keep results tied to a build and test date.

### R2-B reference evidence (2026-10-22)

- Added a merge-blocking Playwright suite that starts only local synthetic loopback services and exercises the rendered public BFF, conversation rail, and staff-preview dashboard.
- Repaired the public and staff mobile drawer transitions so the drawer is focusable when it opens and keyboard focus returns predictably after Escape without overwriting a later user focus move. The staff command palette also has a rendered visible-focus assertion.
- Five clean browser-suite runs passed (25 rendered test executions). See [the R2-B report](../audit/phase-R2-B-browser-flow-report.md) and [the browser-flow runbook](../runbooks/browser-flow-assurance.md).
- The suite does not use live taxpayer/staff data, tax values, credentials, or provider endpoints. It provides no production-readiness or phase-exit claim.

## Re-audit 2026-10-23

**Scope:** The served public chat (`apps/web/server.js`) and staff preview dashboards (`packages/ui/ops-console.js`, `apps/console/server.js`) at commit `a30d9ee`.
**Method:** Code review, then reproduction in Chromium against a loopback synthetic scenario runtime, plus computed WCAG contrast for the theme tokens. No taxpayer data, credentials, or live endpoints were used. Each gap below was reproduced before it was recorded.

### Gaps found

| ID | Severity | Gap | Phase |
|---|---|---|---|
| [AUD-014](../audit/findings.md#aud-014--s1--grounded-ui--served-chat-renderer-bypasses-the-closed-component-registry-and-invents-missing-facts) | S1 | The served renderer bypassed the Zod registry. It filled missing props with invented facts: `COMPLIANT`, `FILED`, `Due: 15th`, `Mon–Fri 08:00–17:00`, a queue name, and a payment-policy line. It also rendered unregistered components. The runtime sends `HandoffCard` with only a `reason` on anonymous abstentions, so the invented hours reached public users. | R2-C |
| [AUD-015](../audit/findings.md#aud-015--s2--truthful-state--failed-turns-show-raw-error-bodies-or-misreport-the-cause) | S2 | Raw error JSON and `detail` text were shown as answers. An HTML `500` was reported as a lost connection. `Retry-After` was dropped, and there was no retry control. | R2-C |
| [AUD-016](../audit/findings.md#aud-016--s2--truthful-state--public-chat-shows-controls-and-metadata-it-cannot-back) | S2 | A confirmation button appeared that the BFF can never honour. Tier, intent, affect, and timing labels were shown to taxpayers. `Provenance Verified` came from a default-true flag. Copy and feedback overstated their results. | R2-C |
| [AUD-017](../audit/findings.md#aud-017--s3--session-hygiene--public-thread-identifiers-are-guessable) | S3 | Conversation identifiers were derived from timestamps. | R2-C |
| [AUD-018](../audit/findings.md#aud-018--s2--accessibility--announcements-and-widget-semantics-fall-short-of-wcag-22-and-aria-apg-patterns) | S2 | The whole message log was re-announced on every update, and the status line was hidden on phones. Menu, tab, and combobox semantics were incomplete. The UI used native `prompt` and `confirm`, offered an unconfirmed purge, and advertised shortcuts that do nothing. | R2-D, R2-F |
| [AUD-019](../audit/findings.md#aud-019--s2--accessibility--light-theme-status-text-fails-contrast-preview-status-is-styled-as-healthy) | S2 | In light theme, offline status contrast is 1.31:1 and the console "Preview only" label is 1.45–1.64:1. The preview state is styled as healthy green. | R2-D, R2-F |
| [AUD-020](../audit/findings.md#aud-020--s2--language-governance--ui-publishes-unreviewed-strings-for-phase-4-locales) | S2 | Unreviewed, script-mixed interface strings ship for five Phase 4 locales. Dinka support is advertised without evaluation. | R2-E |
| [AUD-021](../audit/findings.md#aud-021--s3--ai-transparency-and-privacy--no-persistent-ai-or-accuracy-notice-at-the-composer) | S3 | There is no AI or accuracy notice at the composer, and no warning against entering identifiers in public chat. | R2-E |
| [AUD-022](../audit/findings.md#aud-022--s3--low-bandwidth-and-resilience--low-data-mode-does-not-reduce-rendering-cost-no-no-script-path) | S3 | Low-data mode does not reduce rendering cost. There is no `<noscript>` path, `/healthz` leaks internal URLs, and Brotli quality 4 is larger than gzip for this page. | R2-E |
| [AUD-023](../audit/findings.md#aud-023--s3--dashboard-truthfulness--preview-navigation-describes-unavailable-capabilities-as-current) | S3 | Preview navigation describes live calls, live flags, and seal proofs that do not exist. | R2-F |

### Phased remediation (2026-10-23)

Each phase is one pull request. Each pull request includes rendered tests that fail on the previous code.

1. **R2-C: Truthful answers (implemented).** Close the public render boundary to public registered components with no defaults. Remove the confirmation control from anonymous chat. Show plain-language trust cues and citations that carry their effective date. Show truthful failure states with retry and draft restoration. Forward `Retry-After`. Use 128-bit thread identifiers, and return `400` for malformed BFF input.
2. **R2-D: Accessible interaction (public chat) (implemented).** Render the log incrementally, with a separate polite status region. Keep the status line visible on phones. Use the disclosure pattern for the account popover and the APG tabs pattern for Settings. Replace `prompt` and `confirm` with an in-page `<dialog>` opened by `showModal()`. Confirm every purge. Remove false shortcut hints. Fix light-theme status contrast. Add `forced-colors` support. Set speech language from the locale.
3. **R2-E: Language honesty, disclosure, and low-bandwidth (implemented).** Phase 4 locales use English interface text with a notice, and advertised languages match the evaluated set. Add AI, accuracy, and identifier warnings, with wording labelled pending OQ-009. Low-data mode and `prefers-reduced-transparency` remove blur, gradients, and animation. Add a `<noscript>` path, remove internal URLs from `/healthz`, and choose a measured compression setting.
4. **R2-F: Staff dashboards (implemented).** Apply the APG combobox pattern to the command palette. The account menu closes on Escape and returns focus. Make light-theme preview labels readable and style the preview state as a warning. Describe destinations as planned capabilities, and render the preview state on the server.

Still open after these phases: moderated research with taxpayers and staff, assistive-technology testing (NVDA, JAWS, TalkBack, VoiceOver), low-end Android and real 2G testing, reviewed `pga`, `ar`, and Phase 4 translations (OQ-008), statutory disclosure wording (OQ-009), contact-centre hours and channels (OQ-010 and OQ-011), staff identity (OQ-014), analytics provenance (OQ-013), and an approved automated accessibility scanner (OQ-012).

### Standards and research checked on 2026-10-23

- [WCAG 2.2](https://www.w3.org/TR/WCAG22/) remains the normative baseline. [WCAG 3.0](https://www.w3.org/TR/wcag-3.0/) is still a Working Draft, and W3C advises against citing it as a requirement.
- [WAI-ARIA APG combobox pattern](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/): an editable combobox keeps DOM focus on the input, sets `aria-expanded` and `aria-controls`, and moves `aria-activedescendant` across `option` elements with `aria-selected`.
- Practitioner guidance on streaming chat interfaces ([Atlassian Rovo issue ROVO-978](https://jira.atlassian.com/browse/ROVO-978); [accessible streaming chat UI](https://azukiazusa.dev/en/blog/accessible-streaming-chat-ui)) recommends a separate live region that announces short state changes, such as "response ready", instead of making the transcript itself a live region. No WCAG criterion addresses streaming text directly; SC 4.1.3 Status Messages is the closest. These are secondary sources, so R2-D still requires screen-reader testing.
- [GOV.UK Chat app design (GDS, 19 August 2026)](https://insidegovuk.blog.gov.uk/2026/08/19/designing-gov-uk-chat-for-the-gov-uk-app/): tells users up front that "AI can make mistakes", links each answer to its source, avoids imagery that overstates capability, and keeps the input usable at larger text sizes.
- EU AI Act Article 50(1) requires disclosure, from the first interaction, that a user is talking to an AI system. It applied from 2 August 2026; the Commission's guidelines are non-binding. South Sudan is not bound by it. It is used here only as a comparative benchmark until OQ-009 sets the required wording.
- [MDN: `HTMLDialogElement.closedBy`](https://developer.mozilla.org/docs/Web/API/HTMLDialogElement/closedBy) is not Baseline, and Safari does not support it. R2-D uses `showModal()` and handles backdrop dismissal explicitly.
- [Chrome: `prefers-reduced-transparency`](https://developer.chrome.com/blog/css-prefers-reduced-transparency) is supported from Chromium 118 but not in Safari. R2-E therefore also ties the same reduction to the explicit low-data setting.

## Accessibility, adaptability, responsiveness, and performance audit (2026-10-24)

Lighthouse 12.8.2 scored 100 for Performance, Accessibility, Best Practices, and SEO on the public and staff pages, so the earlier 100-score claim reproduces for the initial load. The default audit does not exercise saved history, phone layouts in use, larger text, long conversations, or DOM-XSS enforcement. A rendered lab audit found these gaps:

| ID | Gap | Phase |
|---|---|---|
| [AUD-025](../audit/findings.md#aud-025--s2--truthful-state--saved-conversations-never-appeared-after-a-reload) | Saved conversations never appeared after a reload | R2-G (fixed) |
| [AUD-026](../audit/findings.md#aud-026--s2--mobile-reflow--phone-layout-rules-were-overridden-by-the-base-stylesheet) | Phone rules were overridden by the base stylesheet: a 173 px header, a 40 px landscape transcript, and an unreachable language selector at 320 px and with 200 % text | R2-G (fixed) |
| [AUD-027](../audit/findings.md#aud-027--s3--accessibility--staff-mobile-menu-button-failed-label-in-name) | Staff "Menu" button failed Label in Name | R2-G (fixed) |
| [AUD-028](../audit/findings.md#aud-028--s3--adaptability--no-on-screen-keyboard-or-browser-theme-adaptation) | No `interactive-widget` or `theme-color` | R2-G (fixed) |
| [AUD-029](../audit/findings.md#aud-029--s2--interaction-performance--long-conversations-exceed-the-inp-threshold) | 80-turn conversations reach 272–344 ms interactions under CPU slowdown | R2-H (fixed) |
| [AUD-030](../audit/findings.md#aud-030--s2--dom-xss-hardening--trusted-types-are-created-but-not-enforced) | Trusted Types created but not enforced | R2-H (fixed) |
| [AUD-031](../audit/findings.md#aud-031--s3--regression-tooling--live-smoke-suite-asserts-behaviour-the-fail-closed-policy-forbids) | Live smoke suite expects statuses that the fail-closed policy forbids | Tooling PR |
| [AUD-032](../audit/findings.md#aud-032--s3--adaptability--a-saved-locale-overrides-the-locale-in-the-url) | A saved locale overrides `/ar` and other locale URLs | Open |
| [AUD-033](../audit/findings.md#aud-033--s3--answer-relevance--an-out-of-scope-question-received-unrelated-grounded-guidance) | An out-of-scope question received unrelated cited guidance | Open (runtime) |

Loading is not the bottleneck: on emulated 2G with 4× CPU the page is one 25 KB request with an LCP of 1.15 s. Measurements and research are in [the R2-G report](../audit/phase-R2-G-adaptive-layout-report.md).

## Standards and research checked on 2026-10-21

- [W3C Web Content Accessibility Guidelines 2.2](https://www.w3.org/TR/WCAG22/) — normative accessibility baseline. Relevant criteria include reflow at 320 CSS pixels, keyboard focus visibility/not obscured, target size, and consistent help. The project’s 44px control target is a design target that exceeds the WCAG 2.2 AA minimum for most controls; it does not by itself prove conformance.
- [GOV.UK Design System: Error summary](https://design-system.service.gov.uk/components/error-summary/) — current guidance requires a linked summary and moving keyboard focus to it after validation errors.
- [GOV.UK Design System: Recover from validation errors](https://design-system.service.gov.uk/patterns/validation/) — server-side validation is always required; client-side validation may supplement it; preserve entered data so people can recover.
- [Australian Government Digital Service Standard](https://www.digital.gov.au/policy/digital-experience/digital-service-standard) — user-friendly, inclusive, adaptable, measurable services; criteria include trust, doing no harm, monitoring, and continuing to meet user needs.
- [Australian Government Digital Service Standard, criterion 7: Do no harm](https://www.digital.gov.au/policy/digital-experience/digital-service-standard/criterion-7) — understand privacy impacts, user rights, and limits of data using qualitative and quantitative evidence.

These sources support the standards above. The decision to hide unauthenticated staff data, require timestamped telemetry, and use Juba-time conversation groups is the project’s risk-based application of those standards.
