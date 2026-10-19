"""FastAPI application for services/agent-runtime (LangGraph + AG-UI SSE endpoint)."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict
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
from ssra_runtime.graphs import SSRAConversationRuntime
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


def create_runtime_app(runtime: SSRAConversationRuntime | None = None) -> FastAPI:
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
        if request.method in ("POST", "PUT", "PATCH"):
            req_bytes = await request.body()
            if len(req_bytes) > _MAX_RUNTIME_BODY_BYTES:
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
        return {"status": "ok", "service": "ssra-agent-runtime"}

    @app.post("/v1/turns", response_model=RuntimeTurnResponse)
    async def execute_turn(body: AguiStreamRequest) -> RuntimeTurnResponse:
        event = make_conversation_event(
            body.message,
            locale=body.locale,
            channel=body.channel,
            thread_id=body.thread_id,
            rich_ui=not body.low_data_mode,
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
        return active_runtime.reconstruct_conversation(thread_id)

    @app.post("/v1/field-officer/assist", response_model=FieldOfficerAssistResponse)
    async def field_officer_assist(
        body: FieldOfficerAssistRequest,
    ) -> FieldOfficerAssistResponse:
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
        event = make_conversation_event(
            body.message,
            locale=body.locale,
            channel=body.channel,
            thread_id=body.thread_id,
            rich_ui=not body.low_data_mode,
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
