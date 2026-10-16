"""Stateless MCP Revision 2026-07-28 Server Base over Streamable HTTP (Section 8).

Implements:
- Stateless 2026-07-28 protocol check (`_meta.protocolVersion == "2026-07-28"`, no initialize session)
- `Mcp-Method` and `Mcp-Name` HTTP header verification for gateway routing
- `tools/list` cacheable response with `ttlMs` and SHA-256 description hash pinning
- JSON Schema 2020-12 validation of tool input and output schemas
- OAuth 2.1 audience & RFC 8693 `subject_ref` verification for T1-T3 tools
- Single-use `confirmation_token` + `idempotency_key` verification for T2/T3 state-changing tools
- Mandatory `provenance` and `data_classification` envelope on every tool result
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

import jsonschema
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from ssra_core import AuthLevel, McpErrorCode, RiskTier, SSRAError, new_id, utc_now
from ssra_security import (
    ConfirmationTokenManager,
    HashChainedAuditLedger,
    SubjectTokenClaims,
    TokenExchangeService,
)

MCP_PROTOCOL_VERSION = "2026-07-28"
JSON_SCHEMA_2020_12 = "https://json-schema.org/draft/2020-12/schema"


class ToolAnnotations(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    readOnlyHint: bool = True
    destructiveHint: bool = False
    idempotentHint: bool = True
    openWorldHint: bool = False


class ProvenanceEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    system: str
    record_id: str
    retrieved_at: datetime
    as_of: str


@dataclass(frozen=True)
class ToolContext:
    server_name: str
    tool_name: str
    tier: RiskTier
    claims: SubjectTokenClaims
    traceparent: str | None


ToolHandler = Callable[[dict[str, Any], ToolContext], dict[str, Any]]


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    description: str
    tier: RiskTier
    annotations: ToolAnnotations
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    data_classification: Literal["PUBLIC", "CONFIDENTIAL_TAXPAYER", "INTERNAL_STAFF"]
    upstream_system: str
    handler: ToolHandler

    @property
    def description_sha256(self) -> str:
        return hashlib.sha256(self.description.encode("utf-8")).hexdigest()


class McpRequestMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    protocolVersion: str = MCP_PROTOCOL_VERSION
    clientCapabilities: dict[str, Any] = Field(default_factory=dict)


class StatelessMcpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str
    params: dict[str, Any] = Field(default_factory=dict)
    meta: McpRequestMeta = Field(default_factory=McpRequestMeta, alias="_meta")


_DEPRECATED_METHOD_PREFIXES: tuple[str, ...] = ("roots/", "sampling/", "logging/")
_ALLOWED_MCP_METHODS: frozenset[str] = frozenset(
    {"tools/list", "tools/call", "tasks/create", "tasks/get", "tasks/cancel"}
)


class StatelessMcpServer:
    """Stateless 2026-07-28 MCP server speaking Streamable HTTP behind agentgateway."""

    def __init__(
        self,
        *,
        server_name: str,
        audience: str | None = None,
        ttl_ms: int = 300_000,
        token_service: TokenExchangeService | None = None,
        confirmation_manager: ConfirmationTokenManager | None = None,
        audit_ledger: HashChainedAuditLedger | None = None,
    ) -> None:
        self.server_name = server_name
        self.audience = audience or f"mcp-{server_name}"
        self.ttl_ms = ttl_ms
        self.token_service = token_service or TokenExchangeService()
        self.confirmation_manager = confirmation_manager or ConfirmationTokenManager()
        self.audit_ledger = audit_ledger or HashChainedAuditLedger()
        self._tools: dict[str, RegisteredTool] = {}
        self._idempotent_cache: dict[str, dict[str, Any]] = {}
        self._tasks: dict[str, dict[str, Any]] = {}

    @property
    def tools(self) -> dict[str, RegisteredTool]:
        return dict(self._tools)

    def register_tool(self, tool: RegisteredTool) -> None:
        if tool.tier == RiskTier.T4:
            raise ValueError("Principle 3: T4 is human-only; no MCP tool may exist at Tier T4.")
        # Validate schemas are valid JSON Schema 2020-12
        if tool.input_schema.get("$schema") != JSON_SCHEMA_2020_12:
            raise ValueError(f"Tool '{tool.name}' input_schema must declare $schema 2020-12")
        if tool.output_schema.get("$schema") != JSON_SCHEMA_2020_12:
            raise ValueError(f"Tool '{tool.name}' output_schema must declare $schema 2020-12")
        jsonschema.Draft202012Validator.check_schema(tool.input_schema)
        jsonschema.Draft202012Validator.check_schema(tool.output_schema)
        self._tools[tool.name] = tool

    def handle_list_tools(self) -> dict[str, Any]:
        return {
            "_meta": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "ttlMs": self.ttl_ms,
                "server": self.server_name,
            },
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "descriptionSha256": t.description_sha256,
                    "tier": t.tier.value,
                    "annotations": t.annotations.model_dump(),
                    "inputSchema": t.input_schema,
                    "outputSchema": t.output_schema,
                }
                for t in self._tools.values()
            ],
        }

    def handle_task_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """MCP 2026-07-28 Tasks extension for long-running operations (Section 8.1)."""
        if method == "tasks/create":
            task_id = new_id("task")
            task_rec = {
                "taskId": task_id,
                "status": "RUNNING",
                "operation": str(params.get("operation", "background_task")),
                "createdAt": utc_now().isoformat(),
            }
            self._tasks[task_id] = task_rec
            return {"_meta": {"protocolVersion": MCP_PROTOCOL_VERSION}, "task": task_rec}

        task_id = str(params.get("taskId", ""))
        rec = self._tasks.get(task_id)
        if rec is None:
            raise SSRAError(
                McpErrorCode.NOT_FOUND,
                f"Task '{task_id}' not found on server '{self.server_name}'",
                status_code=404,
            )
        if method == "tasks/cancel":
            rec["status"] = "CANCELLED"
        return {"_meta": {"protocolVersion": MCP_PROTOCOL_VERSION}, "task": rec}

    def handle_call_tool(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        bearer_token: str | None,
        traceparent: str | None = None,
    ) -> dict[str, Any]:
        tool = self._tools.get(tool_name)
        if tool is None:
            raise SSRAError(
                McpErrorCode.NOT_FOUND,
                f"Unknown tool '{tool_name}' on server '{self.server_name}'",
                status_code=404,
            )

        # 1. Verify OAuth 2.1 / RFC 8693 token
        if bearer_token:
            raw_tok = bearer_token.removeprefix("Bearer ").strip()
            claims = self.token_service.verify_exchanged_token(
                raw_tok,
                expected_audience=self.audience,
                required_tier=tool.tier,
            )
        else:
            if tool.tier != RiskTier.T0:
                raise SSRAError(
                    McpErrorCode.NOT_AUTHORIZED,
                    f"Tool '{tool_name}' requires OAuth 2.1 token at tier {tool.tier}",
                    status_code=401,
                )
            claims = SubjectTokenClaims(
                aud=self.audience,
                sub=None,
                auth_level=AuthLevel.ANONYMOUS,
                exp=utc_now(),
            )

        # 2. Extract and validate state-changing controls (T2/T3)
        clean_args = dict(arguments)
        confirmation_token = clean_args.pop("confirmation_token", None)
        idempotency_key = clean_args.pop("idempotency_key", None)

        if not tool.annotations.readOnlyHint or tool.tier in (RiskTier.T2, RiskTier.T3):
            if not confirmation_token or not idempotency_key:
                raise SSRAError(
                    McpErrorCode.NOT_AUTHORIZED,
                    f"State-changing tool '{tool_name}' ({tool.tier}) requires confirmation_token and idempotency_key",
                    status_code=403,
                )
            cache_key = f"{self.server_name}:{tool_name}:{claims.sub or 'anon'}:{idempotency_key}"
            if cache_key in self._idempotent_cache:
                return self._idempotent_cache[cache_key]

            self.confirmation_manager.consume_token(
                token=str(confirmation_token),
                tool_name=tool_name,
                arguments=clean_args,
                subject_ref=claims.sub,
                idempotency_key=str(idempotency_key),
            )
        else:
            cache_key = None

        # 3. Validate input arguments against JSON Schema 2020-12
        try:
            jsonschema.Draft202012Validator(tool.input_schema).validate(clean_args)
        except jsonschema.ValidationError as exc:
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                f"Input schema validation failed for '{tool_name}': {exc.message}",
                status_code=400,
            ) from exc

        # 4. Execute handler and sanitise output URLs / length caps (Section 8.3)
        ctx = ToolContext(
            server_name=self.server_name,
            tool_name=tool_name,
            tier=tool.tier,
            claims=claims,
            traceparent=traceparent,
        )
        from ssra_mcp.sanitiser import sanitise_structured_output

        raw_result = sanitise_structured_output(tool.handler(clean_args, ctx))

        # 5. Validate output against JSON Schema 2020-12
        try:
            jsonschema.Draft202012Validator(tool.output_schema).validate(raw_result)
        except jsonschema.ValidationError as exc:
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                f"Output schema validation failed for '{tool_name}': {exc.message}",
                status_code=500,
            ) from exc

        now = utc_now()
        provenance = ProvenanceEnvelope(
            system=tool.upstream_system,
            record_id=str(raw_result.get("record_id", f"{self.server_name}:{tool_name}")),
            retrieved_at=now,
            as_of=str(raw_result.get("as_of", now.date().isoformat())),
        )
        response_envelope = {
            "_meta": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "server": self.server_name,
                "tool": tool_name,
                "tier": tool.tier.value,
                "traceparent": traceparent,
            },
            "structuredContent": raw_result,
            "provenance": provenance.model_dump(mode="json"),
            "data_classification": tool.data_classification,
        }

        self.audit_ledger.append(
            actor=claims.caller_workload,
            on_behalf_of=claims.sub,
            action=f"mcp.{self.server_name}.{tool_name}",
            resource=f"mcp://{self.server_name}/{tool_name}",
            payload={
                "args": clean_args,
                "record_id": provenance.record_id,
                "tier": tool.tier.value,
            },
        )

        if cache_key is not None:
            self._idempotent_cache[cache_key] = response_envelope

        return response_envelope

    def create_fastapi_app(self) -> FastAPI:
        app = FastAPI(
            title=f"SSRA MCP Server — {self.server_name}",
            version="0.1.0",
        )

        @app.get("/healthz")
        async def healthz() -> dict[str, str]:
            return {
                "status": "ok",
                "server": self.server_name,
                "protocol": MCP_PROTOCOL_VERSION,
            }

        @app.post("/mcp")
        async def mcp_endpoint(
            request: Request,
            mcp_method: str | None = Header(default=None, alias="Mcp-Method"),
            mcp_name: str | None = Header(default=None, alias="Mcp-Name"),
            authorization: str | None = Header(default=None, alias="Authorization"),
            traceparent: str | None = Header(default=None, alias="traceparent"),
        ) -> JSONResponse:
            try:
                body = await request.json()
                req = StatelessMcpRequest.model_validate(body)
                if req.meta.protocolVersion != MCP_PROTOCOL_VERSION:
                    raise SSRAError(
                        McpErrorCode.VALIDATION_FAILED,
                        f"Unsupported MCP protocolVersion '{req.meta.protocolVersion}'; expected '{MCP_PROTOCOL_VERSION}'",
                        status_code=400,
                    )
                if mcp_method and mcp_method != req.method:
                    raise SSRAError(
                        McpErrorCode.VALIDATION_FAILED,
                        "Mcp-Method header does not match body method",
                        status_code=400,
                    )
                if mcp_name and mcp_name != self.server_name:
                    raise SSRAError(
                        McpErrorCode.VALIDATION_FAILED,
                        f"Mcp-Name header '{mcp_name}' does not match server '{self.server_name}'",
                        status_code=400,
                    )

                if any(req.method.startswith(p) for p in _DEPRECATED_METHOD_PREFIXES):
                    raise SSRAError(
                        McpErrorCode.VALIDATION_FAILED,
                        f"Deprecated MCP feature '{req.method}' (Roots/Sampling/Logging) is prohibited by SSRA MCP 2026-07-28 baseline",
                        status_code=400,
                    )
                if req.method not in _ALLOWED_MCP_METHODS:
                    raise SSRAError(
                        McpErrorCode.VALIDATION_FAILED,
                        f"Unsupported MCP method '{req.method}'",
                        status_code=400,
                    )

                if req.method == "tools/list":
                    return JSONResponse(content=self.handle_list_tools(), status_code=200)

                if req.method.startswith("tasks/"):
                    return JSONResponse(
                        content=self.handle_task_method(req.method, req.params),
                        status_code=200,
                    )

                tool_name = str(req.params.get("name", ""))
                arguments = dict(req.params.get("arguments", {}))
                result = self.handle_call_tool(
                    tool_name=tool_name,
                    arguments=arguments,
                    bearer_token=authorization,
                    traceparent=traceparent,
                )
                return JSONResponse(content=result, status_code=200)
            except SSRAError as err:
                return JSONResponse(
                    content={
                        "error": {
                            "code": err.code.value,
                            "message": err.message,
                        }
                    },
                    status_code=err.status_code,
                )

        return app
