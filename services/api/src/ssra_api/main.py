"""FastAPI Modular Monolith (`services/api`) assembling all 8 bounded contexts (Section 10.2-10.4)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from ssra_core import SSRAError

from ssra_api.admin.api import router as admin_router
from ssra_api.analytics_api.api import router as analytics_router
from ssra_api.appointments.api import router as appointments_router
from ssra_api.cases.api import router as cases_router
from ssra_api.consent.api import router as consent_router
from ssra_api.conversations.api import router as conversations_router
from ssra_api.identity_link.api import router as identity_link_router
from ssra_api.knowledge_admin.api import router as knowledge_admin_router
from ssra_api.middleware import install_api_conventions_middleware


def create_api_app() -> FastAPI:
    app = FastAPI(
        title="SSRA Assist Core API",
        version="0.1.0",
        openapi_version="3.1.0",
        description="Modular monolith API for SSRA Assist (South Sudan Revenue Authority).",
    )
    install_api_conventions_middleware(app)

    @app.exception_handler(SSRAError)
    async def ssra_error_handler(request: Request, exc: SSRAError) -> JSONResponse:
        traceparent = request.headers.get("traceparent")
        problem = exc.to_problem_details(instance=str(request.url.path), trace_id=traceparent)
        return JSONResponse(
            status_code=exc.status_code,
            content=problem.model_dump(mode="json"),
            media_type="application/problem+json",
        )

    @app.get("/healthz", tags=["system"])
    async def healthz() -> dict[str, str]:
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
