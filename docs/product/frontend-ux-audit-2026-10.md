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
| P1 | Sidebar labeled all unpinned conversations “Today,” did not sort by activity, and could leave hidden rail controls in keyboard focus. | Added deterministic activity sorting and `Africa/Juba` date groups, active-row semantics, meaningful empty state, and `inert` handling for collapsed/closed navigation. |
| P1 | Compact action controls and motion/focus feedback were inconsistent. | Main chat rail actions now meet the 44px design target, visible keyboard focus is explicit, reduced-motion preferences are honored, and focus follows sidebar open/close state. |
| P1 | The chat header labeled a sample-prompt modal as a toll-free AI receptionist, and browser speech recognition did not disclose processing limits. | Renamed it to voice input, disclosed browser processing and language limits, and warned against speaking private account details in public chat. |
| P2 | Analytics view-model helpers treated values without observation timestamps as live. | Added `LIVE`, `STALE`, `UNKNOWN`, `CI target` and `illustrative` provenance states. Unknown or stale evidence cannot claim that all gates pass. |

## Remaining gaps

- Staff dashboards are intentionally not operational; there is no verified staff-session integration in the server-rendered console. OQ-014 blocks release of staff data and actions.
- OQ-013 remains open for warehouse aggregation and synthetic-baseline metadata. Current runtime UI does not use the newer TypeScript view models as its renderer, so integration must be completed before showing live metrics.
- Current code review cannot confirm that all generated layouts pass screen-reader, zoom, keyboard, 320px reflow, Arabic RTL, or low-end Android user scenarios. Automated accessibility results previously recorded in `docs/PROGRESS.md` must not be treated as a substitute for this review or moderated testing.
- Language coverage beyond English, Juba Arabic, and Arabic needs qualified human review. Do not publish improvised translations for tax/legal concepts.
- Forms and consequential flows need an end-to-end error pattern: server-side validation, preserved inputs, linked field errors, a focused error summary, and clear recovery instructions.

## Phased remediation

### Phase 1 — Trustworthy baseline (implemented in this branch)

- Remove client-selected taxpayer/staff identities from access decisions.
- Fail closed on staff APIs and label the staff shell as a non-operational preview.
- Show actual connection and citation state; never turn offline fallback into a source citation.
- Preserve drafts after network loss and state clearly when the request may have reached the server.
- Make sidebar recency, empty/search states, focus management, touch targets, and reduced-motion behavior predictable.
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

## Standards and research checked on 2026-10-21

- [W3C Web Content Accessibility Guidelines 2.2](https://www.w3.org/TR/WCAG22/) — normative accessibility baseline. Relevant criteria include reflow at 320 CSS pixels, keyboard focus visibility/not obscured, target size, and consistent help. The project’s 44px control target is a design target that exceeds the WCAG 2.2 AA minimum for most controls; it does not by itself prove conformance.
- [GOV.UK Design System: Error summary](https://design-system.service.gov.uk/components/error-summary/) — current guidance requires a linked summary and moving keyboard focus to it after validation errors.
- [GOV.UK Design System: Recover from validation errors](https://design-system.service.gov.uk/patterns/validation/) — server-side validation is always required; client-side validation may supplement it; preserve entered data so people can recover.
- [Australian Government Digital Service Standard](https://www.digital.gov.au/policy/digital-experience/digital-service-standard) — user-friendly, inclusive, adaptable, measurable services; criteria include trust, doing no harm, monitoring, and continuing to meet user needs.
- [Australian Government Digital Service Standard, criterion 7: Do no harm](https://www.digital.gov.au/policy/digital-experience/digital-service-standard/criterion-7) — understand privacy impacts, user rights, and limits of data using qualitative and quantitative evidence.

These sources support the standards above. The decision to hide unauthenticated staff data, require timestamped telemetry, and use Juba-time conversation groups is the project’s risk-based application of those standards.
