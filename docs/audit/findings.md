# R0 Findings Register

**Baseline commit:** 7ca1f26e83b08decf64eacf02af059b537e69db7

**Status convention:** R0 findings were opened with evidence only. Each finding's `Status` line records later remediation; a closed finding still makes no production-readiness claim.

## Severity summary

| Severity | Count | IDs |
|---|---:|---|
| S0 | 0 | None |
| S1 | 6 | AUD-001, AUD-002, AUD-003, AUD-014, AUD-034, AUD-035 |
| S2 | 26 | AUD-004 through AUD-012, AUD-015, AUD-016, AUD-018, AUD-019, AUD-020, AUD-024, AUD-025, AUD-026, AUD-029, AUD-030, AUD-036 through AUD-039, AUD-041 through AUD-043 |
| S3 | 11 | AUD-013, AUD-017, AUD-021, AUD-022, AUD-023, AUD-027, AUD-028, AUD-031, AUD-032, AUD-033, AUD-040 |

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
- Staff console (R2-F): the command palette follows the APG combobox pattern (`role="combobox"`, `aria-expanded`, `aria-controls`, `aria-activedescendant`, options with `aria-selected`, and a polite result count), and the shell is inert while it is open. The account menu follows the APG menu-button pattern: focus moves to the first item, arrow keys and Home/End move between items, Escape closes and returns focus, Tab closes, and radio items sit in labelled groups.
- Verification (R2-F): `tests/browser/staff-console-a11y.spec.ts` fails on the R2-E code and passes after R2-F.
- Phase: R2-D, R2-F · Owner: Frontend · Status: Fixed in R2-D (public chat) and R2-F (staff console).

### AUD-019 · S2 · Accessibility · Light-theme status text fails contrast; preview status is styled as healthy

- Location: `apps/web/server.js` `.status-badge[data-connection="offline"]` (`#ffb2b5`); `packages/ui/ops-console.js` `.ops-preview-chip` and `.ops-preview-banner strong` (`#F4C430`); `.presence-pill` green styling.
- Evidence: Computed contrast in the light theme: offline status 1.31:1; preview chip 1.64:1 on white; preview banner heading 1.45:1. The "Preview only · no authenticated staff session" pill uses the success colour.
- Standard: WCAG 2.2 SC 1.4.3 (4.5:1) and SC 1.4.1; master prompt invariant 10.
- Impact: The two most important status messages are unreadable in light theme, and a non-operational state looks healthy.
- Fix: R2-D sets the light-theme offline text to `#991B1B` (6.35:1 on the badge background), follows the system colour scheme and `prefers-contrast: more` until the user chooses, adds `forced-colors` borders and focus colours, and raises small labels to at least 12 px. The console colours are planned for R2-F.
- Verification: A rendered test computes the offline status contrast in the light theme and requires at least 4.5:1.
- Staff console (R2-F): the preview chip uses the theme accent (7.79:1 on white in the light theme). The preview status pill uses the warning colour instead of the success colour. The unused `.ops-preview-banner` rule was removed.
- Phase: R2-D, R2-F · Owner: Frontend · Status: Fixed in R2-D (public chat) and R2-F (staff console).

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
- Fix: R2-F removes the `blurb` descriptions; they were never rendered, so they were dead data. The destination list moves to module scope, and the server renders the preview card, page title, and heading for each route. Client navigation updates only the heading and title. The page is now meaningful without JavaScript.
- Verification: A rendered test with JavaScript disabled finds the route heading and preview statement, and none of the capability claims.
- Phase: R2-F · Owner: Frontend · Status: Fixed in R2-F.

### AUD-024 · S2 · Contract drift · Runtime emits Generative UI props outside the closed registry

- Location: `services/agent-runtime/src/ssra_runtime/nodes/compose.py` (customs duty estimate, from commit `774dd7c`); `packages/chat-ui/src/index.ts` `CalculatorFormPropsSchema`.
- Evidence: `compose.py` emits `CalculatorForm` with `calculator_type: "CUSTOMS_DUTY"` and spreads tool output (`**sc`). The registry allows only `z.enum(["PAYE", "WHT"])`. The same commit widened the served renderer's duck typing to show `estimated_duty_ssp`, and reintroduced the `filing_status || "COMPLIANT"` default for `last_filed_period`. R2-C replaces that renderer.
- Standard: Master prompt invariant 9 (closed, Zod-validated registry); ADR-005; ADR-023.
- Impact: Runtime and registry disagree about which cards exist. With ADR-023, the public renderer shows the cited answer text but no card for customs estimates. A future permissive renderer could again show unvalidated amounts.
- Fix: Extend the registry under ADR-005, with schema, contract codegen, renderer, and rendered tests, if customs estimates need a card. Add a runtime contract test that validates every emitted `ui_component` against the registry schemas.
- Verification: A rendered test asserts that an unregistered calculator type renders no amount card.
- Phase: R2 · Owner: Agent runtime and Frontend · Status: Open. Mitigated in public chat by ADR-023.

