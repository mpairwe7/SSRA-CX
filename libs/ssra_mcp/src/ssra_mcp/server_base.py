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
import ipaddress
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlparse

import jsonschema
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from ssra_core import (
    AuthLevel,
    McpErrorCode,
    RiskTier,
    SSRAError,
    build_mcp_span_attributes,
    ensure_w3c_traceparent,
    new_id,
    utc_now,
)
from ssra_security import (
    ConfirmationTokenManager,
    HashChainedAuditLedger,
    SubjectTokenClaims,
    TokenExchangeService,
    compute_action_digest,
    compute_least_privilege_mcp_scope,
    redact_pii,
)

MCP_PROTOCOL_VERSION = "2026-07-28"
JSON_SCHEMA_2020_12 = "https://json-schema.org/draft/2020-12/schema"
MAX_MCP_TASKS = 512
MAX_MCP_IDEMPOTENT_CACHE = 1024
MAX_MCP_REQUEST_BODY_BYTES = 262_144
MCP_TASK_TTL_SECONDS = 3600
_SHELL_METACHAR_RE = re.compile(r"[;|`$><\r\n\x00]")
_NUMERIC_HOST_RE = re.compile(r"^(?:0x[0-9a-f]+|0[0-7]+|\d+)$", flags=re.IGNORECASE)
_INTERNAL_MCP_HOST_RE = re.compile(r"^mcp-[a-z0-9-]+$")

_ALLOWED_MCP_HOSTS: frozenset[str] = frozenset(
    {
        "testserver",
        "localhost",
        "127.0.0.1",
        "mcp.ssra.gov.ss",
        "agentgateway",
    }
)
_ALLOWED_MCP_ORIGINS: frozenset[str] = frozenset(
    {
        "https://assist.ssra.gov.ss",
        "https://console.ssra.gov.ss",
        "http://localhost:3000",
        "http://localhost:3001",
    }
)


def _is_trusted_mcp_hostname(raw_host: str) -> bool:
    """Return True if raw_host is an allow-listed sovereign or internal MCP hostname."""
    clean_host = raw_host.strip().lower().split(":", 1)[0]
    return bool(clean_host) and (
        clean_host in _ALLOWED_MCP_HOSTS
        or bool(_INTERNAL_MCP_HOST_RE.match(clean_host))
        or clean_host.endswith(".ssra.gov.ss")
        or clean_host.endswith(".svc.cluster.local")
    )


def validate_mcp_transport_headers(
    host: str | None,
    origin: str | None,
    *,
    x_forwarded_host: str | None = None,
) -> None:
    """Block Streamable HTTP DNS rebinding, spoofed X-Forwarded-Host, and untrusted Origins (CVE-2026-81092, CVE-2026-81315, CVE-2026-11624)."""
    if host is not None and not _is_trusted_mcp_hostname(host):
        raise SSRAError(
            McpErrorCode.NOT_AUTHORIZED,
            f"MCP DNS rebinding blocked: untrusted Host header '{host}' (CVE-2026-81092)",
            status_code=403,
        )
    if x_forwarded_host is not None and not _is_trusted_mcp_hostname(x_forwarded_host):
        raise SSRAError(
            McpErrorCode.NOT_AUTHORIZED,
            f"MCP DNS rebinding blocked: untrusted X-Forwarded-Host header '{x_forwarded_host}' (CVE-2026-81315)",
            status_code=403,
        )
    if origin is not None:
        clean_origin = origin.strip()
        if clean_origin.lower() == "null" or clean_origin not in _ALLOWED_MCP_ORIGINS:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                f"MCP cross-origin request blocked: untrusted Origin '{origin}' (CVE-2026-11624)",
                status_code=403,
            )


def _contains_null_byte(val: Any) -> bool:
    """Return True if any dict key or string value contains a NUL byte (GHSA-q382-vc8q-7jhj)."""
    if isinstance(val, str):
        return "\x00" in val
    if isinstance(val, dict):
        return any(_contains_null_byte(k) or _contains_null_byte(v) for k, v in val.items())
    if isinstance(val, (list, tuple)):
        return any(_contains_null_byte(item) for item in val)
    return False


