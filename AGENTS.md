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

- **Keep Living Docs, ADRs & Runbooks Current (`living-docs-adr-runbooks-traceability` & `keep-docs-current` skills):** Update `AGENTS.md`, `docs/PROGRESS.md`, affected ADR(s) in `docs/adr/`, `docs/ai-governance/model-cards-and-datasheet.md`, `docs/open-questions.md`, and affected runbooks (`docs/runbooks/`) in the **same commit and PR** as any architectural, model, config, or code update, and run `task gen` + `task lint` (`tools/verify_supply_chain_and_signatures.py`) to enforce traceability.
- **Codebase Knowledge Graph (`graphify`):** Once the repository scaffold is created, maintain and query `graphify-out/GRAPH_REPORT.md` before broad file exploration, using only SSRA-approved local/configured backends with zero secrets or PII.
- **Commands:** Use `Taskfile.yml` as the single entry point:
  - `task up` — start local stack with mock upstreams (`infra/compose/docker-compose.gpu.yml` for sovereign GPU + local HF cache + Qdrant + Valkey + PostgreSQL 18; `tools/run_1000_complex_ngrok_benchmark.py` for 1,000-scenario live Ngrok stress/load verification)
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

---

## 5. Mandatory Feature-Branch, Pull Request, CI & CodeRabbit Workflow (`pr-ci-coderabbit-workflow`)

1. **Never push directly to `main`:** Every code, configuration, knowledge-base, or documentation change must be committed to a feature/fix branch (`feat/<slug>`, `fix/<slug>`, `chore/<slug>`) branched from the latest `origin/main`.
2. **Always authenticate as `mpairwe7` via `~/bin/gh` (`gh-mpairwe7` skill):** Run `~/bin/gh auth switch --user mpairwe7 && ~/bin/gh api user --jq .login` immediately before every `git push`, `pr create`, `pr comment`, or `pr merge`.
3. **Open a Pull Request & Preserve Issue State (`no-issue-autoclose` skill):** Open a PR against `main` using `~/bin/gh pr create` with bare `(#N)` issue references only (never `fixes #N`, `closes #N`, or `resolves #N`).
4. **Watch CI & Resolve Any Failures Immediately:** Monitor GitHub Actions checks (`~/bin/gh pr checks <PR> --watch`). If any CI step fails, inspect `~/bin/gh run view <RUN_ID> --log-failed`, fix the root cause on the feature branch, push the fix commit, and re-verify until 100% of CI checks are green.
5. **Resolve All CodeRabbit (`coderabbitai[bot]`) & Reviewer Comments:** Inspect all PR reviews, inline review comments, and issue comments (`~/bin/gh api repos/mpairwe7/SSRA-CX/pulls/<PR>/comments`, `/reviews`, and `/issues/<PR>/comments`). Address every actionable finding on the branch before merging.
6. **Merge Only When CI is 100% Green:** Merge via `~/bin/gh pr merge <PR> --squash --delete-branch` only after all CI checks pass and review comments are resolved, then sync local `main` (`git checkout main && git pull --ff-only origin main`).

<!-- BEGIN:turborepo-agent-rules -->

# This is NOT the Turborepo you know

Turborepo configuration, task behavior, and CLI commands can vary between installed versions and may differ from your training data. Resolve the `turbo` package from this file's directory or relevant workspace; in monorepos, it may not be visible from the repository root. For example, run `node -p "require.resolve('turbo/package.json')"` from a workspace that depends on `turbo`.

Read `docs/README.md` inside that installed package first, then read the relevant pages from its `docs/` directory before changing Turborepo configuration or commands. Heed deprecation notices. These bundled docs match the installed package version and are available without network access.

This block is written and re-added by `turbo` before repository-scoped commands when an AI agent is detected. In the Turborepo source repository, its template is defined in `crates/turborepo-cli/src/cli/agent_guidance.rs`. Removing the managed block while updates are enabled means a later qualifying invocation will add it again. Set `"agentGuidance": false` in the root `turbo.json` or `turbo.jsonc` to opt out; this does not remove an existing block. Keep the block committed with your work to avoid an uncommitted change on the next agent invocation.
<!-- END:turborepo-agent-rules -->