## Accessibility, adaptability, responsiveness, and performance audit (2026-10-24)

Evidence comes from Lighthouse 12.8.2 (Apache-2.0, run from a verified local cache as an external tool, not a repository dependency) against the live GPU profile, plus a Playwright lab audit against loopback copies of the same merged servers (`f9c8861`). That audit covered ten viewports, WCAG text spacing, 200 % text, Event Timing under 4× and 6× CPU slowdown, emulated 2G and 3G, and back/forward cache. Lighthouse scored 100 in all four categories for every page tested. The findings below are what the default load audit does not exercise. See [the R2-G report](./phase-R2-G-adaptive-layout-report.md).

### AUD-025 · S2 · Truthful state · Saved conversations never appeared after a reload

- Location: `apps/web/server.js` inline script (no initial `renderApp()` call, present since before `a30d9ee`).
- Evidence: A conversation seeded in `localStorage` survived the reload, but the rail rendered zero rows and no empty state until the user sent a message. The rail note says that conversations are saved on this device.
- Standard: Master prompt invariant 10; WCAG 2.2 SC 3.2.4 (consistent identification of features).
- Impact: Returning users could not reach their saved history, which also makes the device-history controls misleading.
- Fix: Render once at the end of start-up.
- Verification: A rendered test seeds a conversation, reloads, and expects the row. It fails on `f9c8861`.
- Phase: R2-G · Owner: Frontend · Status: Fixed in R2-G.

### AUD-026 · S2 · Mobile reflow · Phone layout rules were overridden by the base stylesheet

- Location: `apps/web/server.js` CSS. The `@media (max-width: 640px)` block preceded the base rules of equal specificity.
- Evidence: At 320×568 the header wrapped to 173 px, the composer dock took 238 px, and the transcript got 157 px (28 %). On a 568×320 landscape phone the transcript got 40 px (13 %). At 320 px, which is also 400 % zoom on a 1280 px screen, the language selector sat off-screen and, because `body` does not scroll, could not be reached. At 360 px with 200 % text, the voice, language, and theme controls went off-screen. The scam-check sample prompt's URL did not wrap.
- Standard: WCAG 2.2 SC 1.4.10 Reflow, 1.4.4 Resize Text, and 1.4.12 Text Spacing.
- Impact: Phone users, particularly in landscape or with larger text, lost most of the conversation area and could not change language.
- Fix: Responsive rules now follow the base rules. Phones use a two-row grid header with icon-only controls that keep their accessible names. Screens shorter than 500 px scroll the whole column. Long strings wrap.
- Verification: The header is 107 px at 320 px and 360 px, and the transcript area is 44 % at 320×568 and 57 % at 360×740. Landscape uses a full-height scrolling column. The lab audit finds no off-screen control, text-spacing, or 200 %-text failure on either surface. Seven rendered tests fail on `f9c8861`; two pass on both and guard sizes that already worked.
- Phase: R2-G · Owner: Frontend · Status: Fixed in R2-G.

### AUD-027 · S3 · Accessibility · Staff mobile menu button failed Label in Name

- Location: `packages/ui/ops-console.js` `#mobile-ops-nav-btn`.
- Evidence: Lighthouse `label-content-name-mismatch` scored 0. The visible text "Menu" was not part of the accessible name "Open preview navigation". The audit is unweighted, so the accessibility score remained 100.
- Standard: WCAG 2.2 SC 2.5.3 Label in Name.
- Fix: The accessible name is the visible "Menu", and `aria-expanded` carries the state. The audit now reports no mismatch.
- Phase: R2-G · Owner: Frontend · Status: Fixed in R2-G.

### AUD-028 · S3 · Adaptability · No on-screen keyboard or browser theme adaptation

