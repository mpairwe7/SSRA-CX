# ADR-023: Public Chat Render Boundary and Truthful Failure States

- **Status:** Accepted as a repository safety baseline; not production authorization
- **Date:** 2026-10-23
- **Deciders:** SSRA Assist engineering maintainers
- **Reversal Cost:** Medium
- **Related:** [ADR-005](./0005-ag-ui-streaming-and-generative-ui-registry.md), [ADR-008](./0008-risk-tiered-autonomy-subject-binding-and-opa.md), [ADR-018](./0018-staff-console-preview-and-trusted-session-gate.md), [ADR-021](./0021-rendered-browser-assurance-and-synthetic-runtime.md), [AUD-014](../audit/findings.md#aud-014--s1--grounded-ui--served-chat-renderer-bypasses-the-closed-component-registry-and-invents-missing-facts) to [AUD-017](../audit/findings.md#aud-017--s3--session-hygiene--public-thread-identifiers-are-guessable), [R2-C report](../audit/phase-R2-C-truthful-answer-report.md)

## Context

ADR-005 defines a closed, Zod-validated registry of seven Generative UI components in `packages/chat-ui`. The served public chat is an inline browser script in `apps/web/server.js`. It cannot import that TypeScript registry, so it had its own renderer. That renderer matched props by duck typing, filled missing fields with defaults, and rendered any component name. The runtime sends `HandoffCard` with only a `reason` on anonymous abstentions, so public users saw invented contact hours. A missing `filing_status` was shown as `COMPLIANT`.

The public BFF forces `auth_level: "ANONYMOUS"` and strips confirmation tokens. Personal (T1) cards and action (T2) confirmations therefore never belong in this channel. A confirmation button there can never execute.

Failure handling had the same problem. Error bodies, HTTP statuses, and network failures were shown as answers or misreported.

## Options Considered

1. Bundle the Zod registry into the inline script. This adds a build step and dependency surface to the Node BFF shell that ADR-020 deliberately avoided.
2. Validate on the BFF by mirroring the registry. This creates a second schema source that can drift.
3. Close the browser render boundary to the components valid in anonymous chat, applying the registry's required-field rules without defaults, and add rendered tests that fail if a default or an unlisted component reappears.

## Decision

1. Public chat renders only `CitationList` guided steps, `CalculatorForm`, `PaymentInstructionsCard`, and `HandoffCard`. Required fields follow `packages/chat-ui` schemas. A missing or invalid value hides the card; it is never replaced with a default.
2. `BalanceCard`, `FilingStatusTimeline`, `ConfirmActionSheet`, and any `pending_confirmation` render a sign-in notice that points to the official e-Tax portal. No action control is rendered. Unknown component names render nothing.
3. A `CalculatorForm` amount is shown only with `is_estimate: true`, an "Estimate only" label, and at least one approved source in the same reply. Without a source, the card says that an estimate cannot be shown.
4. `HandoffCard` says that an officer needs to answer. It makes no claim about availability, queue, or hours until OQ-010 supplies approved values.
5. Trust cues replace internal telemetry. They show the approved-source count, `No source cited`, `Not fully verified` (only when `outcome_verified` is explicitly `false`), and `Estimate`. Citations show title, anchor, effective date, version, and an `https` link when one is supplied.
6. Failure states describe what the client knows: not sent (offline), not answered (an HTTP status), may not have been answered (timeout or dropped upstream), or stopped by the user. The draft is restored when the composer is empty, and `Try again` resends the same anonymous question. The BFF forwards only a delta-seconds `Retry-After` and returns `400` for malformed bodies and thread identifiers.
7. New public thread identifiers carry 128 random bits.

## Consequences

- Public users can no longer see a status, deadline, office hour, queue, or payment-policy line that the runtime did not supply.
- Any new public component needs a renderer change and a rendered test. Adding one to the runtime alone does not make it appear.
- The `packages/chat-ui` registry remains the schema authority. The public renderer is a stricter subset, not a second schema. A renderer that relaxed a registry rule would be a defect.
- Some valid runtime replies now show less: an estimate without a source and a handoff without contact details. This is intended until the runtime or SSRA supplies grounded values.

## Reversal Cost

Restoring the permissive renderer would re-open AUD-014 and AUD-016 and require new legal-content review. Moving to option 1 or option 2 later would replace this subset with a shared validator; the rendered tests would still apply.

## Verification

`tests/browser/public-chat-answers.spec.ts` covers every decision above against the synthetic scenarios in `tests/browser/mock-runtime.mjs`. Those tests fail on commit `a30d9ee` and pass after this change. The R2-C report records the run evidence.