async def read_bounded_mcp_json_body(
    request: Request,
    *,
    max_bytes: int = MAX_MCP_REQUEST_BODY_BYTES,
) -> dict[str, Any]:
    """Stream and parse a bounded JSON-RPC / MCP request body while rejecting >256KB DoS (CVE-2026-67432) and NUL bytes (GHSA-q382-vc8q-7jhj)."""
    content_len_str = request.headers.get("content-length")
    if content_len_str and content_len_str.isdigit() and int(content_len_str) > max_bytes:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            f"MCP request body exceeds maximum allowed size of {max_bytes} bytes (CVE-2026-67432)",
            status_code=413,
        )
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > max_bytes:
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                f"MCP request body exceeds maximum allowed size of {max_bytes} bytes (CVE-2026-67432)",
                status_code=413,
            )
        chunks.append(chunk)
    raw = b"".join(chunks)
    request._body = raw  # pyright: ignore[reportPrivateUsage]
    if not raw:
        return {}
    if b"\x00" in raw:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "MCP JSON payload contains prohibited NUL byte (GHSA-q382-vc8q-7jhj)",
            status_code=400,
        )
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "Malformed JSON in MCP request body",
            status_code=400,
        ) from exc
    if not isinstance(parsed, dict) or _contains_null_byte(parsed):
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "MCP request body must be a JSON object without NUL characters (GHSA-q382-vc8q-7jhj)",
            status_code=400,
        )
    return parsed


def validate_mcp_oauth_url(url: str, *, allow_dev_loopback: bool = False) -> str:
    """Validate MCP OAuth 2.1 metadata/authorization URLs against SSRF and XSS/RCE (MCP 2026-07-28 Security Best Practices & RFC 9728 §7.7)."""
    cleaned = url.strip()
    if not cleaned or _SHELL_METACHAR_RE.search(cleaned):
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "MCP OAuth URL rejected: empty or contains shell metacharacters",
            status_code=400,
        )
    parsed = urlparse(cleaned)
    scheme = parsed.scheme.lower()
    if scheme not in ("https", "http"):
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            f"MCP OAuth URL rejected: dangerous or unsupported scheme '{scheme}'",
            status_code=400,
        )
    if parsed.username or parsed.password:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "MCP OAuth URL rejected: embedded credentials are prohibited",
            status_code=400,
        )
    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "MCP OAuth URL rejected: missing hostname",
            status_code=400,
        )
    if _NUMERIC_HOST_RE.match(host):
        raise SSRAError(
            McpErrorCode.NOT_AUTHORIZED,
            f"MCP OAuth SSRF blocked: obfuscated numeric IP host '{host}' (RFC 9728 §7.7)",
            status_code=403,
        )
    is_loopback_name = host in ("localhost", "127.0.0.1", "::1")
    try:
        ip_obj = ipaddress.ip_address(host)
        effective_ip = (
            ip_obj.ipv4_mapped
            if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped
            else ip_obj
        )
        if effective_ip.is_loopback:
            if not allow_dev_loopback:
                raise SSRAError(
                    McpErrorCode.NOT_AUTHORIZED,
                    f"MCP OAuth SSRF blocked: loopback IP '{host}' not permitted in production",
                    status_code=403,
                )
        elif (
            effective_ip.is_private
            or effective_ip.is_link_local
            or effective_ip.is_multicast
            or effective_ip.is_reserved
            or effective_ip.is_unspecified
        ):
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                f"MCP OAuth SSRF blocked: private/reserved/metadata IP '{host}' (RFC 9728 §7.7)",
                status_code=403,
            )
    except ValueError:
        if is_loopback_name and not allow_dev_loopback:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                f"MCP OAuth SSRF blocked: loopback host '{host}' not permitted in production",
                status_code=403,
            ) from None

    if scheme == "http" and not (allow_dev_loopback and is_loopback_name):
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "MCP OAuth 2.1 requires https:// for all non-loopback URLs (OAuth 2.1 §1.5)",
            status_code=400,
        )
    return cleaned


def _redact_audit_value(val: Any) -> Any:
    """Recursively redact PII across string, dict, list, and tuple values."""
    if isinstance(val, str):
        return redact_pii(val).redacted_text
    if isinstance(val, dict):
        return {str(k): _redact_audit_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_redact_audit_value(item) for item in val]
    if isinstance(val, tuple):
        return tuple(_redact_audit_value(item) for item in val)
    return val


