# ADR-013: Python 3.14/3.15 Workspace, FastAPI 0.13x, and ASGI Server Selection

- **Status:** Proposed
- **Date:** 2026-10-16
- **Deciders:** Founding Principal Architect / Staff Engineer, SSRA Technical Lead
- **Reversal Cost:** Low
- **References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Section 10.1, Appendix A

---

## 1. Problem Statement

How do we standardise the Python monorepo toolchain (`uv`, Ruff, `basedpyright`), reconcile the FastAPI version pin (`0.139.2` vs. `0.143.0`), and choose between Uvicorn and Granian for containerised ASGI execution?

## 2. Context

Section 10.1 specifies:
- Python 3.14 in production now, with Python 3.15 (released 9 October 2026) in the CI matrix (and local dev compatibility where system Python/wheels require `>=3.12,<3.16` during bootstrap);
- `uv` workspaces, Ruff for linting/formatting, and `basedpyright` in strict mode;
- FastAPI pinned on the latest `0.13x` release (`0.139.2`, released 2026-07-16), while noting that PyPI also has `0.143.0` (released 2026-10-08, within the 7-day cooldown);
- Uvicorn as a single process per container scaled horizontally by Kubernetes HPA/KEDA, with Granian benchmarked in an ADR.

## 3. Options Considered

1. **Multi-worker Gunicorn + Uvicorn Workers per Container:** Hides worker memory leaks from Kubernetes liveness probes and complicates CPU limit tuning.
2. **Single-Process Uvicorn `0.54.0` (`uvloop` + `httptools`) per Container in Production + Granian `2.8.4` Benchmark Profile (Selected):** Standard, battle-tested ASGI lifecycle with OpenTelemetry auto-instrumentation, while keeping Granian ready as a drop-in Rust-based ASGI server after load-test verification.

## 4. Decision

We adopt Option 2:

1. **Workspace & Type/Lint Toolchain (`pyproject.toml`):**
   - Manage all Python services (`services/*`), MCP servers (`mcp-servers/*`), and shared libraries (`libs/*`) in a single root `uv` workspace with `exclude-newer = "2026-10-09T23:59:59Z"` (7-day cooldown).
   - Enforce `ruff==0.17.0` (lint + format) and `basedpyright==1.40.2` (`typeCheckingMode = "strict"`), plus `import-linter==2.15` for hexagonal boundaries.
2. **FastAPI Version Pin (`0.139.2` Baseline) & RFC 9457 / Outbox Conventions:**
   - Pin `fastapi==0.139.2` (`sha256: b9ad015a835173d59865e2f5d8296fbc2b317bf56a2ba1a5bfbdd03de2fd4b1c`) to strictly match the `0.13x` specification in Section 10.1 and Appendix A.
   - Override both `SSRAError` and `RequestValidationError` handlers across `services/api`, `services/agent-runtime`, and `services/channel-gateway` to emit RFC 9457 `application/problem+json` with `traceparent` (`ensure_w3c_traceparent`), `Strict-Transport-Security`, and `Permissions-Policy` headers.
   - Stage bounded, PII-redacted CloudEvents 1.0 domain events into `TransactionalOutboxStore` (`outbox_events` table) across bounded context mutations (`conversations`, `cases`, `consent`, `admin`), enforce PostgreSQL 18 RLS across `conversations`, `cases`, and `handoffs`, and support resumable `Last-Event-ID` AG-UI SSE streams (`services/agent-runtime`).
3. **ASGI Server (Uvicorn `0.54.0` Default vs. Granian `2.8.4` Benchmark):**
   - Run **one Uvicorn process per container** (`uvicorn --no-access-log --loop uvloop --http httptools`) and scale replicas horizontally via Kubernetes HPA/KEDA.
   - Provide a benchmark target comparing `uvicorn==0.54.0` and `granian==2.8.4` under `k6` SSE streaming load (`services/agent-runtime`). Uvicorn remains the default because its OpenTelemetry ASGI middleware and graceful SSE connection draining semantics are fully verified across all dependencies.

## 5. Consequences

- **Positive:** Deterministic 1-process-per-pod failure domain, full OpenTelemetry compatibility, and strict static typing across all 7 shared libraries and 16 deployables.
- **Negative / Trade-offs:** Higher pod count on Kubernetes compared to multi-process containers, mitigated by lightweight container footprints.

## 6. Reversal Cost & Migration Path

- **Reversal Cost:** Low. Switching between Uvicorn and Granian changes only the container `ENTRYPOINT` command.