- Location: `apps/web/server.js` `<head>`.
- Evidence: The viewport meta did not opt into `interactive-widget=resizes-content`. Since Chrome 108 on Android, the keyboard resizes only the visual viewport by default, which can cover a bottom-docked composer. There was no `theme-color`.
- Fix: Added `interactive-widget=resizes-content` and light and dark `theme-color` values, which follow the chosen theme. Browsers without support ignore both.
- Verification: A rendered test checks the viewport meta and the theme colour after a theme change. On-screen keyboard behaviour needs real-device confirmation.
- Phase: R2-G · Owner: Frontend · Status: Fixed in R2-G; device confirmation open.

### AUD-029 · S2 · Interaction performance · Long conversations exceed the INP threshold

- Location: `apps/web/server.js` `renderApp()`, which rewrites the whole transcript on every update.
- Evidence: With 80 synthetic turns, the worst interaction took 272 ms at 4× and 344 ms at 6× CPU slowdown. With 6 turns it took 64 ms and 88 ms. The Core Web Vitals "good" INP threshold is 200 ms.
- Fix: R2-H rebuilds only the turns that changed and keeps earlier message nodes. It opens long conversations progressively: the latest 30 turns paint first and older turns are prepended in 20-turn chunks while an anchor keeps the latest turn in place. Message rows use `content-visibility: auto` with a remembered intrinsic size, and the rail skips unchanged rewrites.
- Verification: With 80 turns the worst interaction fell from 256 ms to 120 ms at 4× and from 368 ms to 144 ms at 6× CPU, and opening the conversation from 240 ms to 152 ms at 6×. Send-to-answer at 6× fell from 708 ms to 161 ms. Rendered tests check node preservation, progressive completion in order with the latest turn in view, and `content-visibility`. Lab numbers are not field INP; CrUX or RUM data is still needed.
- Phase: R2-H · Owner: Frontend · Status: Fixed in R2-H.

### AUD-030 · S2 · DOM XSS hardening · Trusted Types are created but not enforced

- Location: `apps/web/server.js` and `apps/console/server.js` CSP.
- Evidence: Lighthouse `trusted-types-xss` reported (severity High) that no CSP Trusted Types directive was found. Both pages create a policy, but without `require-trusted-types-for 'script'` any DOM sink still accepts a string. Trusted Types is supported in Chrome 83, Firefox 148, and Safari 26.
- Fix: R2-H enforces `require-trusted-types-for 'script'` with named policies: `ssra-web-html` and `ssra-web-script-url` (which allows only `/sw.js`) for the public chat, and `ssra-ops-html` for the staff preview. A string assignment to any DOM sink now throws.
- Verification: Rendered tests check both CSP headers, a rejected string `innerHTML` assignment on each surface, and service-worker registration through the script-URL policy. Lighthouse `trusted-types-xss` now reports no items, and the full browser suite shows no console errors.
- Phase: R2-H · Owner: Frontend and Security · Status: Fixed in R2-H.

### AUD-031 · S3 · Regression tooling · Live smoke suite asserts behaviour the fail-closed policy forbids

- Location: `tools/smoke_test_stack.py` (public status and section 8).
- Evidence: Against the live stack on 2026-10-23, the suite failed at its first assertion. It expects `200` from `/v1/admin/public-status`, which correctly returns RFC 9457 `503`. It also sends client-supplied staff IDs to takeover, hand-back, and feature-flag routes, which correctly return `403`, as `services/api/tests/test_route_matrix.py` requires. With those expectations corrected, the rest of the suite passed. The 1,000-scenario benchmark generator also hard-codes the report date and labels direct runtime calls "over Ngrok".
- Fix: `tools/smoke_test_stack.py` now expects the governed `503` and `403` statuses, including for a forged `X-SSRA-Staff-Id`. `task up` runs the in-process suite with `SSRA_RUNTIME_MODE=reference` for that test step only; before this, production-default `503` responses failed the suite at `/healthz`. Both benchmark generators record the run date in Africa/Juba and the transport (tunnel or direct) instead of a hard-coded date and an "over Ngrok" label. `tools/live_frontend_regression.mjs` and [the live regression runbook](../runbooks/live-regression.md) make the live run repeatable.
- Verification: In reference mode, the previous suite fails in-process and the corrected suite passes. Against the live stack, the corrected expectations passed on 2026-10-23 ([record](./live-regression-2026-10-23.md)).
- Phase: R2 · Owner: QA · Status: Fixed.

### AUD-032 · S3 · Adaptability · A saved locale overrides the locale in the URL

