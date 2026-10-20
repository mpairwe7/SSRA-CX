"""FastAPI application for services/agent-runtime (LangGraph + AG-UI SSE endpoint)."""

from __future__ import annotations

import os
import re
import socket
from collections.abc import Awaitable, Callable
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from ssra_core import (
    AuthLevel,
    ChannelName,
    LocaleCode,
    McpErrorCode,
    SSRAError,
    ensure_w3c_traceparent,
)
from ssra_testing import make_conversation_event

from ssra_runtime.field_officer import (
    FieldOfficerAssistRequest,
    FieldOfficerAssistResponse,
    execute_field_officer_assist,
)
from ssra_runtime.graphs import SSRAConversationRuntime, validate_safe_subject_ref
from ssra_runtime.memory import HydratedCognitiveContext
from ssra_runtime.replay import ReconstructedTurnRecord
from ssra_runtime.schemas import RuntimeTurnResponse
from ssra_runtime.streaming import stream_agui_events

_VALID_HOST_RE = re.compile(r"^[A-Za-z0-9.\[\]:-]+$")
_MAX_RUNTIME_BODY_BYTES = 1_048_576
_RUNTIME_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


class AguiStreamRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    thread_id: str | None = None
    locale: LocaleCode = LocaleCode.EN
    channel: ChannelName = ChannelName.WEB
    auth_level: AuthLevel = AuthLevel.ANONYMOUS
    subject_ref: str | None = None
    confirmation_token: str | None = None
    idempotency_key: str | None = None
    low_data_mode: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_auth_subject_consistency(self) -> AguiStreamRequest:
        """Synchronize `subject_ref` and `auth_level` and bound `metadata` at the request adapter boundary (ASI03)."""
        if self.auth_level == AuthLevel.ANONYMOUS and self.subject_ref is not None:
            raise ValueError("Anonymous requests cannot specify a non-null subject_ref (ASI03)")
        if len(self.metadata) > 16 or any(
            len(k) > 64 or len(v) > 128 for k, v in self.metadata.items()
        ):
            raise ValueError("Request metadata exceeds entry count (16) or key/value length bounds")
        return self


class MemoryConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consented: bool
    preferred_locale: LocaleCode = LocaleCode.EN
    preferred_channel: ChannelName = ChannelName.WEB
    low_data_mode: bool = False
    high_contrast_a11y: bool = False
    voice_first_a11y: bool = False


