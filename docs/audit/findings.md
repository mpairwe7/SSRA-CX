# R0 Findings Register

**Baseline commit:** 7ca1f26e83b08decf64eacf02af059b537e69db7

**Status convention:** R0 findings were opened with evidence only. Each finding's `Status` line records later remediation; a closed finding still makes no production-readiness claim.

## Severity summary

| Severity | Count | IDs |
|---|---:|---|
| S0 | 0 | None |
| S1 | 4 | AUD-001, AUD-002, AUD-003, AUD-014 |
| S2 | 15 | AUD-004 through AUD-012, AUD-015, AUD-016, AUD-018, AUD-019, AUD-020, AUD-024 |
| S3 | 5 | AUD-013, AUD-017, AUD-021, AUD-022, AUD-023 |

### AUD-001 · S1 · Runtime durability · Conversation state is process-local

- Location: services/agent-runtime/src/ssra_runtime/graphs/conversation.py:14, 118–129, 389–440; services/agent-runtime/src/ssra_runtime/memory.py:132 onward.
- Evidence: rg -n "InMemorySaver|checkpointer|_thread_subject|_pending_by_thread|_workflow_stack|_checkpoint_state" services/agent-runtime/src services/agent-runtime/tests identifies InMemorySaver and four in-process dictionaries. Existing continuation tests use the same runtime instance; no restart-and-resume test was found.
- Standard: OWASP Agentic 2026 ASI06 and ASI08; OWASP ASVS v5.0.0-16.5.2; NIST SSDF v1.1 PW.8.
- Impact: A restart or replica change loses a pending confirmation, subject/thread binding, workflow stack, and active checkpoint. A T2/T3 conversation cannot demonstrate single, safe continuation.
- Fix: Use a PostgreSQL LangGraph checkpointer outside unit tests; move subject binding, pending confirmation state, replay, preferences, and goal state to durable, subject-scoped stores. Define retention and RLS under OQ-015.
- Verification: Kill a runtime during a T2 interrupt, start a fresh instance, resume once with the original token and idempotency key, and prove cross-subject replay fails.
- Phase: R3 · Owner: Backend and Security Engineering · Estimated PRs: 2–3 · Status: Open.

### AUD-002 · S1 · Egress boundary · GPU profile bypasses the governed gateway

- Location: infra/compose/docker-compose.gpu.yml:279–282; infra/compose/docker-compose.gpu.yml lacks an agentgateway service. The general profile declares agentgateway at infra/compose/docker-compose.yml:158–175.
- Evidence: rg -n "agentgateway|VLLM_BASE_URL|REASONER_BASE_URL|ORPHEUS_TTS_URL" infra/compose confirms direct runtime URLs in the GPU profile and agentgateway only in the general profile.
- Standard: OWASP ASVS v5.0.0-15.2.5 and v5.0.0-16.5.2; OWASP Agentic 2026 ASI02, ASI03, and ASI08; OWASP MCP Top 10 MCP07/MCP08 advisory mapping; NSA MCP guidance on authenticated, bound requests and untrusted tool output.
- Impact: Model and tool egress controls, spend limits, token exchange, audit emission, kill switches, and tool-description enforcement cannot be proven for the GPU topology.
- Fix: Route GPU runtime model and MCP calls through agentgateway or an equivalently governed service. Restrict runtime DNS/network egress so direct model and MCP destinations are unreachable.
- Verification: Compose E2E test proves a runtime request succeeds through the gateway and fails when addressed directly to a model or MCP host.
- Phase: R3 · Owner: Platform and Agent Runtime · Estimated PRs: 2 · Status: Open.

### AUD-003 · S1 · Event durability · Core API has no transactional outbox

- Location: services/api/src/ssra_api/outbox.py:48–122; services/api/src/ssra_api/conversations/application/__init__.py; services/api/src/ssra_api/cases/application/__init__.py; services/api/alembic/versions/0001_initial_core_entities.py.
- Evidence: rg -n "InMemoryOutboxBuffer|stage_domain_event" services/api/src services/api/tests shows a process-local buffer. The migration has schema intent, but R0 found no runtime publisher or transaction coupling state mutation and event persistence.
- Standard: OWASP Agentic 2026 ASI08; OWASP ASVS v5.0.0-16.5.2; NIST SSDF v1.1 PW.8.
- Impact: Process death can lose events, duplicate downstream effects, and orphan SLA or audit activity. The transactional-outbox architecture claim is not true at runtime.
- Fix: Persist domain state and outbox event in one PostgreSQL transaction; publish through durable NATS JetStream with idempotent consumers and a reconciliation path.
- Verification: Fault-injection test crashes after database commit and before publish, then proves eventual single handling after restart.
- Phase: R3 · Owner: Core API and Platform · Estimated PRs: 2–3 · Status: Open.

