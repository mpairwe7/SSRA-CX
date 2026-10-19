"""Governed AI Gateway HTTP Service (`agentgateway` reference enforcement server — Sections 5, 8.1-8.5, 13).

Enforces:
- Stateless MCP 2026-07-28 header routing (`Mcp-Method` and `Mcp-Name`)
- `tools/list` caching for server-declared `ttlMs`
- Per-invocation OPA policy, OAuth 2.1 RFC 8693 token exchange, and tool description SHA-256 hash pinning
- Daily USD spend cap (`daily_usd_cap = 150.00`) with alert/cutoff (`RATE_LIMITED`)
- Reserved A2A v1.0 boundary (`/a2a/v1`) blocked while stub `"enabled": false` (ADR-014)
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

from fastapi import FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse
from ssra_core import AuthLevel, McpErrorCode, RiskTier, SSRAError
from ssra_mcp import MCP_PROTOCOL_VERSION, validate_mcp_transport_headers
from ssra_security import compute_least_privilege_mcp_scope

from ssra_runtime.tools import GovernedMcpGatewayClient

_SAFE_SUBJECT_REF_RE = re.compile(r"^[A-Za-z0-9_:-]{3,64}$")


def create_agentgateway_app(*, daily_usd_cap: float = 150.0) -> FastAPI:
    app = FastAPI(title="SSRA Assist AI Gateway (agentgateway)", version="1.0.0")
    gateway = GovernedMcpGatewayClient()
    tools_list_cache: dict[str, tuple[float, str, dict[str, Any]]] = {}
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

    @app.get("/.well-known/oauth-protected-resource/gateway")
    @app.get("/.well-known/oauth-protected-resource")
    async def oauth_protected_resource() -> dict[str, Any]:
        return {
            "resource": "https://mcp.ssra.gov.ss/gateway",
            "authorization_servers": ["https://sso.ssra.gov.ss/realms/ssra"],
            "scopes_supported": [f"mcp:{s}:read" for s in sorted(gateway.servers)],
            "bearer_methods_supported": ["header"],
            "mcp_protocol_version": MCP_PROTOCOL_VERSION,
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
        authorization: str | None = Header(default=None, alias="Authorization"),
        if_none_match: str | None = Header(default=None, alias="If-None-Match"),
        x_ssra_auth_level: str = Header(default="ANONYMOUS", alias="X-SSRA-Auth-Level"),
        x_ssra_subject_ref: str | None = Header(default=None, alias="X-SSRA-Subject-Ref"),
        traceparent: str | None = Header(default=None, alias="traceparent"),
    ) -> Response:
        try:
            validate_mcp_transport_headers(
                request.headers.get("host"),
                request.headers.get("origin"),
            )
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
                now_ms = time.monotonic() * 1000.0
                cached = tools_list_cache.get(mcp_name)
                if cached is None or now_ms >= cached[0]:
                    listing = srv.handle_list_tools()
                    for t_item in listing.get("tools", []):
                        t_key = f"{mcp_name}.{t_item['name']}"
                        if gateway.pinned_description_hashes.get(t_key) != t_item.get(
                            "descriptionSha256"
                        ):
                            raise SSRAError(
                                McpErrorCode.NOT_AUTHORIZED,
                                f"Gateway detected tool description hash drift on tools/list for '{t_key}'",
                                status_code=403,
                            )
                    ttl_ms = int(listing.get("_meta", {}).get("ttlMs", srv.ttl_ms))
                    digest = hashlib.sha256(
                        json.dumps(listing, sort_keys=True).encode("utf-8")
                    ).hexdigest()[:16]
                    etag = f'W/"{digest}"'
                    cached = (now_ms + ttl_ms, etag, listing)
                    tools_list_cache[mcp_name] = cached

                _, etag, listing_payload = cached
                ttl_sec = max(1, int(srv.ttl_ms // 1000))
                cache_headers = {
                    "ETag": etag,
                    "Cache-Control": f"private, max-age={ttl_sec}",
                }
                if if_none_match and if_none_match.strip() == etag:
                    return Response(status_code=304, headers=cache_headers)
                return JSONResponse(
                    status_code=200,
                    content=listing_payload,
                    headers=cache_headers,
                )

            try:
                resolved_auth_level = AuthLevel(x_ssra_auth_level)
            except ValueError as exc:
                raise SSRAError(
                    McpErrorCode.NOT_AUTHORIZED,
                    f"Invalid X-SSRA-Auth-Level header '{x_ssra_auth_level}'",
                    status_code=401,
                ) from exc

            resolved_subject_ref = x_ssra_subject_ref.strip() if x_ssra_subject_ref else None
            if resolved_subject_ref is not None and not _SAFE_SUBJECT_REF_RE.match(
                resolved_subject_ref
            ):
                raise SSRAError(
                    McpErrorCode.NOT_AUTHORIZED,
                    "Malformed X-SSRA-Subject-Ref header rejected",
                    status_code=403,
                )
            if authorization:
                raw_tok = authorization.removeprefix("Bearer ").strip()
                claims = gateway.token_service.verify_exchanged_token(
                    raw_tok,
                    expected_audience=srv.audience,
                    required_tier=RiskTier.T0,
                    expected_resource=f"https://mcp.ssra.gov.ss/servers/{srv.audience}",
                )
                if (
                    resolved_subject_ref is not None
                    and claims.sub is not None
                    and resolved_subject_ref != claims.sub
                ):
                    raise SSRAError(
                        McpErrorCode.NOT_AUTHORIZED,
                        "Confused deputy blocked: X-SSRA-Subject-Ref does not match Bearer token sub claim",
                        status_code=403,
                    )
                if x_ssra_auth_level != "ANONYMOUS" and resolved_auth_level != claims.auth_level:
                    raise SSRAError(
                        McpErrorCode.NOT_AUTHORIZED,
                        "Confused deputy blocked: X-SSRA-Auth-Level does not match Bearer token auth_level claim",
                        status_code=403,
                    )
                resolved_auth_level = claims.auth_level
                resolved_subject_ref = claims.sub
            elif resolved_auth_level == AuthLevel.ANONYMOUS and resolved_subject_ref is not None:
                raise SSRAError(
                    McpErrorCode.NOT_AUTHORIZED,
                    "Anonymous MCP request cannot assert X-SSRA-Subject-Ref without authentication",
                    status_code=403,
                )

            body = await request.json()
            meta = body.get("_meta", {})
            if isinstance(meta, dict):
                proto = meta.get("protocolVersion", MCP_PROTOCOL_VERSION)
                if proto != MCP_PROTOCOL_VERSION:
                    raise SSRAError(
                        McpErrorCode.VALIDATION_FAILED,
                        f"Unsupported MCP protocolVersion '{proto}'; expected '{MCP_PROTOCOL_VERSION}'",
                        status_code=400,
                    )
            body_method = body.get("method")
            if body_method and body_method != mcp_method:
                raise SSRAError(
                    McpErrorCode.VALIDATION_FAILED,
                    "Mcp-Method header does not match body method",
                    status_code=400,
                )

            params = dict(body.get("params", {}))
            if mcp_method.startswith("tasks/"):
                task_res = srv.handle_task_method(
                    mcp_method,
                    params,
                    caller_sub=resolved_subject_ref or "ANONYMOUS",
                )
                return JSONResponse(status_code=200, content=task_res)

            tool_name = str(params.get("name", ""))
            arguments = dict(params.get("arguments", {}))

            artifact = gateway.invoke_tool(
                server_name=mcp_name,
                tool_name=tool_name,
                arguments=arguments,
                auth_level=resolved_auth_level,
                subject_ref=resolved_subject_ref,
                traceparent=traceparent,
            )
            return JSONResponse(
                status_code=200,
                content=artifact.model_dump(mode="json"),
            )
        except SSRAError as err:
            err_headers: dict[str, str] = {}
            if err.status_code in (401, 403) and mcp_name:
                aud = f"mcp-{mcp_name}"
                res_meta_url = (
                    f"https://mcp.ssra.gov.ss/.well-known/oauth-protected-resource/servers/{aud}"
                )
                target_tier = (
                    RiskTier.T3 if err.code == McpErrorCode.STEP_UP_REQUIRED else RiskTier.T1
                )
                req_scope = compute_least_privilege_mcp_scope(aud, target_tier)
                oauth_err = (
                    "insufficient_scope"
                    if err.code == McpErrorCode.STEP_UP_REQUIRED
                    else err.code.value.lower()
                )
                err_headers["WWW-Authenticate"] = (
                    f'Bearer realm="{aud}", '
                    f'resource="https://mcp.ssra.gov.ss/servers/{aud}", '
                    f'resource_metadata="{res_meta_url}", '
                    f'scope="{req_scope}", '
                    f'error="{oauth_err}"'
                )
            return JSONResponse(
                status_code=err.status_code,
                content={"error": {"code": err.code.value, "message": err.message}},
                headers=err_headers,
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
