# AGENTS.md — SSRA Assist Agent Rulebook

This file is the authoritative engineering and safety rulebook for all coding agents working in the **SSRA Assist** (`ssra-cx`) monorepo. [`docs/00-master-prompt.md`](./docs/00-master-prompt.md) is the single source of truth.

---

## 1. Mission & Non-Negotiable Invariants

1. **Correctness over fluency, determinism over cleverness, auditability over convenience.**
2. **Never invent South Sudan tax law, rates, deadlines, penalties, fees, exchange rates, endpoints, or data formats.** When any upstream API, rate, or legal rule is unknown, define a typed port interface, build a synthetic mock adapter, log an open question in [`docs/open-questions.md`](./docs/open-questions.md) as `OQ-###`, and default runtime behaviour to safe abstention + human handoff.
3. **Treat `SSRA` and `NRA` (National Revenue Authority) as synonyms** across search, intent detection, and content; compute all deadlines in `Africa/Juba` (`UTC+02:00`).
4. **Grounded or silent:** Every factual claim must cite an approved `KnowledgeSnapshot` (document, section anchor, effective date).
5. **Numbers come only from deterministic tools:** Every tax rate, threshold, deadline, balance, fee, or exchange rate must trace to an MCP tool artifact (`tax_facts` or authenticated `ledger`/`customs` tool) and pass the `numeric_provenance` output validator.
6. **Risk-tiered autonomy (`T0`–`T4`):** Tier is determined from `ai/policies/risk-tiers.yaml` by intent and tool—never by the LLM—and enforced in both `services/agent-runtime` (OPA `policy_gate`) and `agentgateway`. `T4` actions have no tools and always route to human staff.
7. **Single governed egress:** All LLM, MCP (`2026-07-28` stateless Streamable HTTP), and future A2A (`1.0`) calls from `services/agent-runtime` must transit `agentgateway`.
8. **Zero trust for model arguments & strict subject binding:** OTP and identity verification run outside the LLM in `deterministic_router`. Verified identity binds an opaque `subject_ref` to the thread and propagates via OAuth 2.1 RFC 8693 token exchange. Never trust a TIN or subject identifier emitted by a model.
9. **Closed Generative UI Registry:** The agent may only request registered components (`BalanceCard`, `FilingStatusTimeline`, `PaymentInstructionsCard`, `CalculatorForm`, `CitationList`, `ConfirmActionSheet`, `HandoffCard`) validated by Zod 4. Never emit raw HTML or JavaScript from a model.

---

## 2. Stop and Ask a Human Before

- Performing any irreversible infrastructure or data operation;
- Adding a dependency with non-permissive licensing or export-control/sanctions implications (`OQ-012`);
- Touching real taxpayer data, production credentials, or confidential legal drafts (use synthetic data only);
- Changing any risk-tier assignment in `ai/policies/risk-tiers.yaml` (requires an SSRA-approved ADR);
- Relaxing any security, privacy, guardrail, or supply-chain control;
- Advancing across a Phase Exit Gate (`Gate 0` through `Gate 4`).

---

## 3. Supply-Chain & Dependency Policy (2026 Hardening)

- **7-Day Cooldown:** Never adopt a package release younger than 7 days (`pnpm` `minimumReleaseAge: 10080`, `uv` `exclude-newer`), unless it is a reviewed security patch.
- **Verify & Pin:** Before adding or upgrading any dependency, check its official release notes, pin the exact version and cryptographic hash in lockfiles, and record the verification date in `docs/PROGRESS.md`.
- **CI Digest Pinning:** Pin every GitHub Action, container image, and scanner tool by immutable SHA-256 digest or commit SHA.

---

## 4. Workflow, Codebase Navigation & Definition of Done

- **Keep Living Docs Current:** Update `AGENTS.md`, `docs/PROGRESS.md`, `docs/open-questions.md`, and affected runbooks (`docs/runbooks/`) in the same change as any architectural, config, or code update.
- **Codebase Knowledge Graph (`graphify`):** Once the repository scaffold is created, maintain and query `graphify-out/GRAPH_REPORT.md` before broad file exploration, using only SSRA-approved local/configured backends with zero secrets or PII.
- **Commands:** Use `Taskfile.yml` as the single entry point:
  - `task up` — start local stack with mock upstreams
  - `task lint` — run Biome, TypeScript `tsc`, Ruff, `basedpyright` (strict), and `import-linter`
  - `task test` — run Vitest, pytest, Hypothesis property tests, and contract tests
  - `task eval` — run deterministic and golden evaluation slices
  - `task gen` — regenerate Pydantic v2, TypeScript, Zod, and OpenAPI client types from `packages/contracts` and `services/api`
- **Definition of Done (every task):**
  1. Code, tests (unit, contract, property where relevant), and docs updated; strict types; lint clean.
  2. Threat-model delta noted; no secrets committed; dependency changes pinned and justified.
  3. AI changes: eval slice passed; prompt, model, or knowledge version bumped; changelog entry written.
  4. OpenTelemetry spans, metrics, and Presidio-redacted structured logs added.
  5. UI changes verified for WCAG 2.2 AA accessibility, low-bandwidth budgets (≤ 150 KB gzip first-load JS), and i18n (`en`, `pga`, and RTL `ar`).
  6. ADR written in `docs/adr/` for any decision with a real reversal cost.

<!-- BEGIN:turborepo-agent-rules -->

# This is NOT the Turborepo you know

Turborepo configuration, task behavior, and CLI commands can vary between installed versions and may differ from your training data. Resolve the `turbo` package from this file's directory or relevant workspace; in monorepos, it may not be visible from the repository root. For example, run `node -p "require.resolve('turbo/package.json')"` from a workspace that depends on `turbo`.

Read `docs/README.md` inside that installed package first, then read the relevant pages from its `docs/` directory before changing Turborepo configuration or commands. Heed deprecation notices. These bundled docs match the installed package version and are available without network access.

This block is written and re-added by `turbo` before repository-scoped commands when an AI agent is detected. In the Turborepo source repository, its template is defined in `crates/turborepo-cli/src/cli/agent_guidance.rs`. Removing the managed block while updates are enabled means a later qualifying invocation will add it again. Set `"agentGuidance": false` in the root `turbo.json` or `turbo.jsonc` to opt out; this does not remove an existing block. Keep the block committed with your work to avoid an uncommitted change on the next agent invocation.
<!-- END:turborepo-agent-rules -->