def probe_valkey_redis(redis_url: str) -> str:
    """Probe Valkey/Redis TCP RESP `PING` health without external redis client dependencies."""
    if not redis_url:
        return "in_memory_fallback"
    parsed = urlparse(redis_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 6379
    try:
        with socket.create_connection((host, port), timeout=2.0) as sock:
            sock.sendall(b"*1\r\n$4\r\nPING\r\n")
            return "healthy" if b"+PONG" in sock.recv(32) else "unreachable"
    except OSError:
        return "unreachable"


def _collect_runtime_stack_status(active_runtime: SSRAConversationRuntime) -> dict[str, object]:
    """Collect sovereign GPU, local HF cache models, Qdrant vector store, and Valkey/Redis health."""
    hf_home = Path(os.environ.get("HF_HOME", "/home/developer/huggingface_cache"))
    hub_dir = hf_home / "hub"
    cached_entries = sorted(p.name for p in hub_dir.iterdir()) if hub_dir.exists() else []
    sunflower_models = [name for name in cached_entries if "Sunflower" in name]
    gpu_devs = sorted(p.name for p in Path("/dev").glob("nvidia[0-9]*"))
    qdrant_url = os.environ.get("SSRA_QDRANT_URL", "").strip().rstrip("/")
    qdrant_points = active_runtime.preference_store.qdrant_episodic_points_count(force_probe=True)
    qdrant_status = (
        "healthy"
        if (qdrant_url and qdrant_points is not None)
        else ("unreachable" if qdrant_url else "in_memory_fallback")
    )
    return {
        "service": "ssra-agent-runtime",
        "hf_offline_mode": os.environ.get("HF_HUB_OFFLINE") == "1",
        "hf_cached_entries_count": len(cached_entries),
        "sunflower_models": sunflower_models,
        "gpu_devices": gpu_devs,
        "qdrant_status": qdrant_status,
        "qdrant_episodic_points": qdrant_points or 0,
        "valkey_status": probe_valkey_redis(os.environ.get("SSRA_REDIS_URL", "")),
    }


async def _read_bounded_runtime_body(request: Request, max_bytes: int) -> bytes | None:
    """Check Content-Length and stream request chunks while enforcing max_bytes before buffering."""
    content_len_str = request.headers.get("content-length")
    if content_len_str and content_len_str.isdigit() and int(content_len_str) > max_bytes:
        return None
    if request.method not in ("POST", "PUT", "PATCH"):
        return b""
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > max_bytes:
            return None
        chunks.append(chunk)
    raw = b"".join(chunks)
    request._body = raw  # pyright: ignore[reportPrivateUsage]
    return raw


def create_runtime_app(runtime: SSRAConversationRuntime | None = None) -> FastAPI:
    """Create the FastAPI application for services/agent-runtime with security middleware and SSE streaming."""
    app = FastAPI(
        title="SSRA Assist Agent Runtime",
        version="0.1.0",
        openapi_version="3.1.0",
    )
    active_runtime = runtime or SSRAConversationRuntime()

    @app.middleware("http")
    async def runtime_security_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Enforce RFC 9112 Host validation, streaming payload bounds, traceparent, and security headers."""
        raw_path = str(request.scope.get("path", "/"))
        tp = ensure_w3c_traceparent(request.headers.get("traceparent"))
        host_header = request.headers.get("host", "localhost")
        if not host_header or not _VALID_HOST_RE.match(host_header):
            err = SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                "Malformed HTTP Host header rejected per RFC 9112 §3.2 (CVE-2026-48710)",
                status_code=400,
            )
            return JSONResponse(
                status_code=400,
                content=err.to_problem_details(instance=raw_path, trace_id=tp).model_dump(
                    mode="json"
                ),
                media_type="application/problem+json",
                headers={"traceparent": tp, **_RUNTIME_SECURITY_HEADERS},
            )
        if await _read_bounded_runtime_body(request, _MAX_RUNTIME_BODY_BYTES) is None:
            err = SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                f"Request body exceeds maximum allowed size of {_MAX_RUNTIME_BODY_BYTES} bytes",
                status_code=413,
            )
            return JSONResponse(
                status_code=413,
                content=err.to_problem_details(instance=raw_path, trace_id=tp).model_dump(
                    mode="json"
                ),
                media_type="application/problem+json",
                headers={"traceparent": tp, **_RUNTIME_SECURITY_HEADERS},
            )
        response = await call_next(request)
        response.headers["traceparent"] = tp
        for hk, hv in _RUNTIME_SECURITY_HEADERS.items():
            response.headers.setdefault(hk, hv)
        return response

    @app.exception_handler(SSRAError)
    async def ssra_error_handler(request: Request, exc: SSRAError) -> JSONResponse:
        """Format SSRAError exceptions as RFC 9457 Problem Details JSON responses."""
        raw_path = str(request.scope.get("path", "/"))
        tp = ensure_w3c_traceparent(request.headers.get("traceparent"))
        problem = exc.to_problem_details(instance=raw_path, trace_id=tp)
        return JSONResponse(
            status_code=exc.status_code,
            content=problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"traceparent": tp, **_RUNTIME_SECURITY_HEADERS},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Format FastAPI RequestValidationError exceptions as RFC 9457 Problem Details 422 responses."""
        raw_path = str(request.scope.get("path", "/"))
        tp = ensure_w3c_traceparent(request.headers.get("traceparent"))
        err = SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            f"Runtime request validation failed ({len(exc.errors())} error(s))",
            status_code=422,
        )
        return JSONResponse(
            status_code=422,
            content=err.to_problem_details(instance=raw_path, trace_id=tp).model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"traceparent": tp, **_RUNTIME_SECURITY_HEADERS},
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Return runtime service health status."""
        return {"status": "ok", "service": "ssra-agent-runtime"}

    @app.get("/v1/runtime/stack-status")
    def runtime_stack_status() -> dict[str, object]:
        """Return sovereign GPU, local HF cache models, Qdrant vector store, and Valkey/Redis health."""
        return _collect_runtime_stack_status(active_runtime)

    def _verify_subject_header(subject_ref: str, x_ssra_subject_ref: str | None) -> str:
        """Validate `subject_ref` and enforce `X-SSRA-Subject-Ref` header parity when present."""
        safe_sub = validate_safe_subject_ref(subject_ref, auth_level=AuthLevel.T1_TIN_BOUND)
        if x_ssra_subject_ref is not None and x_ssra_subject_ref.strip() != safe_sub:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "X-SSRA-Subject-Ref header mismatch with path subject_ref (ASI03)",
                status_code=403,
            )
        return safe_sub

    @app.post("/v1/memory/{subject_ref}/consent", response_model=HydratedCognitiveContext)
    def configure_memory_consent(
        subject_ref: str,
        body: MemoryConsentRequest,
        x_ssra_subject_ref: str | None = Header(default=None, alias="X-SSRA-Subject-Ref"),
    ) -> HydratedCognitiveContext:
        """Configure Tier 2/4 memory continuity consent and Tier 3 accessibility/channel preferences."""
        safe_sub = _verify_subject_header(subject_ref, x_ssra_subject_ref)
        active_runtime.preference_store.upsert_preferences(
            subject_ref=safe_sub,
            preferred_locale=body.preferred_locale,
            preferred_channel=body.preferred_channel,
            low_data_mode=body.low_data_mode,
            high_contrast_a11y=body.high_contrast_a11y,
            voice_first_a11y=body.voice_first_a11y,
        )
        active_runtime.preference_store.set_memory_continuity_consent(
            safe_sub,
            consented=body.consented,
        )
        return active_runtime.preference_store.hydrate_subject_context(safe_sub)

    @app.get("/v1/memory/{subject_ref}", response_model=HydratedCognitiveContext)
    def get_hydrated_memory(
        subject_ref: str,
        x_ssra_subject_ref: str | None = Header(default=None, alias="X-SSRA-Subject-Ref"),
    ) -> HydratedCognitiveContext:
        """Hydrate Tiers 2, 3, and 4 cognitive memory snapshot for a validated `subject_ref`."""
        safe_sub = _verify_subject_header(subject_ref, x_ssra_subject_ref)
        return active_runtime.preference_store.hydrate_subject_context(safe_sub)

    @app.delete("/v1/memory/{subject_ref}")
    def erase_subject_memory(
        subject_ref: str,
        x_ssra_subject_ref: str | None = Header(default=None, alias="X-SSRA-Subject-Ref"),
    ) -> dict[str, object]:
        """Execute immediate Right-to-Erasure across Tiers 2, 3, 4 and Qdrant vector store."""
        safe_sub = _verify_subject_header(subject_ref, x_ssra_subject_ref)
        erased = active_runtime.preference_store.delete_subject_preferences(safe_sub)
        remaining = active_runtime.preference_store.qdrant_episodic_points_count(safe_sub)
        if remaining is None or (os.environ.get("SSRA_QDRANT_URL") and not erased):
            raise SSRAError(
                McpErrorCode.UPSTREAM_UNAVAILABLE,
                "Qdrant vector store erasure failed; Right-to-Erasure incomplete",
                status_code=503,
            )
        aud = active_runtime.audit_ledger.append(
            actor="ssra-agent-runtime",
            on_behalf_of=safe_sub,
            action="memory.subject.right_to_erasure",
            resource=f"memory://{safe_sub}",
            payload={"erased": erased},
        )
        return {
            "subject_ref": safe_sub,
            "erased": erased,
            "qdrant_remaining_points": remaining,
            "audit_event_hash": aud.hash,
        }

    @app.post("/v1/turns", response_model=RuntimeTurnResponse)
    async def execute_turn(body: AguiStreamRequest) -> RuntimeTurnResponse:
        """Execute a synchronous 11-node LangGraph conversation turn."""
        event = make_conversation_event(
            body.message,
            locale=body.locale,
            channel=body.channel,
            thread_id=body.thread_id,
            rich_ui=not body.low_data_mode,
            metadata=body.metadata,
        )
        return active_runtime.run_turn(
            event,
            auth_level=body.auth_level,
            subject_ref=body.subject_ref,
            confirmation_token=body.confirmation_token,
            idempotency_key=body.idempotency_key,
        )

    @app.get("/v1/turns/{thread_id}/replay", response_model=list[ReconstructedTurnRecord])
    async def replay_thread(thread_id: str) -> list[ReconstructedTurnRecord]:
        """Reconstruct turn-by-turn forensic replay records for a conversation thread."""
        return active_runtime.reconstruct_conversation(thread_id)

    @app.post("/v1/field-officer/assist", response_model=FieldOfficerAssistResponse)
    async def field_officer_assist(
        body: FieldOfficerAssistRequest,
    ) -> FieldOfficerAssistResponse:
        """Execute passkey-gated Field-Officer Assist tasks with WORM audit logging."""
        return execute_field_officer_assist(
            body,
            gateway=active_runtime.gateway,
            audit_ledger=active_runtime.audit_ledger,
        )

    @app.post("/v1/agui/stream")
    async def agui_stream(
        body: AguiStreamRequest,
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ) -> StreamingResponse:
        """Stream AG-UI protocol events over Server-Sent Events with Last-Event-ID resumption."""
        event = make_conversation_event(
            body.message,
            locale=body.locale,
            channel=body.channel,
            thread_id=body.thread_id,
            rich_ui=not body.low_data_mode,
            metadata=body.metadata,
        )
        turn = active_runtime.run_turn(
            event,
            auth_level=body.auth_level,
            subject_ref=body.subject_ref,
            confirmation_token=body.confirmation_token,
            idempotency_key=body.idempotency_key,
        )
        return StreamingResponse(
            stream_agui_events(turn, last_event_id=last_event_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    return app


app = create_runtime_app()
