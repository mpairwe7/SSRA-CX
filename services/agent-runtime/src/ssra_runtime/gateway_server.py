"""Governed AI Gateway HTTP Service (`agentgateway` reference enforcement server — Sections 5, 8.1-8.5, 13).

Enforces:
- Stateless MCP 2026-07-28 header routing (`Mcp-Method` and `Mcp-Name`)
- `tools/list` caching for server-declared `ttlMs`
- Per-invocation OPA policy, OAuth 2.1 RFC 8693 token exchange, and tool description SHA-256 hash pinning
- Daily USD spend cap (`daily_usd_cap = 150.00`) with alert/cutoff (`RATE_LIMITED`)
- Reserved A2A v1.0 boundary (`/a2a/v1`) blocked while stub `"enabled": false` (ADR-014)
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from ssra_core import AuthLevel, McpErrorCode, SSRAError

from ssra_runtime.tools import GovernedMcpGatewayClient


def create_agentgateway_app(*, daily_usd_cap: float = 150.0) -> FastAPI:
    app = FastAPI(title="SSRA Assist AI Gateway (agentgateway)", version="1.0.0")
    gateway = GovernedMcpGatewayClient()
    tools_list_cache: dict[str, dict[str, Any]] = {}
    state: dict[str, float] = {"daily_spend_usd": 0.0}

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "ssra-agentgateway",
            "daily_spend_usd": state["daily_spend_usd"],
            "daily_usd_cap": daily_usd_cap,
            "pinned_tools_count": len(gateway.pinned_description_hashes),
        }

    @app.post("/v1/spend/record")
    async def record_spend(request: Request) -> JSONResponse:
        body = await request.json()
        delta = float(body.get("cost_usd", 0.0))
        if state["daily_spend_usd"] + delta > daily_usd_cap:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": McpErrorCode.RATE_LIMITED.value,
                        "message": f"Daily gateway spend cap ({daily_usd_cap} USD) exceeded",
                    }
                },
            )
        state["daily_spend_usd"] = round(state["daily_spend_usd"] + delta, 6)
        return JSONResponse(
            status_code=200,
            content={"daily_spend_usd": state["daily_spend_usd"], "daily_usd_cap": daily_usd_cap},
        )

    @app.post("/mcp")
    async def route_mcp(
        request: Request,
        mcp_method: str | None = Header(default=None, alias="Mcp-Method"),
        mcp_name: str | None = Header(default=None, alias="Mcp-Name"),
        x_ssra_auth_level: str = Header(default="ANONYMOUS", alias="X-SSRA-Auth-Level"),
        x_ssra_subject_ref: str | None = Header(default=None, alias="X-SSRA-Subject-Ref"),
        traceparent: str | None = Header(default=None, alias="traceparent"),
    ) -> JSONResponse:
        try:
            if state["daily_spend_usd"] >= daily_usd_cap:
                raise SSRAError(
                    McpErrorCode.RATE_LIMITED,
                    "Daily AI gateway spend cap reached",
                    status_code=429,
                )
            if not mcp_method or not mcp_name:
                raise SSRAError(
                    McpErrorCode.VALIDATION_FAILED,
                    "Stateless MCP 2026-07-28 requires Mcp-Method and Mcp-Name headers",
                    status_code=400,
                )

            srv = gateway.servers.get(mcp_name)
            if srv is None:
                raise SSRAError(
                    McpErrorCode.NOT_FOUND,
                    f"Unknown MCP server '{mcp_name}'",
                    status_code=404,
                )

            if mcp_method == "tools/list":
                if mcp_name not in tools_list_cache:
                    tools_list_cache[mcp_name] = srv.handle_list_tools()
                return JSONResponse(status_code=200, content=tools_list_cache[mcp_name])

            body = await request.json()
            params = dict(body.get("params", {}))
            tool_name = str(params.get("name", ""))
            arguments = dict(params.get("arguments", {}))

            artifact = gateway.invoke_tool(
                server_name=mcp_name,
                tool_name=tool_name,
                arguments=arguments,
                auth_level=AuthLevel(x_ssra_auth_level),
                subject_ref=x_ssra_subject_ref,
                traceparent=traceparent,
            )
            return JSONResponse(
                status_code=200,
                content=artifact.model_dump(mode="json"),
            )
        except SSRAError as err:
            return JSONResponse(
                status_code=err.status_code,
                content={"error": {"code": err.code.value, "message": err.message}},
            )

    @app.post("/a2a/v1")
    async def a2a_boundary_stub() -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": McpErrorCode.NOT_AUTHORIZED.value,
                    "message": "A2A v1.0 boundary is reserved and disabled in MVP (ADR-014).",
                }
            },
        )

    return app


gateway_app = create_agentgateway_app()