### AUD-004 · S2 · Consent and subject governance · Reference stores are transient and accept body/path subject references

- Location: services/api/src/ssra_api/consent/application/__init__.py:10–54; services/api/src/ssra_api/consent/api/__init__.py:22–104; services/api/src/ssra_api/main.py:31–55.
- Evidence: rg -n "_pref_store|record_consent|subject_ref" services/api/src shows a module dictionary and request models with subject_ref. Production middleware returns 503 unless explicit reference mode is configured.
- Standard: OWASP ASVS v5.0.0-4.1.3 and v5.0.0-15.3.3; OWASP Agentic 2026 ASI03 and ASI06; NIST SSDF v1.1 PW.8.
- Impact: Current production posture is fail closed, but reference behavior cannot prove durable consent or server-bound ownership. Enabling it outside tightly controlled local fixtures would make consent evidence and access binding unsafe.
- Fix: Bind subject from verified server-side identity only; persist consent and preferences under RLS with an immutable audit record. Keep reference routes blocked until this is complete.
- Verification: Restart test proves STOP/opt-out persists; forged body and path subject values cannot read, change, or delete another subject's state.
- Phase: R3 · Owner: Core API, Identity, and Privacy Engineering · Estimated PRs: 2 · Status: Open.

### AUD-005 · S2 · Platform hardening · GPU Compose profile is not equivalent to the hardened baseline

- Location: infra/compose/docker-compose.gpu.yml:16, 148, 175, 178, 279–282; compare infra/compose/docker-compose.yml:1–21 and docker-compose.prod.yml:31–101.
- Evidence: Static scan finds a tag-pinned Orpheus image, an unpinned PostgreSQL variable default, env_file use, and services outside the general hardened defaults. The general profile uses digest-pinned images and a hardened anchor; R0 could not render Compose because the local plugin failed.
- Standard: OWASP ASVS v5.0.0-15.2.5 and v5.0.0-16.5.2; CIS Docker Benchmark intent; NIST SSDF v1.1 PO.3.
- Impact: GPU deployment cannot inherit the security and reproducibility assertions claimed for the general/production topology.
- Fix: Make every GPU service use digest-pinned images, non-root users, read-only filesystems with bounded writable mounts, dropped capabilities, no-new-privileges, resource limits, health checks, internal networks, and file/OpenBao-managed secrets.
- Verification: Rendered profile passes a policy linter; negative tests detect a tag image, missing hardening field, external port, Docker socket, or environment secret.
- Phase: R4, with digest remediation in R1 · Owner: Platform Security · Estimated PRs: 2 · Status: Open.

### AUD-006 · S2 · CI assurance · Supply-chain checks are incomplete and workflow review is not protected

- Location: .github/workflows/ci.yml; .github/CODEOWNERS; tools/verify_supply_chain_and_signatures.py; libs/ssra_security/tests/test_supply_chain_policy.py.
- Evidence: R1-A adds workflow-default `permissions: {}`, explicit least-privilege job permissions, a `.github/workflows/**` SecOps ownership rule, full-reachable-history Gitleaks, and a pinned zizmor gate. The repository verifier rejects every valid `pull_request_target` form, mutable action tags, missing workflow permissions, and persisted checkout credentials across `.yml` and `.yaml` workflows. Merged PR #71 passed the full required CI set, including the new full-history secret scan and workflow-security scan.
- Standard: SLSA v1.2 Build L3; NIST SSDF v1.1 PO.3, PW.7, and RV.1; OWASP ASVS v5.0.0-15.1.2 and v5.0.0-15.2.1.
- Impact: A future workflow regression, history secret, or unsafe workflow pattern can merge without the required second-control and security-owner review.
- Fix: Implemented in R1-A. CI runs the required checks; repository branch protection still needs external evidence that it enforces the workflow ownership rule before this finding can be marked fully remediated.
- Verification: The local verifier and adversarial fixtures cover tag actions, missing permissions, all `pull_request_target` forms, and `.yaml` workflow coverage. PR #71 supplied passing full-history and workflow-audit CI evidence.
- Phase: R1 · Owner: DevSecOps · Estimated PRs: 2 · Status: Implemented and CI verified; branch-protection evidence pending.