- Location: `apps/web/server.js` state initialisation.
- Evidence: After a visit to `/en`, opening `/ar` in the same browser showed English and left-to-right text. The server renders `lang="ar"`, but the saved preference then replaces it.
- Impact: Shared links to a language version do not open in that language for returning users.
- Fix: Proposed: let an explicit locale path win, and update the saved preference.
- Phase: R2 · Owner: Frontend · Status: Open.

### AUD-033 · S3 · Answer relevance · An out-of-scope question received unrelated grounded guidance

- Location: Agent runtime retrieval and abstention (observed through the live BFF).
- Evidence: "Can you book me a flight to Nairobi?" returned e-Tax filing-manual guidance with one approved source, instead of an out-of-scope response or handoff.
- Impact: A cited but irrelevant answer can look authoritative.
- Fix: Runtime owner to review relevance thresholds and out-of-scope detection; add an evaluation case.
- Phase: R2 · Owner: Agent runtime · Status: Open.

## Call receptionist audit (2026-10-24)

Scope: `services/voice` (`ssra_voice`), `packages/chat-ui/src/call-receptionist.ts`, the `VoiceIvrChannelAdapter` in `services/channel-gateway`, the web voice-input dialog, the staff "Calls" preview, and the voice services in the GPU Compose profile, at commit `70a6d1a`. **No live telephony path exists.** No SIP trunk, voice WebSocket, or voice service is deployed; `python -m ssra_voice` prints a status object and exits; and the voice functions below are called only by unit tests, evaluation suites, and the benchmark tools. Findings marked latent are not exploitable today, but they would become live as soon as an IVR is connected. See [the call receptionist audit](../product/call-receptionist-audit-2026-10.md).

### AUD-034 · S1 (latent) · Identity binding · Voice DTMF step-up authorized any well-formed TIN and OTP

- Location: `services/voice/src/ssra_voice/__init__.py` `verify_voice_dtmf_step_up`.
- Evidence: Any 9–12 digit TIN with any 6 digits returned `authorized=True` and `BOUND_T1` or `BOUND_T3`. The OTP was never checked against an issued code, attempts were unlimited, and the existing unit test asserted this as correct. No caller outside tests exists today.
- Standard: Master prompt invariant 8 (OTP and identity verification outside the model, strict subject binding); OWASP ASVS v5.0.0 V6 (authentication); OQ-005 (identity proofing).
- Impact: Once connected to an IVR, any caller could bind any taxpayer's identity, and at T3.
- Fix: The function now requires an injected `otp_verifier` port, backed by the approved identity provider. Without one it returns `WARM_TRANSFER_TO_OFFICER`. A rejected code returns `OTP_REJECTED`. Each rejection is recorded in an injected `StepUpAttemptStore` against the call's `call_id`, so the limit cannot be reset by the caller; the third rejection sends the call to an officer. A verifier or store that raises also sends the call to an officer and binds nothing. The masked TIN is returned only on success.
- Verification: The tightened unit test fails on `70a6d1a` (`authorized` was `True` with no verifier) and passes after the fix. It covers no verifier, three rejections counted by the store, a correct code after the limit, a raising verifier, a raising store, a missing `call_id`, and the verified path. CodeRabbit review of #97 prompted the store and the exception handling.
- Phase: R2-I · Owner: Voice and Security · Status: Fixed in R2-I.

### AUD-035 · S1 (latent) · Token integrity · Call-to-web carryover tokens were signed with a public constant and never expired

- Location: `ssra_voice` `_compute_carryover_hmac`, `build_call_to_web_carryover`, and `verify_call_to_web_carryover`.
- Evidence: Without `SSRA_VOICE_CARRYOVER_HMAC_KEY`, tokens were signed with `"ssra-voice-carryover-sovereign-default-2026-10"`, a value committed to this public repository. Tokens carried no issue time, so a valid token stayed valid forever.
- Standard: Master prompt invariant 11 (missing configuration fails closed); OWASP ASVS v5.0.0 V11 (cryptography) and V7 (session tokens).
- Impact: Anyone could mint a carryover token that resumes a goal for any caller identifier.
- Fix: A key of at least 32 bytes is required, otherwise the call fails closed with `503`. `issued_at` is bound into the HMAC, and tokens older than 15 minutes, or more than 60 seconds in the future, are rejected. The key is documented in ADR-024 rather than `.env.example`, because workspace policy forbids committing `.env*` files.
- Verification: Unit tests cover a short key, wrong owner, expiry, a tampered issue time, a tampered action, and a tampered model flag.
- Phase: R2-I · Owner: Voice and Security · Status: Fixed in R2-I.

