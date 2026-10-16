# ADR-003: Dual Orchestration — LangGraph for Conversation Control and Temporal for Durable Workflows

- **Status:** Proposed
- **Date:** 2026-10-16
- **Deciders:** Founding Principal Architect / Staff Engineer, SSRA Technical Lead
- **Reversal Cost:** High
- **References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 5, 6, 7, 10.1, 10.2, 17, Appendix A

---

## 1. Problem Statement

How do we separate low-latency, stateful, interruptible conversational turn orchestration from long-running, retry-heavy background business workflows (such as legal document ingestion, eval gates, and multi-day case SLA timers)?

## 2. Context

SSRA Assist requires two fundamentally different kinds of state machines:
1. **Sub-second to multi-second conversational turns** (Web TTFT p95 ≤ 1.5 s, grounded answer p95 ≤ 6 s, tool-backed answer p95 ≤ 8 s) that need explicit graph edges, deterministic routing before any LLM runs, input/output guardrails, token/tool budgets, and durable human-in-the-loop pause/resume (`interrupt()`) when a user must confirm a `T2` or `T3` action over Web PWA, WhatsApp, or USSD.
2. **Minutes-to-days durable business workflows** that must survive pod restarts, upstream outages, and multi-day human approvals: Knowledge Release pipelines (Docling OCR/parsing → legal chunking → embedding → eval regression gate → one-step rollback), `Case` and `Handoff` SLA timers, and consent-verified outbound notification campaigns.

Using free-roaming multi-agent swarms violates Principle 1 (Determinism over cleverness) and Principle 9 (Reconstructability). Conversely, running sub-second token-streaming turns inside Temporal activities adds unnecessary latency, while running multi-day SLA timers inside LangGraph threads bloats conversational checkpoint tables.

## 3. Options Considered

1. **Free-Roaming Multi-Agent Framework (e.g., autonomous agent swarms / dynamic handoffs):** Unpredictable latency, high token burn, vulnerable to OWASP ASI01/ASI08 cascading agent failures, and impossible to prove deterministic policy gates. Rejected.
2. **Custom Hand-Rolled State Machine + Celery/Redis Queues:** Lacks first-class graph checkpointing/interrupts for conversations and lacks deterministic workflow replay/versioning for multi-day SLAs and knowledge releases.
3. **LangGraph `1.2.x` (Postgres Checkpointer) for Conversational Control + Temporal (`temporalio` `1.34.0`) for Durable Background Workflows (Selected):** Pairs an explicit, single-supervisor LangGraph state machine for turn-by-turn conversation with Temporal for long-running business processes.

## 4. Decision

We adopt Option 3 with strict separation of responsibilities:

1. **Conversational Control (`services/agent-runtime` — LangGraph `1.2.14` + `langgraph-checkpoint-postgres` `3.1.2`):**
   - Implement one explicit **Supervisor Graph** (`graphs/conversation.py`) executing the 11 ordered nodes defined in Section 6.1 (`ingress` → `deterministic_router` → `input_guard` → `understand` → `policy_gate` → specialist subgraph → `tool_exec` → `compose` → `output_guard` → `confirm` → `egress`).
   - Specialist subgraphs (`knowledge_qa`, `guided_journey`, `self_service`, `calculator`, `verify_official`, `complaint_intake`, `handoff`) are deterministic subgraphs invoked by the supervisor—never autonomous peer swarms.
   - Persist thread state in PostgreSQL 18 via `AsyncPostgresSaver` keyed by `thread_id` in all environments except unit tests (which may use `InMemorySaver`).
   - Use LangGraph `interrupt()` in the `confirm` node for all `T2` and `T3` state-changing actions, resuming only after receiving a user confirmation event bound to the action digest.
2. **Durable Background Workflows (`services/workers` — `temporalio` `1.34.0`):**
   - Execute Knowledge Release workflows (Docling ingestion, legal-structure chunking, embedding/reranker indexing, automated eval gate, snapshot activation/rollback).
   - Execute `Case` and `Handoff` SLA timers and escalation workflows.
   - Execute consent-checked notification campaigns and upstream reconciliation polling.

## 5. Consequences

- **Positive:**
  - Every conversational turn follows a verifiable, reconstructable path with bounded LLM calls (`understand` and `compose` only) and native pause/resume for `T2`/`T3` confirmations.
  - Long-running ingestion, eval suites, and SLA timers have durable state, automatic retries, and visibility in Temporal without blocking real-time chat workers.
- **Negative / Trade-offs:**
  - Operates two state engines (LangGraph checkpointer tables in PostgreSQL + Temporal server), mitigated by running Temporal against the same CloudNativePG PostgreSQL 18 cluster in local and initial NCA deployments.

## 6. Reversal Cost & Migration Path

- **Reversal Cost:** High. Domain logic inside graph nodes and Temporal activities is kept framework-agnostic in `libs/` and `application/` use cases so orchestration wrappers can be replaced without rewriting business rules, guardrails, or MCP tools.