def redact_audit_args(args: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact PII from tool arguments before appending to the hash-chained audit ledger."""
    return {str(k): _redact_audit_value(v) for k, v in args.items()}


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


def require_subject_ref(ctx: ToolContext) -> str:
    """Return verified `ctx.claims.sub` for T1-T3 tools or raise NOT_AUTHORIZED (Section 8.2 & 12.3)."""
    if not ctx.claims.sub:
        raise SSRAError(
            McpErrorCode.NOT_AUTHORIZED,
            f"Verified subject_ref claim required for '{ctx.server_name}.{ctx.tool_name}'",
            status_code=403,
        )
    return ctx.claims.sub


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
        """Compute the immutable SHA-256 hex digest of the tool description."""
        return hashlib.sha256(self.description.encode("utf-8")).hexdigest()


class McpRequestMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    protocolVersion: str = MCP_PROTOCOL_VERSION
    clientCapabilities: dict[str, Any] = Field(default_factory=dict)

    @property
    def effective_protocol_version(self) -> str:
        """Resolve protocolVersion from either standard or SEP-2575 namespaced _meta field."""
        extra = self.model_extra or {}
        namespaced = extra.get("io.modelcontextprotocol/protocolVersion")
        if isinstance(namespaced, str) and namespaced.strip():
            return namespaced.strip()
        return self.protocolVersion


class StatelessMcpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str
    params: dict[str, Any] = Field(default_factory=dict)
    meta: McpRequestMeta = Field(default_factory=McpRequestMeta, alias="_meta")


_DEPRECATED_METHOD_PREFIXES: tuple[str, ...] = (
    "roots/",
    "sampling/",
    "logging/",
    "initialize",
    "notifications/initialized",
    "ping",
)
_ALLOWED_MCP_METHODS: frozenset[str] = frozenset(
    {
        "server/discover",
        "tools/list",
        "tools/call",
        "tasks/create",
        "tasks/get",
        "tasks/update",
        "tasks/cancel",
    }
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
        self._idempotent_cache: dict[str, tuple[str, dict[str, Any]]] = {}
        self._tasks: dict[str, dict[str, Any]] = {}

    @property
    def tools(self) -> dict[str, RegisteredTool]:
        """Return a shallow copy of registered tools on this MCP server."""
        return dict(self._tools)

    def register_tool(self, tool: RegisteredTool) -> None:
        """Register a tool after verifying Tier T0-T3 and JSON Schema 2020-12 invariants."""
        if tool.tier == RiskTier.T4:
            raise ValueError("Principle 3: T4 is human-only; no MCP tool may exist at Tier T4.")
        # Validate schemas are valid JSON Schema 2020-12 and forbid additionalProperties: True
        if tool.input_schema.get("$schema") != JSON_SCHEMA_2020_12:
            raise ValueError(f"Tool '{tool.name}' input_schema must declare $schema 2020-12")
        if tool.output_schema.get("$schema") != JSON_SCHEMA_2020_12:
            raise ValueError(f"Tool '{tool.name}' output_schema must declare $schema 2020-12")
        if tool.input_schema.get("additionalProperties") is True:
            raise ValueError(
                f"Tool '{tool.name}' input_schema must not set additionalProperties: True (Section 8.3)"
            )
        if tool.output_schema.get("additionalProperties") is True:
            raise ValueError(
                f"Tool '{tool.name}' output_schema must not set additionalProperties: True (Section 8.3)"
            )
        jsonschema.Draft202012Validator.check_schema(tool.input_schema)
        jsonschema.Draft202012Validator.check_schema(tool.output_schema)
        self._tools[tool.name] = tool

    def handle_server_discover(self) -> dict[str, Any]:
        """Return MCP 2026-07-28 server/discover capabilities, protocol versions, and server identity (SEP-2575)."""
        return {
            "resultType": "complete",
            "supportedProtocolVersions": [MCP_PROTOCOL_VERSION],
            "serverInfo": {
                "name": f"ssra-mcp-{self.server_name}",
                "version": "2026.10.1",
            },
            "capabilities": {
                "tools": {"listChanged": False},
                "extensions": {"io.modelcontextprotocol/tasks": {}},
            },
            "_meta": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL_VERSION,
                "server": self.server_name,
            },
        }

    def handle_list_tools(self) -> dict[str, Any]:
        """Return deterministic sorted tools/list CacheableResult with ttlMs and cacheScope (SEP-2549)."""
        sorted_tools = sorted(self._tools.values(), key=lambda item: item.name)
        return {
            "resultType": "complete",
            "ttlMs": self.ttl_ms,
            "cacheScope": "private",
            "_meta": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL_VERSION,
                "ttlMs": self.ttl_ms,
                "cacheScope": "private",
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
                for t in sorted_tools
            ],
        }

    def handle_task_method(
        self,
        method: str,
        params: dict[str, Any],
        *,
        caller_sub: str = "ANONYMOUS",
    ) -> dict[str, Any]:
        """MCP 2026-07-28 Tasks extension (SEP-2663) with State-Handle Hijacking & TTL protection."""
        now = utc_now()
        now_iso = now.isoformat()
        # Evict expired tasks proactively
        expired_ids = [
            tid for tid, trec in self._tasks.items() if str(trec.get("expiresAt", "9999")) < now_iso
        ]
        for tid in expired_ids:
            self._tasks.pop(tid, None)

        if method == "tasks/create":
            if len(self._tasks) >= MAX_MCP_TASKS:
                reclaimable = [
                    tid
                    for tid, trec in self._tasks.items()
                    if trec.get("status") not in ("RUNNING", "working")
                ]
                if not reclaimable:
                    raise SSRAError(
                        McpErrorCode.RATE_LIMITED,
                        f"Active MCP task capacity ({MAX_MCP_TASKS}) reached",
                        status_code=429,
                    )
                self._tasks.pop(reclaimable[0], None)
            task_id = new_id("task")
            task_rec: dict[str, Any] = {
                "taskId": task_id,
                "owner_sub": caller_sub,
                "status": "RUNNING",
                "taskStatus": "working",
                "operation": str(params.get("operation", "background_task")),
                "createdAt": now_iso,
                "lastUpdatedAt": now_iso,
                "ttlMs": MCP_TASK_TTL_SECONDS * 1000,
                "expiresAt": (now + timedelta(seconds=MCP_TASK_TTL_SECONDS)).isoformat(),
            }
            self._tasks[task_id] = task_rec
            return {
                "resultType": "complete",
                "_meta": {"protocolVersion": MCP_PROTOCOL_VERSION},
                "task": task_rec,
            }

        task_id = str(params.get("taskId", ""))
        rec = self._tasks.get(task_id)
        if rec is None:
            raise SSRAError(
                McpErrorCode.NOT_FOUND,
                f"Task '{task_id}' not found on server '{self.server_name}'",
                status_code=404,
            )
        if rec.get("owner_sub") != caller_sub:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "State-handle hijacking blocked: caller does not own taskId",
                status_code=403,
            )
        rec["lastUpdatedAt"] = now_iso
        if method == "tasks/update":
            if "inputResponses" in params:
                rec["inputResponses"] = params["inputResponses"]
            rec["status"] = "RUNNING"
            rec["taskStatus"] = "working"
        elif method == "tasks/cancel":
            rec["status"] = "CANCELLED"
            rec["taskStatus"] = "cancelled"
        return {
            "resultType": "complete",
            "_meta": {"protocolVersion": MCP_PROTOCOL_VERSION},
            "task": rec,
        }

    def handle_call_tool(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        bearer_token: str | None,
        traceparent: str | None = None,
    ) -> dict[str, Any]:
        """Execute a registered MCP tool with OAuth 2.1, confirmation token, JSON Schema 2020-12, and output sanitisation."""
        if _contains_null_byte(arguments):
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                f"Tool '{tool_name}' arguments contain prohibited NUL byte (GHSA-q382-vc8q-7jhj)",
                status_code=400,
            )
        tool = self._tools.get(tool_name)
        if tool is None:
            raise SSRAError(
                McpErrorCode.NOT_FOUND,
                f"Unknown tool '{tool_name}' on server '{self.server_name}'",
                status_code=404,
            )

        resolved_tp = ensure_w3c_traceparent(traceparent)

        # 1. Verify OAuth 2.1 / RFC 8693 token & RFC 8707 resource indicator
        expected_res = f"https://mcp.ssra.gov.ss/servers/{self.audience}"
        if bearer_token:
            raw_tok = bearer_token.removeprefix("Bearer ").strip()
            claims = self.token_service.verify_exchanged_token(
                raw_tok,
                expected_audience=self.audience,
                required_tier=tool.tier,
                expected_resource=expected_res,
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

        # 2. Extract and validate state-changing controls (T2/T3) with payload-bound idempotency
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
            action_digest = compute_action_digest(
                tool_name=tool_name,
                arguments=clean_args,
                subject_ref=claims.sub,
            )
            cache_key = f"{self.server_name}:{tool_name}:{claims.sub or 'anon'}:{idempotency_key}"
            if cache_key in self._idempotent_cache:
                cached_digest, cached_envelope = self._idempotent_cache[cache_key]
                if cached_digest != action_digest:
                    raise SSRAError(
                        McpErrorCode.VALIDATION_FAILED,
                        f"Idempotency key '{idempotency_key}' replayed with mutated arguments for '{tool_name}'",
                        status_code=422,
                    )
                return cached_envelope

            self.confirmation_manager.consume_token(
                token=str(confirmation_token),
                tool_name=tool_name,
                arguments=clean_args,
                subject_ref=claims.sub,
                idempotency_key=str(idempotency_key),
            )
        else:
            cache_key = None
            action_digest = ""

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
            traceparent=resolved_tp,
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
        otel_span = build_mcp_span_attributes(
            server_name=self.server_name,
            tool_name=tool_name,
            tier=tool.tier,
            data_classification=tool.data_classification,
            traceparent=resolved_tp,
        )
        response_envelope = {
            "resultType": "complete",
            "isError": False,
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(raw_result, ensure_ascii=False, sort_keys=True),
                }
            ],
            "_meta": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL_VERSION,
                "server": self.server_name,
                "tool": tool_name,
                "tier": tool.tier.value,
                "traceparent": resolved_tp,
                "otel": otel_span.to_otel_dict(),
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
                "args": redact_audit_args(clean_args),
                "record_id": provenance.record_id,
                "tier": tool.tier.value,
            },
        )

        if cache_key is not None:
            if len(self._idempotent_cache) >= MAX_MCP_IDEMPOTENT_CACHE:
                oldest_key = next(iter(self._idempotent_cache))
                self._idempotent_cache.pop(oldest_key, None)
            self._idempotent_cache[cache_key] = (action_digest, response_envelope)

        return response_envelope

    def get_protected_resource_metadata(self) -> dict[str, Any]:
        """RFC 9728 OAuth 2.0 Protected Resource Metadata with progressive Scope Minimization (MCP 2026-07-28)."""
        resource_uri = f"https://mcp.ssra.gov.ss/servers/{self.audience}"
        tiers_present = {t.tier for t in self._tools.values()}
        scopes = [f"mcp:{self.server_name}:read"]
        if RiskTier.T2 in tiers_present:
            scopes.append(f"mcp:{self.server_name}:write")
        if RiskTier.T3 in tiers_present:
            scopes.append(f"mcp:{self.server_name}:step_up")
        scopes.append(f"mcp:{self.server_name}:invoke")
        return {
            "resource": resource_uri,
            "authorization_servers": ["https://sso.ssra.gov.ss/realms/ssra"],
            "scopes_supported": scopes,
            "bearer_methods_supported": ["header"],
            "mcp_protocol_version": MCP_PROTOCOL_VERSION,
            "resource_documentation": f"{resource_uri}/docs",
        }

    def create_fastapi_app(self) -> FastAPI:
        """Create the FastAPI Streamable HTTP transport app for this StatelessMcpServer."""
        app = FastAPI(
            title=f"SSRA MCP Server — {self.server_name}",
            version="0.1.0",
        )

        @app.get("/healthz")
        async def healthz() -> dict[str, str]:
            """Return MCP server health status and protocol revision."""
            return {
                "status": "ok",
                "server": self.server_name,
                "protocol": MCP_PROTOCOL_VERSION,
            }

        @app.get(f"/.well-known/oauth-protected-resource/servers/{self.audience}")
        @app.get("/.well-known/oauth-protected-resource")
        async def oauth_protected_resource() -> dict[str, Any]:
            """Return RFC 9728 OAuth 2.0 Protected Resource Metadata for this MCP server."""
            return self.get_protected_resource_metadata()

        @app.post("/mcp")
        async def mcp_endpoint(
            request: Request,
            mcp_method: str | None = Header(default=None, alias="Mcp-Method"),
            mcp_name: str | None = Header(default=None, alias="Mcp-Name"),
            mcp_protocol_version: str | None = Header(default=None, alias="MCP-Protocol-Version"),
            mcp_session_id: str | None = Header(default=None, alias="Mcp-Session-Id"),
            authorization: str | None = Header(default=None, alias="Authorization"),
            traceparent: str | None = Header(default=None, alias="traceparent"),
        ) -> JSONResponse:
            """Handle stateless MCP 2026-07-28 Streamable HTTP POST requests."""
            try:
                validate_mcp_transport_headers(
                    request.headers.get("host"),
                    request.headers.get("origin"),
                    x_forwarded_host=request.headers.get("x-forwarded-host"),
                )
                if mcp_session_id is not None:
                    raise SSRAError(
                        McpErrorCode.VALIDATION_FAILED,
                        "Legacy Mcp-Session-Id header is prohibited by stateless MCP 2026-07-28 (SEP-2567)",
                        status_code=400,
                    )
                body = await read_bounded_mcp_json_body(request)
                req = StatelessMcpRequest.model_validate(body)
                effective_proto = req.meta.effective_protocol_version
                if effective_proto != MCP_PROTOCOL_VERSION:
                    raise SSRAError(
                        McpErrorCode.VALIDATION_FAILED,
                        f"Unsupported MCP protocolVersion '{effective_proto}'; expected '{MCP_PROTOCOL_VERSION}'",
                        status_code=400,
                    )
                if mcp_protocol_version and mcp_protocol_version.strip() != effective_proto:
                    raise SSRAError(
                        McpErrorCode.VALIDATION_FAILED,
                        "MCP-Protocol-Version header does not match _meta protocolVersion (HeaderMismatch -32020)",
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
                        f"Deprecated or removed MCP feature '{req.method}' is prohibited by SSRA MCP 2026-07-28 baseline",
                        status_code=400,
                    )
                if req.method not in _ALLOWED_MCP_METHODS:
                    raise SSRAError(
                        McpErrorCode.VALIDATION_FAILED,
                        f"Unsupported MCP method '{req.method}'",
                        status_code=400,
                    )

                if req.method == "server/discover":
                    return JSONResponse(content=self.handle_server_discover(), status_code=200)

                if req.method == "tools/list":
                    return JSONResponse(content=self.handle_list_tools(), status_code=200)

                if req.method.startswith("tasks/"):
                    caller_sub = "ANONYMOUS"
                    if authorization:
                        raw_tok = authorization.removeprefix("Bearer ").strip()
                        claims = self.token_service.verify_exchanged_token(
                            raw_tok,
                            expected_audience=self.audience,
                            required_tier=RiskTier.T0,
                            expected_resource=f"https://mcp.ssra.gov.ss/servers/{self.audience}",
                        )
                        caller_sub = claims.sub or "ANONYMOUS"
                    return JSONResponse(
                        content=self.handle_task_method(
                            req.method, req.params, caller_sub=caller_sub
                        ),
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
                err_headers: dict[str, str] = {}
                if err.status_code in (401, 403):
                    res_meta_url = f"https://mcp.ssra.gov.ss/.well-known/oauth-protected-resource/servers/{self.audience}"
                    target_tier = (
                        RiskTier.T3 if err.code == McpErrorCode.STEP_UP_REQUIRED else RiskTier.T1
                    )
                    req_scope = compute_least_privilege_mcp_scope(self.audience, target_tier)
                    oauth_err = (
                        "insufficient_scope"
                        if err.code == McpErrorCode.STEP_UP_REQUIRED
                        else err.code.value.lower()
                    )
                    err_headers["WWW-Authenticate"] = (
                        f'Bearer realm="{self.audience}", '
                        f'resource="https://mcp.ssra.gov.ss/servers/{self.audience}", '
                        f'resource_metadata="{res_meta_url}", '
                        f'scope="{req_scope}", '
                        f'error="{oauth_err}"'
                    )
                return JSONResponse(
                    content={
                        "error": {
                            "code": err.code.value,
                            "message": err.message,
                        }
                    },
                    status_code=err.status_code,
                    headers=err_headers,
                )

        return app
