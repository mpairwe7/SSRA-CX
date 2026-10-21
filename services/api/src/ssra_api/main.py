"""FastAPI Modular Monolith (`services/api`) assembling all 8 bounded contexts (Section 10.2-10.4)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from ssra_core import McpErrorCode, SSRAError, ensure_w3c_traceparent
from ssra_core.deployment import is_reference_mode

from ssra_api.admin.api import router as admin_router
from ssra_api.analytics_api.api import router as analytics_router
from ssra_api.appointments.api import router as appointments_router
from ssra_api.cases.api import router as cases_router
from ssra_api.consent.api import router as consent_router
from ssra_api.conversations.api import router as conversations_router
from ssra_api.identity_link.api import router as identity_link_router
from ssra_api.knowledge_admin.api import router as knowledge_admin_router
from ssra_api.middleware import SECURITY_HEADERS, install_api_conventions_middleware


def create_api_app() -> FastAPI:
    """Create the SSRA Assist Core API FastAPI application assembling all 8 bounded contexts."""
    app = FastAPI(
        title="SSRA Assist Core API",
        version="0.1.0",
        openapi_version="3.1.0",
        description="Modular monolith API for SSRA Assist (South Sudan Revenue Authority).",
    )
    install_api_conventions_middleware(app)

    @app.middleware("http")
    async def reference_runtime_guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Keep process-local and synthetic API handlers unavailable outside explicit reference mode."""
        if not is_reference_mode():
            traceparent = ensure_w3c_traceparent(request.headers.get("traceparent"))
            error = SSRAError(
                code=McpErrorCode.UPSTREAM_UNAVAILABLE,
                message=(
                    "Core API is unavailable until approved providers and durable persistence "
                    "are configured; set SSRA_RUNTIME_MODE=reference only for local fixtures."
                ),
                status_code=503,
            )
            return JSONResponse(
                status_code=503,
                content=error.to_problem_details(
                    instance=str(request.scope.get("path", "/")), trace_id=traceparent
                ).model_dump(mode="json"),
                media_type="application/problem+json",
                headers={"traceparent": traceparent, **SECURITY_HEADERS},
            )
        response = await call_next(request)
        response.headers["X-SSRA-Runtime-Mode"] = "reference"
        return response

    @app.exception_handler(SSRAError)
    async def ssra_error_handler(request: Request, exc: SSRAError) -> JSONResponse:
        """Convert SSRAError exceptions into RFC 9457 Problem Details JSON responses."""
        traceparent = ensure_w3c_traceparent(request.headers.get("traceparent"))
        raw_path = str(request.scope.get("path", "/"))
        problem = exc.to_problem_details(instance=raw_path, trace_id=traceparent)
        return JSONResponse(
            status_code=exc.status_code,
            content=problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"traceparent": traceparent, **SECURITY_HEADERS},
        )

    @app.get("/healthz", tags=["system"])
    async def healthz() -> dict[str, str]:
        """Return Core API service health status."""
        return {"status": "ok", "service": "ssra-api"}

    app.include_router(conversations_router)
    app.include_router(identity_link_router)
    app.include_router(cases_router)
    app.include_router(appointments_router)
    app.include_router(knowledge_admin_router)
    app.include_router(consent_router)
    app.include_router(analytics_router)
    app.include_router(admin_router)
    return app


app = create_api_app()
