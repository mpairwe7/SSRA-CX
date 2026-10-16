# ADR-002: Service Decomposition and Modular Monolith (`services/api`)

- **Status:** Proposed
- **Date:** 2026-10-16
- **Deciders:** Founding Principal Architect / Staff Engineer, SSRA Technical Lead
- **Reversal Cost:** Medium
- **References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 5, 10.2, 10.3, 16

---

## 1. Problem Statement

How do we partition backend responsibilities to balance operational simplicity for SSRA's local team with blast-radius isolation and independent scaling for AI orchestration, external channels, and domain tools?

## 2. Context

SSRA Assist encompasses diverse workloads:
- CRUD and transactional state management (`conversations`, `identity_link`, `cases`, `appointments`, `knowledge_admin`, `consent`, `analytics_api`, `admin`);
- Stateful, CPU/IO-intensive conversational graph execution and SSE streaming (`agent-runtime`);
- Public webhook termination and telecom protocol normalization for WhatsApp, SMS, USSD, and Voice (`channel-gateway`);
- Strict capability-scoped domain tools invoked by the agent (`mcp-servers/*`);
- Long-running asynchronous workflows such as Docling PDF/gazette ingestion, vector re-indexing, and SLA timers (`workers`).

Deploying dozens of fine-grained microservices for CRUD domains would overwhelm SSRA's in-country operations team with distributed-transaction complexity. Conversely, bundling public telecom webhooks, LLM graph execution, MCP resource servers, and core CRUD into a single process would violate least privilege (Section 4) and allow a spike in WhatsApp traffic or a slow PDF ingestion job to starve core APIs.

## 3. Options Considered

1. **Single Monolithic Python Process for Everything:** Simplest deployment, but violates the security requirement that the agent runtime can only reach tools and models across `agentgateway` via mTLS and OAuth 2.1 token exchange. Also couples webhook DDoS blast radius with internal staff APIs.
2. **Fine-Grained Microservices per Bounded Context (15+ Core Services + 11 MCP Servers):** Maximum isolation, but high operational overhead, cross-service schema drift, and distributed transaction complexity on NCA Kubernetes.
3. **Modular Monolith for Core API + Separate Deployables for Runtime, Channel Gateway, Workers, and MCP Servers (Selected):** Consolidates the eight core business contexts into one strongly-typed FastAPI modular monolith (`services/api`) while isolating `services/agent-runtime`, `services/channel-gateway`, `services/workers`, and `mcp-servers/*` as separate deployables.

## 4. Decision

We adopt Option 3:

1. **`services/api` (FastAPI Modular Monolith):** Houses the eight core bounded contexts under `src/ssra_api/<context>/` (`conversations`, `identity_link`, `cases`, `appointments`, `knowledge_admin`, `consent`, `analytics_api`, `admin`).
   - Every bounded context strictly follows the hexagonal layout: `api/`, `application/`, `domain/`, `infrastructure/`, `tests/`.
   - **`import-linter` enforcement in CI:** Contexts may only communicate via published `application/` ports or domain events over the transactional outbox; cross-context imports of `infrastructure/` or ORM models fail the build.
2. **`services/agent-runtime`:** Separately deployed FastAPI + LangGraph service. Has no direct database credentials for business tables (only its checkpointer schema) and no direct network path to upstreams—all tool and model calls exit through `agentgateway`.
3. **`services/channel-gateway`:** Separately deployed FastAPI perimeter service handling WhatsApp, SMS, USSD, and Voice webhooks/SMPP, deduplication, and CloudEvents 1.0 normalization.
4. **`services/workers`:** Separately deployed Temporal worker pool for Docling ingestion, re-indexing, eval runs, and SLA timers.
5. **`mcp-servers/*`:** Eleven capability-scoped MCP servers (following `mcp-servers/_template/`), each acting as an independent OAuth 2.1 resource server behind `agentgateway`.

## 5. Consequences

- **Positive:**
  - Local SSRA engineers manage one core database migration stream (Alembic in `services/api`) and one OpenAPI 3.1 contract for frontends (`apps/web`, `apps/console`).
  - `services/agent-runtime` and `mcp-servers/*` maintain hard network and OAuth 2.1 boundaries across `agentgateway`.
  - Any bounded context inside `services/api` can be extracted into a standalone service later because `import-linter` prevents tangled dependencies.
- **Negative / Trade-offs:**
  - Requires discipline to maintain strict module boundaries inside `services/api` and shared library versioning across the `uv` workspace (`libs/ssra_*`).

## 6. Reversal Cost & Migration Path

- **Reversal Cost:** Medium. Because each context in `src/ssra_api/<context>/` has isolated `api/`, `application/`, `domain/`, and `infrastructure/` layers enforced by `import-linter`, extracting a context into a standalone FastAPI service requires only wrapping its router in a new `pyproject.toml` and pointing its repository to a dedicated database schema.