### AUD-036 · S2 · Call desk integrity · Two officers could claim the same call, and ended calls could reappear

- Location: `ssra_voice` `CallLobbyManager.apply_event`.
- Evidence: A second `call.claimed` silently replaced the first officer. A claim was accepted in any state. A late `call.risk` event after `call.ended` recreated the call. Unknown event types and arbitrary priority strings were accepted. A missing `waiting_since` became `1.0`, a 1970 timestamp, so wait times were invented.
- Standard: Master prompt invariant 10 (truthful interface state).
- Fix: Only a call waiting for an officer can be claimed, and the first claim wins. Ended calls leave a tombstone (the most recent 4,096), and only `call.started` can add a call, so a late event for an ended call is ignored or, once its tombstone has been evicted, rejected. Each event is validated before the stored entry changes, so an invalid priority can no longer leave a call half-entered in the waiting queue. Non-finite wait times become `None`. Unknown events and priorities are rejected, and a missing wait start stays `None`.
- Verification: Unit tests cover claim-before-transfer, double claim, revival after end, unknown events, and unknown priorities. The evaluation suite still passes.
- Phase: R2-I · Owner: Voice · Status: Fixed in R2-I.

### AUD-037 · S2 · Launch gate and evidence · The voice WER gate trusts a per-call number, and benchmarks report speech that was never processed

- Location: `ssra_voice` `is_voice_language_approved` and `route_voice_turn`; `tools/run_1000_complex_ngrok_benchmark.py` and `tools/run_20000_complex_ngrok_benchmark.py`.
- Evidence: `is_voice_language_approved` discards `locale`, and `route_voice_turn` accepts `measured_wer` from its caller on every turn. No governed record of measured WER per language and test set exists. The benchmarks' "STT" scenarios pass a fixed `asr_wer` of 0.05 or 0.08 with text messages, so no audio, ASR model, or TTS model is involved. Dinka is therefore "approved" with a WER that has never been measured. The master prompt requires a language to launch on voice only after its WER on SSRA test sets meets the gate.
- Fix: `VoiceWerEvidence` records language, WER, test set, measurement date, and utterance count. The governed `APPROVED_VOICE_WER_EVIDENCE` is empty, so `route_voice_turn` transfers every caller to an officer until SSRA approves a measurement (OQ-008). Missing, mismatched, non-finite, or negative evidence counts as no evidence. Tests and benchmarks inject labelled synthetic evidence. The benchmark generators describe speech scenarios as simulated in their docstrings and reports, add `speech_scenarios_simulated: true` to the JSON, and no longer list SunflowerASR as part of the stack. `tools/verify_phase_gates.py` asserts that no language is approved and adds OQ-008 to the Gate 4 blockers.
- Verification: On the R2-I code, an unmeasured Dinka turn with a caller-supplied WER of 0.05 returned `STREAM_ASR`; after the fix it returns `WARM_TRANSFER_TO_OFFICER` with "no approved word-error-rate evidence for din (OQ-008)". All 300 and 6,000 simulated speech scenarios in the two benchmarks still route as designed. The committed benchmark reports predate this change and were not regenerated, because the SSRA GPU stack was not running.
- Phase: R2-J · Owner: Voice and QA · Status: Fixed in R2-J (no language is approved for voice; evidence remains OQ-008).

### AUD-038 · S2 · Staff truthfulness · Officer briefs and transfer summaries misstate what happened

- Location: `ssra_voice` `generate_officer_call_brief` and `route_voice_turn` warm-transfer summary.
- Evidence: The brief is produced by keyword rules but labelled `model="ssra-sovereign/sunflower-qwen3.5-9b"`, which the staff console displays as its attribution. It adds an open item, "confirm next filing/payment step", that no turn supports. It lists the first three assistant turns rather than the latest. Keywords matched as substrings, so "Show me…" made a caller "confused". It invented sequence number 1 for turns without one. It truncated assistant turns to 140 characters *before* redaction, so a TIN that straddled the cut leaked its first five digits. The transfer summary always said "caller pressed 0, WER exceeded, or low-confidence turns", whatever the actual reason.
- Fix: `model` is `None` for rule-built briefs, and the console shows "Built by keyword rules, not by a model". The brief lists the latest three assistant replies and gives the latest caller request as the open item. Keywords match whole words, and "how" was dropped. Turns without a valid sequence number carry no evidence link. Text is redacted before it is shortened. The opener no longer quotes the caller. The transfer summary lists only the reasons that applied.
- Verification: The R2-I code leaked `10020` from `1002001234` in the boundary case and labelled "Show me my filing options" as confused; unit tests now cover both, plus the latest replies, the open item, missing sequence numbers, and each transfer reason.
- Phase: R2-J · Owner: Voice and Staff Console · Status: Fixed in R2-J.

