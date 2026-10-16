"""FastAPI application for services/agent-runtime (LangGraph + AG-UI SSE endpoint)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict
from ssra_core import (
    AuthLevel,
    ChannelName,
    LocaleCode,
    SSRAError,
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


def create_runtime_app() -> FastAPI:
    app = FastAPI(
        title="SSRA Assist Agent Runtime",
        version="0.1.0",
        openapi_version="3.1.0",
    )
    runtime = SSRAConversationRuntime()

    @app.exception_handler(SSRAError)
    async def ssra_error_handler(request: Request, exc: SSRAError) -> JSONResponse:
        problem = exc.to_problem_details(instance=str(request.url.path))
        return JSONResponse(
            status_code=exc.status_code,
            content=problem.model_dump(mode="json"),
            media_type="application/problem+json",
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
        return runtime.run_turn(
            event,
            auth_level=body.auth_level,
            subject_ref=body.subject_ref,
            confirmation_token=body.confirmation_token,
            idempotency_key=body.idempotency_key,
        )

    @app.get("/v1/turns/{thread_id}/replay", response_model=list[ReconstructedTurnRecord])
    async def replay_thread(thread_id: str) -> list[ReconstructedTurnRecord]:
        return runtime.reconstruct_conversation(thread_id)

    @app.post("/v1/field-officer/assist", response_model=FieldOfficerAssistResponse)
    async def field_officer_assist(
        body: FieldOfficerAssistRequest,
    ) -> FieldOfficerAssistResponse:
        return execute_field_officer_assist(
            body,
            gateway=runtime.gateway,
            audit_ledger=runtime.audit_ledger,
        )

    @app.post("/v1/agui/stream")
    async def agui_stream(body: AguiStreamRequest) -> StreamingResponse:
        event = make_conversation_event(
            body.message,
            locale=body.locale,
            channel=body.channel,
            thread_id=body.thread_id,
            rich_ui=not body.low_data_mode,
        )
        turn = runtime.run_turn(
            event,
            auth_level=body.auth_level,
            subject_ref=body.subject_ref,
            confirmation_token=body.confirmation_token,
            idempotency_key=body.idempotency_key,
        )
        return StreamingResponse(
            stream_agui_events(turn),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    return app


app = create_runtime_app()
