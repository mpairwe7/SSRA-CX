# Phase R2-C Report: Truthful Public Answer Rendering

**Date:** 2026-10-23

**Status:** Source remediation implemented. Gate R2 has not been evaluated or approved.
**Scope:** AUD-014 to AUD-017 in the served public chat (`apps/web/server.js`) and its BFF turn proxy.

## Scope and evidence boundary

Gate R1 approval permits non-production R2 reference remediation. All evidence comes from local Chromium runs against loopback synthetic services. The synthetic scenarios use placeholder values (`111`, `999`, `2000-01-01`, `example.invalid`) that are not tax facts. This report makes no claim about production readiness, legal content, staff identity, or any later phase.

## What was wrong

| Finding | Reproduced at `a30d9ee` |
|---|---|
| AUD-014 (S1) | A `HandoffCard` with only `reason` showed `Domestic Taxes Desk · Duty Hours: Mon–Fri 08:00–17:00 CAT`. A balance card without `filing_status` showed `COMPLIANT`. A period without status or date showed `FILED (Due: 15th CAT)`. An unregistered component name rendered a `Cash-Free Policy` line. The runtime sends reason-only `HandoffCard`s on anonymous abstentions (`compose.py`), so the invented hours reached public users. |
| AUD-015 (S2) | A `503` showed the runtime's `detail`. A `429` and a BFF upstream failure showed raw JSON. An HTML `500` was reported as a lost connection. `Retry-After` was dropped. `null` and array bodies returned `502`. |
| AUD-016 (S2) | `Confirm & Execute <tool>` was rendered although the BFF strips confirmation tokens. Tier, intent slug, `EQ: …`, and `Thought for N ms` were shown on every answer. `Provenance Verified` came from a default-true flag. Copy reported `Copied` after a rejected write. Feedback reported `Flagged for Audit`. |
| AUD-017 (S3) | Thread identifiers looked like `thr_web_mvksx6ee`, derived from `Date.now()`. |

## Implemented controls

- **Closed public render boundary** ([ADR-023](../adr/0023-public-chat-render-boundary-and-truthful-failure-states.md)). Only `CitationList` steps, `CalculatorForm`, `PaymentInstructionsCard`, and `HandoffCard` render, using the registry's required fields with no defaults. Personal and action cards show a sign-in notice. Unknown names render nothing.
- **Estimates need provenance.** An amount appears only with `is_estimate: true`, the label "Estimate only. It is not an official assessment.", and at least one approved source in the same reply.
- **Handoff without invented facts.** The card says that an officer needs to answer and that availability and hours cannot be confirmed here (OQ-010).
- **Trust cues and citations.** Approved-source count, `No source cited`, `Not fully verified` (explicit `false` only), and `Estimate`. Citations show title, anchor, effective date, version, and an `https` link.
- **Failure states.** Each state says what is known: not sent (offline), not answered (with the HTTP status mapped to a plain explanation), may not have been answered (timeout or dropped upstream), or stopped by the user. A 30-second client timeout applies. The draft is restored when the composer is empty, and `Try again` resends the same anonymous question.
- **BFF.** Forwards only a delta-seconds `Retry-After`. Returns `400` for non-object bodies and for thread identifiers that fail the runtime's `^[A-Za-z0-9_:-]{1,128}$` rule.
- **Thread identifiers.** 128 bits from `crypto.getRandomValues`, which works outside secure contexts.
- **Browser flake root cause.** Chromium keeps its temporary profile under `TMPDIR`, which on this host is a CIFS network share. A loop of trivial `setContent` page loads failed 1 in 264 times on the CIFS `TMPDIR`, and `browser.close()` hung. The same loop on local disk passed 3,508 of 3,508. `task test` now sets `TMPDIR=/tmp` for Playwright, the same guard it already applies to pytest. This also cut the suite time from about 48 s to about 8 s.
- **Test isolation.** `SSRA_BROWSER_TEST_PORT_BASE` lets a second copy of the suite run on other loopback ports. During this work, a concurrent session on the same host used the default ports.

## Standards and design references

- Master prompt invariants 2, 4, 5, 9, and 10; OQ-009 and OQ-010 remain open.
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/) SC 3.3.1 and 3.3.3 for error identification and suggestion.
- RFC 9110 §10.2.3 for `Retry-After`.
- OWASP Top 10 for LLM Applications 2025 LLM05 (improper output handling); OWASP Top 10 for Agentic Applications 2026 ASI09 (human-agent trust exploitation).
- [GOV.UK Chat app design (GDS, 19 August 2026)](https://insidegovuk.blog.gov.uk/2026/08/19/designing-gov-uk-chat-for-the-gov-uk-app/) for source-linked answers and an interface that does not overstate capability.

## Validation

| Check | Result |
|---|---|
| New rendered tests on unfixed `a30d9ee` `server.js` | 6 of 6 failed, as intended |
| Full browser suite after the fix | 11 of 11 passed |
| Flake evidence (five full-suite runs, local `TMPDIR`) | Passed: 5 clean runs, 55 executions, 7.4–8.4 s per run |
| Flake evidence with `TMPDIR` on a CIFS share | 2 of 5 runs had one Chromium target crash (`net::ERR_ABORTED`, `Target … has been closed`) in unchanged staff-console tests; 46.6 s–1.3 min per run |
| Biome (`apps`, `packages`, `tests`, `playwright.config.ts`) and workspace `tsc` | Passed |
| `tools/verify_frontend_budgets_and_a11y.py` | Passed |
| `tools/run_sast_dast_sec_pipeline.py` (SAST-FE-01 single `innerHTML` sink, BFF DAST-10) | Passed |
| Served `/en` size (gzip) | 22,777 bytes before; 24,174 bytes after; budget 150 KB |

## Threat-model delta

- **Removed:** anonymous users seeing invented SSRA facts; a dead action control that suggests public chat can execute account actions; internal affect and intent labels shown to the subject they describe; guessable conversation keys.
- **Unchanged:** the BFF still forces anonymous identity and strips confirmation tokens. The runtime's `numeric_provenance` validator remains the primary numeric control; the UI rule is defence in depth.
- **New surface:** none. No dependency, route, or storage key was added. Citation links render only `https://` URLs supplied by the runtime.

## Residual work

- AUD-018 to AUD-023 are planned for R2-D, R2-E, and R2-F.
- Server-side binding of anonymous threads to an HttpOnly session (ADR-012).
- OQ-010 must supply approved contact options before a handoff can show hours or channels.
- Manual screen-reader verification of the new states is part of R2-D.