### AUD-007 · S2 · Artifact and dependency integrity · Cooldown and image-verification claims are only partial

- Location: pnpm-workspace.yaml; package.json; pyproject.toml; uv.lock; docs/runbooks/dependency-security-exceptions.md; mcp-servers/*/Dockerfile; infra/observability/slsa-provenance-v1.json; tools/verify_supply_chain_and_signatures.py.
- Evidence: R1-A enforces pnpm's rolling seven-day age, provenance downgrade protection, exotic-subdependency blocking, and an empty reviewed build-script allow-list. uv uses a rolling one-week limit, pins its resolver version, and retains the span in `uv.lock`. Dependabot holds pnpm, uv, and Actions version updates for seven days. DEP-EXC-001 records the resolver fix; DEP-EXC-002 permits only the Critical-advisory `certifi` 2026.10.19 release with exact source/wheel hashes and a fixed expiry cutoff. Eleven MCP Dockerfiles still use `python:3.14-slim` by tag, and no approved production image/model signature verifier or trust root exists.
- Standard: SLSA v1.2 Build L3; NIST SSDF v1.1 PO.3 and PS.3; OWASP ASVS v5.0.0-15.1.2, v5.0.0-15.2.1, and v5.0.0-15.2.4; CycloneDX 1.7; OpenSSF Model Signing.
- Impact: Lockfiles and some digest pins provide protection, but artifacts and models cannot be shown to be signed, verified, or safely refreshed. Tag resolution makes future builds non-reproducible.
- Fix: R1-A implements the dependency-policy portion, Dependabot cooldown, and a bounded security-fix procedure. Digest-pinning every Dockerfile base, per-image SBOMs, signing, registry trust, and pre-start image/model verification remain blocked by OQ-018.
- Verification: Repository policy checks the rolling cooldowns, exact tool pin, the sole fixed `certifi` exception, and its source/wheel hashes. A tag-base, unsigned, or retagged image/model test remains future work after OQ-018 selects the trust model.
- Phase: R1 · Owner: DevSecOps and Platform · Estimated PRs: 3 · Status: Partially remediated in R1-A; OQ-018 remains open.

### AUD-008 · S2 · Frontend dependency hygiene · Next.js configuration is stale and advisory posture is ambiguous

- Location: apps/web/server.js; apps/console/server.js; apps/web/package.json; apps/console/package.json; apps/web/Dockerfile; apps/console/Dockerfile; ADR-020.
- Evidence: R1-A removes both stale `next.config.ts` files and unused Next telemetry settings. The application manifests do not declare Next.js, and containers explicitly start their Node BFF servers. The repository verifier rejects a reintroduced configuration file or undeclared framework/runtime mismatch.
- Standard: OWASP ASVS v5.0.0-15.1.1 and v5.0.0-15.2.1; NIST SSDF v1.1 PO.3 and PW.7. The 14 October 2026 official Next.js advisory is not applicable to a currently served Next package, but the stale configuration prevents a durable proof of that status.
- Impact: Security response and user-interface maintenance can target the wrong runtime. A future build may unintentionally introduce an affected Next version or Cache Components without an explicit dependency decision.
- Fix: Implemented in R1-A through ADR-020. Any future framework adoption needs an explicit dependency, container, security-review, and test decision.
- Verification: The local verifier checks manifests and container commands; PR #71 CI passed the complete repository gate.
- Phase: R1 · Owner: Frontend and DevSecOps · Estimated PRs: 1 · Status: Implemented and CI verified.

### AUD-009 · S2 · Quality and UX assurance · Browser-flow and flake gates remain partially implemented

- Location: `Taskfile.yml`; `playwright.config.ts`; `tests/browser/`; `apps/web/server.js`; `packages/ui/ops-console.js`; `services/api/tests/test_route_matrix.py`.
- Evidence: R2-A provides a safe synthetic OpenAPI matrix for all 35 Core API operations across 32 paths, with independent reference-status policy checks and fail-closed production-mode behavior. R2-B adds a merge-blocking Playwright suite against fresh loopback public BFF, staff-preview, and synthetic-runtime processes. It verifies anonymous payload canonicalisation, forged identity/header stripping, direct and encoded protected-path rejection, public/staff drawer focus return, 320 CSS-pixel reflow, target size, reduced motion, Arabic RTL, low-data/offline safe fallback, preserved draft, and staff `403`/`no-store` preview denial. Five clean full-suite runs passed on 2026-10-22 (25 rendered test executions). The synthetic runtime contains no live data, statutory figures, credentials, or production provider calls.
- Standard: WCAG 2.2 AA SC 1.4.10, 2.4.3, 2.4.7, 2.4.11, 2.4.13, and 2.5.8 inform the targeted rendered checks; OWASP ASVS v5.0.0-4.1.3; NIST SSDF v1.1 PW.8. Rendered checks are not a conformance claim.
- Impact: The covered main-chat, conversation-rail, BFF, and staff-preview paths now fail before merge when their tested safety and interaction behavior regresses. Untested device, network, accessibility, and API-fuzzing paths remain possible regression sources.
- Fix: R2-A implements the Core API production/reference route matrix and cache protection. R2-B implements rendered Chromium evidence and five-run browser flake evidence. Remaining work includes Schemathesis/reference API fuzzing, supported mutation evidence, real 2G/low-end-device testing, visual baselines, offline-queue coverage, manual assistive-technology testing, and inclusive user research. `@axe-core/playwright` is not adopted because its MPL-2.0 license requires OQ-012 approval.
- Verification: `task test` executes the browser suite and CI installs Chromium from the exact lock-pinned Playwright package. Failure artifacts are retained for diagnostics. [The R2-B report](./phase-R2-B-browser-flow-report.md) records scope and five-run evidence.
- Phase: R2 · Owner: QA and Frontend · Estimated PRs: 2–3 · Status: Partially implemented in R2-A and R2-B.

### AUD-010 · S2 · MCP deployment · Gateway configuration names services that Compose does not run

- Location: infra/gateway/routes.yaml:34–67; infra/compose/docker-compose.yml; infra/compose/docker-compose.gpu.yml.
- Evidence: routes.yaml names 11 mcp-* upstream hosts. The general profile contains agentgateway but does not declare all 11 MCP containers; the GPU profile declares neither gateway nor MCP services. Current gateway tests instantiate servers in-process.
- Standard: OWASP ASVS v5.0.0-15.2.5; OWASP MCP Top 10 MCP03, MCP06–MCP08 advisory mapping; OWASP Agentic 2026 ASI02, ASI03, and ASI08; NSA MCP guidance.
- Impact: Per-tool authentication, gateway routing, network egress, audit propagation, and error behavior are not proven in a deployable topology.
- Fix: Declare or externally provision all MCP endpoints for each supported profile, document ownership and health checks, and execute one T1 and one rejected T2 call through the running gateway.
- Verification: Compose/integration test resolves every configured host, validates the requested audience/subject binding, and rejects a direct runtime-to-tool request.
- Phase: R3 · Owner: Platform and MCP Engineering · Estimated PRs: 2 · Status: Open.

### AUD-011 · S2 · Legal-data governance · Offline UI contains hand-written statutory values

- Location: packages/chat-ui/src/offline-resilience.ts:11–176; tools/validate_schemas.py:74–96; docs/adr/0011-low-bandwidth-taxpayer-pwa-and-service-worker.md.
- Evidence: The package contains PAYE brackets, WHT rates, a deadline, office hours, and payment-channel wording. The schema checker compares selected thresholds and WHT rates to the registry by substring, but does not generate, sign, or revoke a client snapshot and does not check every literal. The current Node BFF does not import this offline module; its exposure in a future browser build is therefore unverified.
- Standard: SSRA grounded-or-silent and numeric-provenance invariants; OWASP Agentic 2026 ASI05 and ASI09; NIST SSDF v1.1 PW.8.
- Impact: A low-bandwidth client can drift from approved tax facts or official-channel data and present stale figures without a live tool artifact, expiry, or revocation path.
- Fix: Generate a minimal, signed, versioned offline statutory snapshot from approved TaxFacts and official-channel sources; include effective dates, citations, expiry, and a safe unavailable state. Remove hand-maintained legal values.
- Verification: A changed registry produces the client snapshot deterministically; stale/unsigned/expired packs are refused; mobile tests show cited estimate-only behavior and safe fallback.
- Phase: R2 · Owner: Frontend, Tax Facts, and Legal Governance · Estimated PRs: 2 · Status: Open.

### AUD-012 · S2 · Observability and resilience · Propagation is coded but end-to-end proof is absent

- Location: apps/web/server.js:1807, 1869, 1966, 2000; services/agent-runtime/src/ssra_runtime/main.py; libs/ssra_mcp/src/ssra_mcp/server_base.py; infra/observability/otel-collector-config.yaml.
- Evidence: Source forwards or mints traceparent through web, runtime, gateway code, and MCP library. R0 found no running-stack test proving a single trace reaches collector, gateway, MCP, adapter, and audit storage with PII redaction; no load or chaos evidence was produced.
- Standard: OWASP ASVS v5.0.0-16.1.1, v5.0.0-16.2.1, and v5.0.0-16.5.2; NIST SSDF v1.1 PW.8.
- Impact: Operators cannot rely on source-level tracing claims for incident reconstruction, safety-trigger monitoring, or SLO response.
- Fix: Add full-path telemetry integration test and collector redaction assertions; keep all error, escalation, and guardrail spans; run load and upstream/database/NATS fault tests against defined SLOs.
- Verification: Trace query correlates browser, BFF, runtime, gateway, MCP, and adapter without PII; chaos report records safe degradation and alert behavior.
- Phase: R4 · Owner: SRE and Security Observability · Estimated PRs: 2 · Status: Open.

### AUD-013 · S3 · Audit reproducibility · Graph and local environment cannot be refreshed deterministically

- Location: graphify-out/GRAPH_REPORT.md; Taskfile.yml:3–6; local audit environment.
- Evidence: The checked-in graph report is reconciled, but graphify is unavailable. Local Node is 20.20.0 while the project declares >=24; the normal gates passed with an engine warning. Docker Compose static inspection was necessary after local plugin instability.
- Standard: NIST SSDF v1.1 PO.3 and PW.8.
- Impact: R0 evidence is useful but cannot fully reproduce graph and profile findings in this sandbox.
- Fix: Provide an approved, pinned graphify distribution or documented equivalent; make supported Node and Compose tooling a verified preflight.
- Verification: Clean environment can refresh the graph, render each profile, and run all gates with the declared Node version.
- Phase: R2 · Owner: Developer Experience and DevSecOps · Estimated PRs: 1 · Status: Open.

## Frontend re-audit findings (2026-10-23)

These findings came from a code and rendered-browser review of `apps/web/server.js`, `packages/ui/ops-console.js`, and `apps/console/server.js` at commit `a30d9ee`. Evidence came from a synthetic scenario runtime on loopback; no taxpayer data, credentials, or live endpoints were used. [The frontend audit](../product/frontend-ux-audit-2026-10.md#re-audit-2026-10-23) holds the phase plan.

### AUD-014 · S1 · Grounded UI · Served chat renderer bypasses the closed component registry and invents missing facts

- Location: `apps/web/server.js` inline `renderGenerativeCard` (commit `a30d9ee`, lines 938–980).
- Evidence: Scenario replies rendered `Filing Status: COMPLIANT` for a balance card without `filing_status`, `FILED (Due: 15th CAT)` for a period without status or date, `Domestic Taxes Desk` and `Duty Hours: Mon–Fri 08:00–17:00 CAT` for a `HandoffCard` carrying only `reason`, and a `Cash-Free Policy` line for an unregistered component name. `services/agent-runtime/src/ssra_runtime/nodes/compose.py` emits `HandoffCard` with only `{"reason": "OUT_OF_SCOPE"}` or `{"reason": "INSUFFICIENT_EVIDENCE"}` on the anonymous path, so every out-of-scope or abstaining public answer showed invented contact hours. The Zod registry in `packages/chat-ui` was not used by the served page.
- Standard: Master prompt invariants 2, 4, 5, and 9; OQ-009 (deadlines) and OQ-010 (contact-centre hours) remain open; OWASP LLM Top 10 2025 LLM05 (improper output handling); OWASP Agentic 2026 ASI09.
- Impact: Anonymous taxpayers could see a fabricated compliance status, deadline, office hours, queue, or payment policy attributed to SSRA.
- Fix: The public renderer accepts only public registered components (`CitationList`, `CalculatorForm`, `PaymentInstructionsCard`, `HandoffCard`) and applies the registry's required-field rules without defaults. Personal and action cards show a sign-in notice. Estimates need `is_estimate: true` and at least one approved source. Unknown components render nothing.
- Verification: `tests/browser/public-chat-answers.spec.ts` fails on `a30d9ee` and passes after the fix.
- Phase: R2-C · Owner: Frontend · Status: Fixed in R2-C.

### AUD-015 · S2 · Truthful state · Failed turns show raw error bodies or misreport the cause

- Location: `apps/web/server.js` `sendTurn` and `/api/turns` proxy (commit `a30d9ee`).
- Evidence: A runtime `503` displayed its `detail` text as the answer; a `429` displayed raw problem JSON; a BFF upstream failure displayed `{"error":"BFF_TURN_PROXY_ERROR"}`; an HTML `500` was reported as a lost connection. The BFF dropped `Retry-After`, and a malformed body (`null` or an array) produced `502` instead of `400`. There was no retry control.
- Standard: Master prompt invariant 10; WCAG 2.2 SC 3.3.1 and 3.3.3; GOV.UK Design System error guidance; RFC 9110 §10.2.3 (`Retry-After`).
- Impact: Taxpayers could read internal error text as SSRA guidance, or wrongly conclude that a question had reached SSRA.
- Fix: Status-specific plain-language failure states, a 30-second client timeout, draft restoration, and a `Try again` control. The BFF forwards only a delta-seconds `Retry-After` and returns `400` for malformed bodies and thread IDs.
- Verification: Rendered tests cover `503`, `429` with `Retry-After`, HTML `500`, dropped upstream connection, retry, and malformed requests.
- Phase: R2-C · Owner: Frontend · Status: Fixed in R2-C.

### AUD-016 · S2 · Truthful state · Public chat shows controls and metadata it cannot back

- Location: `apps/web/server.js` `renderTurnHtml`, confirmation, copy, and feedback handlers (commit `a30d9ee`).
- Evidence: A pending confirmation rendered `Confirm & Execute <tool>`, although `sanitizeBrowserTurnBody` strips confirmation tokens, so the control could never execute. Every answer showed internal fields: risk tier, intent slug, affect label (`EQ: …`), and `Thought for N ms`. `Provenance Verified` came from `outcome_verified`, which defaults to `true` in `services/agent-runtime/src/ssra_runtime/schemas.py`. Copy reported `Copied` when the clipboard write was rejected. Negative feedback reported `Flagged for Audit`.
- Standard: Master prompt invariants 8 and 10; OWASP Agentic 2026 ASI09 (human-agent trust exploitation).
- Impact: Users could trust a dead control, misread internal labels as assurances, or believe that a report had triggered an audit.
- Fix: No confirmation control in public chat. Trust cues show the approved-source count, `No source cited`, `Not fully verified`, and `Estimate`, each only when the reply supports it. Citations show title, anchor, effective date, version, and an `https` link. Copy and feedback report the real outcome.
- Verification: Rendered tests assert that no confirm control exists, that internal fields are absent, and that a copy failure is reported.
- Phase: R2-C · Owner: Frontend · Status: Fixed in R2-C.

### AUD-017 · S3 · Session hygiene · Public thread identifiers are guessable

- Location: `apps/web/server.js` conversation creation (`"thr_web_" + Date.now().toString(36)`).
- Evidence: Rendered conversations stored identifiers such as `thr_web_mvksx6ee`. The runtime keys per-thread language and affect state and forensic replay history by this identifier.
- Standard: OWASP ASVS v5.0.0 V7 (session token entropy, applied by analogy to conversation keys).
- Impact: A visitor who guessed another visitor's thread identifier could influence that thread's stored state.
- Fix: 128-bit identifiers from `crypto.getRandomValues`, which also works outside secure contexts. The BFF validates the runtime's identifier pattern.
- Verification: A rendered test asserts `thr_web_` plus 32 hex characters, and rejects a path-like identifier with `400`.
- Phase: R2-C · Owner: Frontend · Status: Fixed in R2-C. Server-side binding of an anonymous thread to an HttpOnly session remains future work under ADR-012.

### AUD-018 · S2 · Accessibility · Announcements and widget semantics fall short of WCAG 2.2 and ARIA APG patterns

- Location: `apps/web/server.js` message log, composer hint, account popover, settings tabs, rename/delete dialogs, and keyboard hints; `packages/ui/ops-console.js` command palette and account menu.
- Evidence: Each update rewrites the whole `role="log"` live region. The composer status line is `display: none` at 640 px or less, which hides "draft restored" messages on phones. The account popover declares `role="menu"` without menu keyboard support. Settings tabs have no arrow-key model or `aria-controls`. The staff palette input has no `combobox` role, `aria-expanded`, or `aria-activedescendant`. Rename and delete use `window.prompt` and `window.confirm`. Clearing from Settings has no confirmation. `Ctrl+N` and `Ctrl+,` are advertised but not implemented.
- Standard: WCAG 2.2 SC 1.3.1, 2.1.1, 3.2.4, 4.1.2, 4.1.3; WAI-ARIA APG combobox, tabs, and disclosure patterns.
- Impact: Screen-reader users get repeated or missing announcements and cannot operate some controls predictably.
- Fix: R2-D (public chat). The transcript is no longer a live region; a separate polite status region announces "Preparing an answer", "Answer received", and "Not answered". The composer status stays visible at every width, and the keyboard tips hide on small screens. The account panel uses the disclosure pattern and closes on Escape or when focus leaves it. Settings tabs follow the APG model (roving `tabindex`, arrow keys, Home and End, `aria-controls`, a labelled tabpanel). A modal stack makes the page inert behind dialogs and returns focus. An in-page dialog replaces `prompt` and `confirm`, with Cancel focused by default. Clearing from Settings asks for confirmation. False shortcut hints were removed. Conversation groups are lists under headings. Speech output uses the interface language.
- Verification: `tests/browser/public-chat-a11y.spec.ts` (8 tests) fails on the R2-C code and passes after R2-D.
- Phase: R2-D, R2-F · Owner: Frontend · Status: Public chat fixed in R2-D; staff command palette and account menu open for R2-F.

### AUD-019 · S2 · Accessibility · Light-theme status text fails contrast; preview status is styled as healthy

- Location: `apps/web/server.js` `.status-badge[data-connection="offline"]` (`#ffb2b5`); `packages/ui/ops-console.js` `.ops-preview-chip` and `.ops-preview-banner strong` (`#F4C430`); `.presence-pill` green styling.
- Evidence: Computed contrast in the light theme: offline status 1.31:1; preview chip 1.64:1 on white; preview banner heading 1.45:1. The "Preview only · no authenticated staff session" pill uses the success colour.
- Standard: WCAG 2.2 SC 1.4.3 (4.5:1) and SC 1.4.1; master prompt invariant 10.
- Impact: The two most important status messages are unreadable in light theme, and a non-operational state looks healthy.
- Fix: R2-D sets the light-theme offline text to `#991B1B` (6.35:1 on the badge background), follows the system colour scheme and `prefers-contrast: more` until the user chooses, adds `forced-colors` borders and focus colours, and raises small labels to at least 12 px. The console colours are planned for R2-F.
- Verification: A rendered test computes the offline status contrast in the light theme and requires at least 4.5:1.
- Phase: R2-D, R2-F · Owner: Frontend · Status: Public chat fixed in R2-D; staff console open for R2-F.

### AUD-020 · S2 · Language governance · UI publishes unreviewed strings for Phase 4 locales

- Location: `apps/web/server.js` `LOCALE_UI_STRINGS` (`din`, `nus`, `bfa`, `zne`, `shk`), composer placeholder, and landing prompts.
- Evidence: Phase 1 locales are `en`, `pga`, and `ar` (`packages/i18n/src/index.ts` `PHASE1_LOCALES`). The other five dictionaries contain script mixing, for example Arabic script inside the Bari and Dinka strings. The Juba Arabic subtitle also contains an Arabic-script word inside Latin-script text. The placeholder invites questions "in … Dinka", and a Dinka sample prompt is offered, although the Phase 1 evaluation set covers only `en`, `ar`, and `pga`.
- Standard: OQ-008; master prompt invariant 2 (no improvised legal or tax content).
- Impact: Users may receive interface text that a qualified reviewer has not approved, and may expect evaluated support for languages that have none.
- Fix: R2-E keeps interface strings only for `en`, `pga`, and `ar`. The other five locales stay selectable in a "Not yet reviewed (interface in English)" group, show English text with `lang="en"`, and display a notice that the language has not been reviewed or tested. The placeholder and sample prompts no longer advertise Dinka. The `pga` script defect is recorded under OQ-008 item 3 for a qualified reviewer.
- Verification: A rendered test covers `/din` (page `lang="en"`, notice, option group, no Dinka prompt or placeholder) and switching to `ar` (`lang="ar"`, RTL, notice hidden).
- Phase: R2-E · Owner: Frontend and SSRA Communications · Status: Fixed in R2-E for the web shell; reviewed translations remain open under OQ-008.

### AUD-021 · S3 · AI transparency and privacy · No persistent AI or accuracy notice at the composer

- Location: `apps/web/server.js` landing and composer.
- Evidence: The page title says "AI Assistant", but no notice next to the composer says that answers are AI-generated, can be wrong, and should be checked against cited sources. No notice warns against typing a TIN or phone number. The fact that history is saved on the device is shown only in Settings.
- Standard: OQ-009 item 2 (statutory AI disclosure wording); EU AI Act Article 50(1), used as a comparative benchmark only; GOV.UK Chat practice ("AI can make mistakes", check sources).
- Impact: First-time and shared-device users may over-trust answers or disclose identifiers in an anonymous channel.
- Fix: R2-E adds a persistent disclosure under the composer (AI assistant, can make mistakes, check cited sources, do not enter a TIN, phone number, or password). It is marked `lang="en"` because no reviewed translation exists. The rail states where conversations are saved, and Settings → Privacy can turn off device history. The wording is interim and recorded under OQ-009 item 2.
- Verification: Rendered tests assert the disclosure, the device note, and that turning off history leaves no stored conversations after a reload.
- Phase: R2-E · Owner: Frontend and SSRA Legal · Status: Fixed in R2-E with interim wording; statutory wording open under OQ-009.

### AUD-022 · S3 · Low-bandwidth and resilience · Low-data mode does not reduce rendering cost; no no-script path

- Location: `apps/web/server.js` CSS, `/healthz`, and response compression.
- Evidence: Low-data mode changes a request flag and badge text, but `backdrop-filter` blur, layered gradients, shadows, and animations remain. These are costly on low-end Android GPUs. There is no `<noscript>` content. `/healthz` returns the internal API and runtime URLs. With the same served page, Brotli quality 4 produced 22,901 bytes against 22,777 bytes for gzip level 6, and the server prefers Brotli.
- Standard: ADR-011; master prompt low-bandwidth budget; OWASP ASVS v5.0.0 V13 (unintended information disclosure).
- Impact: Slower and less stable rendering on constrained devices, no fallback when scripts are blocked, and internal topology disclosure.
- Fix: R2-E: low-data mode (and `prefers-reduced-transparency`) removes blur, decorative backgrounds, shadows, and motion. Added a `<noscript>` path to the official portal. `/healthz` returns only `status` and `service`. Brotli quality 5 with a size hint replaces quality 4 in both Node servers. On the served `/en` page this measured 24,234 bytes against 26,011 bytes at quality 4 and 25,809 bytes for gzip level 6, at about 1.75 ms against 1.26 ms per compression. Quality 9 cost 16.5 ms.
- Verification: Rendered tests cover low-data computed styles, the no-script note with JavaScript disabled, and the `/healthz` keys.
- Phase: R2-E · Owner: Frontend · Status: Fixed in R2-E. Real low-end Android and 2G measurements remain open.

### AUD-023 · S3 · Dashboard truthfulness · Preview navigation describes unavailable capabilities as current

- Location: `packages/ui/ops-console.js` `DESTINATIONS` descriptions and the client-only preview card.
- Evidence: Descriptions include "live calls, transfers & takeover", "served right now", and "Merkle seal proof", but every staff route is a preview with no data. Main content is rendered only by script.
- Standard: Master prompt invariant 10; ADR-018.
- Impact: Staff reviewing the preview may assume capabilities exist that are not built or connected.
- Fix: Planned for R2-F. Describe destinations as planned capabilities, and render the preview state on the server.
- Phase: R2-F · Owner: Frontend · Status: Open.

### AUD-024 · S2 · Contract drift · Runtime emits Generative UI props outside the closed registry

- Location: `services/agent-runtime/src/ssra_runtime/nodes/compose.py` (customs duty estimate, from commit `774dd7c`); `packages/chat-ui/src/index.ts` `CalculatorFormPropsSchema`.
- Evidence: `compose.py` emits `CalculatorForm` with `calculator_type: "CUSTOMS_DUTY"` and spreads tool output (`**sc`). The registry allows only `z.enum(["PAYE", "WHT"])`. The same commit widened the served renderer's duck typing to show `estimated_duty_ssp`, and reintroduced the `filing_status || "COMPLIANT"` default for `last_filed_period`. R2-C replaces that renderer.
- Standard: Master prompt invariant 9 (closed, Zod-validated registry); ADR-005; ADR-023.
- Impact: Runtime and registry disagree about which cards exist. With ADR-023, the public renderer shows the cited answer text but no card for customs estimates. A future permissive renderer could again show unvalidated amounts.
- Fix: Extend the registry under ADR-005, with schema, contract codegen, renderer, and rendered tests, if customs estimates need a card. Add a runtime contract test that validates every emitted `ui_component` against the registry schemas.
- Verification: A rendered test asserts that an unregistered calculator type renders no amount card.
- Phase: R2 · Owner: Agent runtime and Frontend · Status: Open. Mitigated in public chat by ADR-023.