### AUD-039 · S2 · Legal data · Voice retention periods are invented

- Location: `ssra_voice` `VoiceRetentionPolicy` (raw audio 24 h, transcripts 90 days, analytics 365 days).
- Evidence: OQ-009 item 1 (statutory retention for voice recordings and transcripts) is open, but the values are hard-coded defaults.
- Fix: All three periods default to `None` (no approved period: keep nothing after the call), and the audit entry records `retention_status: "pending_oq_009"`. A policy that stores raw audio without an approved period raises an error.
- Verification: Unit tests cover the defaults and the refused raw-audio policy.
- Phase: R2-J · Owner: Voice and SSRA Legal · Status: Fixed in R2-J (periods remain OQ-009).

### AUD-040 · S3 · Privacy · The TTS phrase cache keeps audio of any text

- Location: `ssra_voice` `TtsPhraseCache`.
- Evidence: Every successfully synthesized phrase is cached in a shared in-memory LRU, including personal answers, which then outlive the call.
- Fix: `TtsPhraseCache` stores audio only for phrases in `fixed_voice_prompts()` (the tool-wait fillers), or an explicit allow-list. Other text is synthesized and returned without being kept. The synthesizer is typed as `TtsSynthesizer`.
- Verification: A personal PAYE answer synthesized twice is never served from cache; a filler is.
- Phase: R2-J · Owner: Voice · Status: Fixed in R2-J.

### AUD-041 · S2 · Caller output · Spoken and SMS output can cut or add figures

- Location: `ssra_voice` `build_voice_spoken_turn_and_sms_followup` and `verify_spoken_figure_fidelity`; `services/channel-gateway` `VoiceIvrChannelAdapter.format_outbound`.
- Evidence: The SMS follow-up is cut at 160 characters, which can split a figure, and the 70-character UCS-2 limit for Arabic is ignored. The text starts "SSRA OFFICIAL:" although it is an automated answer and the official-channel registry is OQ-011. The IVR adapter cuts at 1,000 characters mid-sentence. The strict spoken-figure guard ignores spelled-out numbers such as "five hundred".
- Fix: Planned for R2-K.
- Phase: R2-K · Owner: Voice and Channels · Status: Open.

### AUD-042 · S2 · Caller experience · No spoken AI disclosure, and barge-in is not implemented

- Location: `ssra_voice` (no greeting function); `route_voice_turn` (`_ = barge_in_detected`); `VoiceStreamSession.trigger_barge_in`.
- Evidence: No call-start disclosure exists that says the caller is speaking with an automated assistant and how to reach a person. The master prompt requires barge-in. `route_voice_turn` discards the barge-in signal, and the session records only a flag; it neither stops playback nor cancels generation.
- Standard: Master prompt Voice/IVR specification; OQ-009 item 2 (disclosure wording); EU AI Act Article 50(1) as a comparative benchmark (spoken disclosure at the first interaction).
- Fix: Planned for R2-K.
- Phase: R2-K · Owner: Voice · Status: Open.

### AUD-043 · S2 · Platform exposure · The GPU profile publishes the Core API and model servers on all interfaces

- Location: `infra/compose/docker-compose.gpu.yml` with the local `.env` (live on 2026-10-24).
- Evidence: Live bindings were `0.0.0.0:18083` for the Core API, which bypasses the BFF; `0.0.0.0:28011` for the Sunflower vLLM, which is unauthenticated and bypasses `agentgateway`; and `0.0.0.0:28100` for Orpheus TTS. The Orpheus image is `app-orpheus-tts:latest`, built locally on 2026-10-15 with no repository digest, and no SSRA code calls it. The frontend on `0.0.0.0:3032` is the intended public surface.
- Standard: Master prompt invariant 7; AUD-002, AUD-005, and AUD-007; AGENTS.md digest pinning.
- Impact: Anyone on the host's network can call the model and the Core API directly, without the BFF or gateway controls.
- Fix: Proposed: bind these ports to `127.0.0.1`, pin or remove Orpheus, and route model access through the gateway. This is shared infrastructure, so a human must decide before the bindings change.
- Phase: R3 · Owner: Platform · Status: Open; decision needed.

