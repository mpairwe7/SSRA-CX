# R0 Findings Register

**Baseline commit:** 7ca1f26e83b08decf64eacf02af059b537e69db7

**Status convention:** All findings are open. R0 collected evidence only; no application, CI, security-control, or deployment change was made.

## Severity summary

| Severity | Count | IDs |
|---|---:|---|
| S0 | 0 | None |
| S1 | 3 | AUD-001, AUD-002, AUD-003 |
| S2 | 9 | AUD-004 through AUD-012 |
| S3 | 1 | AUD-013 |

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

- Location: .github/workflows/ci.yml:7–60; .github/CODEOWNERS:1–7; Taskfile.yml:22–35.
- Evidence: All current uses entries are full SHAs and no pull_request_target event exists. CI uses gitleaks detect --no-git, has no zizmor job, and CODEOWNERS has no .github/workflows rule. Full-history gitleaks passed manually but is not a CI gate.
- Standard: SLSA v1.2 Build L3; NIST SSDF v1.1 PO.3, PW.7, and RV.1; OWASP ASVS v5.0.0-15.1.2 and v5.0.0-15.2.1.
- Impact: A future workflow regression, history secret, or unsafe workflow pattern can merge without the required second-control and security-owner review.
- Fix: Add a blocking zizmor job, full-history and PR-aware gitleaks scanning, workflow-specific CODEOWNERS, explicit workflow permissions policy, and adversarial fixtures that prove a tag-pinned action fails CI.
- Verification: CI rejects a tag action, unsafe permission, and synthetic secret in a reachable commit; protected workflow changes request Security review.
- Phase: R1 · Owner: DevSecOps · Estimated PRs: 2 · Status: Open.

### AUD-007 · S2 · Artifact and dependency integrity · Cooldown and image-verification claims are only partial

- Location: pnpm-workspace.yaml:6; pyproject.toml; mcp-servers/*/Dockerfile:2; infra/observability/slsa-provenance-v1.json; tools/verify_supply_chain_and_signatures.py.
- Evidence: pnpm has minimumReleaseAge 10080 but no trustPolicy no-downgrade. uv uses a fixed exclude-newer timestamp rather than a continuously auditable seven-day policy. Eleven MCP Dockerfiles use python:3.14-slim by tag. No installed or CI-referenced cosign, syft, or model-signing verifier was found.
- Standard: SLSA v1.2 Build L3; NIST SSDF v1.1 PO.3 and PS.3; OWASP ASVS v5.0.0-15.1.2, v5.0.0-15.2.1, and v5.0.0-15.2.4; CycloneDX 1.7; OpenSSF Model Signing.
- Impact: Lockfiles and some digest pins provide protection, but artifacts and models cannot be shown to be signed, verified, or safely refreshed. Tag resolution makes future builds non-reproducible.
- Fix: Define the approved security-fix exception process; enforce relative cooldowns supported by the selected toolchain; set pnpm trustPolicy; digest-pin every Dockerfile base; produce per-image CycloneDX 1.7 SBOMs, signatures, and provenance; verify before pull/start; verify model signatures before load.
- Verification: A too-new package and unapproved exception fail; a tag base fails policy; an unsigned or retagged image/model fails the deployment test.
- Phase: R1 · Owner: DevSecOps and Platform · Estimated PRs: 3 · Status: Open.

### AUD-008 · S2 · Frontend dependency hygiene · Next.js configuration is stale and advisory posture is ambiguous

- Location: apps/web/next.config.ts:1–11; apps/console/next.config.ts; apps/web/package.json:12–25; apps/web/Dockerfile:23–32.
- Evidence: pnpm why next sharp react-server-dom-* produced no served dependency. The web image starts node apps/web/server.js, while next.config.ts declares Next 16.3.8 and Cache Components.
- Standard: OWASP ASVS v5.0.0-15.1.1 and v5.0.0-15.2.1; NIST SSDF v1.1 PO.3 and PW.7. The 14 October 2026 official Next.js advisory is not applicable to a currently served Next package, but the stale configuration prevents a durable proof of that status.
- Impact: Security response and user-interface maintenance can target the wrong runtime. A future build may unintentionally introduce an affected Next version or Cache Components without an explicit dependency decision.
- Fix: Decide and document the production frontend runtime. Remove unused Next configuration or add an explicitly pinned, patched, built-and-tested Next runtime with a CI policy test.
- Verification: package inspection and container build prove the selected runtime; CI rejects affected Next/sharp versions if Next is adopted.
- Phase: R1 · Owner: Frontend and DevSecOps · Estimated PRs: 1 · Status: Open.

### AUD-009 · S2 · Quality and UX assurance · No executable browser-flow, route-matrix, or flake gate

- Location: Taskfile.yml:37–52; apps/web/tests/web.test.ts; apps/console/tests/console.test.ts; packages/chat-ui/tests/chat-ui.test.ts; packages/ui/ops-console.js.
- Evidence: Unit tests cover BFF sanitisation, RTL descriptors, offline queues, rail focus helpers, and preview dashboards. Repository search found no Playwright, Schemathesis, mutmut, promptfoo, garak, or PyRIT configuration. The repeated-suite requirement was not completed; targeted route tests are not derived from the 32-path OpenAPI document or BFF routes.
- Standard: WCAG 2.2 AA SC 1.4.10, 2.4.3, 2.4.7, and 2.5.8 require actual rendered-flow evidence; OWASP ASVS v5.0.0-4.1.3; NIST SSDF v1.1 PW.8.
- Impact: The main chat, conversation rail/sidebar, and staff dashboard flows can regress in mobile, keyboard, Arabic RTL, offline, and 2G states while unit tests stay green. Fail-closed claims may omit a newly added route.
- Fix: Add browser tests for public chat, rail/sidebar, dashboard preview, BFF identity stripping, 2G, Arabic RTL, offline queue, focus return, and reduced data. Add a generated route matrix for production/reference status codes, Schemathesis reference API checks, supported mutation testing, and five-run flake evidence.
- Verification: Browser traces/screenshots and accessibility results are attached; a forged subject/header and encoded v1 path fail; the matrix enumerates every path; each suite passes five uncached runs.
- Phase: R2 · Owner: QA and Frontend · Estimated PRs: 3–4 · Status: Open.

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
