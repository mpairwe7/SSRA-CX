# SSRA Assist (`ssra-cx`)

> **Sovereign, multilingual, omnichannel agentic customer-experience platform for the South Sudan Revenue Authority (SSRA).**

- **Single Source of Truth:** [`docs/00-master-prompt.md`](./docs/00-master-prompt.md)
- **Architecture Overview (C4 L1–L3):** [`docs/architecture/overview.md`](./docs/architecture/overview.md)
- **Core Data Model:** [`docs/architecture/data-model.md`](./docs/architecture/data-model.md)
- **Architecture Decision Records (ADR-001 to ADR-015):** [`docs/adr/README.md`](./docs/adr/README.md)
- **Threat Model & Security Controls:** [`docs/security/threat-model.md`](./docs/security/threat-model.md)
- **Open Questions Register (`OQ-001` to `OQ-012`):** [`docs/open-questions.md`](./docs/open-questions.md)
- **Progress & Phase 0 Task Plan:** [`docs/PROGRESS.md`](./docs/PROGRESS.md)
- **Agent Rulebook:** [`AGENTS.md`](./AGENTS.md)

---

## Quick Start

All developer workflows run through [`Taskfile.yml`](./Taskfile.yml):

```bash
# 1. Regenerate shared Pydantic v2, TypeScript, Zod 4, and OpenAPI contracts
task gen

# 2. Run strict linting, formatting, type-checking, and architectural boundary checks
task lint

# 3. Run unit, property-based (Hypothesis), and contract test suites
task test

# 4. Run evaluation harness (golden Q&A, 100% numeric provenance, citation precision, red-team)
task eval

# 5. Bring up the local stack (Postgres 18 + pgvector, Valkey, NATS, agentgateway, MCP servers, API, Runtime, Web PWA)
task up
```

---

## Repository Layout

```text
ssra-cx/
├── AGENTS.md                  # Agent rulebook (CLAUDE.md imports it)
├── CLAUDE.md
├── README.md
├── Taskfile.yml               # task up | down | test | lint | eval | gen
├── package.json  pnpm-workspace.yaml  turbo.json
├── pyproject.toml  uv.lock    # uv workspace root
├── renovate.json
├── .github/workflows/         # Portable CI (digest-pinned)
├── .devcontainer/
├── docs/                      # Master prompt, C4 architecture, ADRs, threat model, runbooks
├── apps/
│   ├── web/                   # Next.js 16.3.x taxpayer PWA + AG-UI chat
│   └── console/               # Next.js 16.3.x staff console
├── packages/                  # Shared TypeScript (ui, chat-ui, api-client, contracts, i18n, telemetry, config)
├── services/                  # Python deployables (api, agent-runtime, channel-gateway, workers, voice)
├── mcp-servers/               # Stateless MCP 2026-07-28 domain tool servers (_template + 11 servers)
├── libs/                      # Shared Python (ssra_core, ssra_security, ssra_llm, ssra_mcp, ssra_rules, ssra_adapters, ssra_testing)
├── ai/                        # Versioned prompts, OPA risk-tier policies (T0-T4), model routing, multilingual termbase
├── knowledge/                 # Approved sources manifest & versioned Tax Facts seed registry
├── evals/                     # Golden datasets, rubrics, suites, and OWASP ASI01-ASI10 red-team probes
├── infra/                     # Docker Compose, agentgateway routes/policies, Helm/Kustomize, OpenTofu, Kyverno, OTel
└── tools/                     # Contract codegen, schema validators, and corpus ingestion scripts
```
