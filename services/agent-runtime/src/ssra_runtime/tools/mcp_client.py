"""Governed MCP 2026-07-28 client routing all calls through agentgateway (Section 5, 6.1, 8).

Enforces:
- Stateless MCP 2026-07-28 headers (`Mcp-Method`, `Mcp-Name`, `traceparent`)
- RFC 8693 OAuth 2.1 subject token exchange for T1-T3 tools
- Tool description SHA-256 hash pinning to block description drift / rug-pull attacks
- Typed `ToolArtifact` storage
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any

import yaml
from ssra_core import (
    AuthLevel,
    McpErrorCode,
    RiskTier,
    SSRAError,
    UpstreamCircuitBreaker,
    ensure_w3c_traceparent,
    execute_with_idempotent_retry,
    new_id,
)
from ssra_mcp import StatelessMcpServer
from ssra_mcp_appointments import create_appointments_mcp_server
from ssra_mcp_cases import create_cases_mcp_server
from ssra_mcp_customs import create_customs_mcp_server
from ssra_mcp_knowledge import create_knowledge_mcp_server
from ssra_mcp_ledger import create_ledger_mcp_server
from ssra_mcp_notifications import create_notifications_mcp_server
from ssra_mcp_official_channels import create_official_channels_mcp_server
from ssra_mcp_payments_info import create_payments_info_mcp_server
from ssra_mcp_tax_facts import create_tax_facts_mcp_server
from ssra_mcp_taxpayer import create_taxpayer_mcp_server
from ssra_mcp_tcc import create_tcc_mcp_server
from ssra_security import (
    ConfirmationTokenManager,
    TokenExchangeService,
    compute_least_privilege_mcp_scope,
)

from ssra_runtime.guardrails.injection import check_prompt_injection
from ssra_runtime.schemas import ToolArtifact, TurnBudget

_RISK_TIERS_FILE = Path(__file__).resolve().parents[5] / "ai" / "policies" / "risk-tiers.yaml"


@functools.lru_cache(maxsize=1)
def _load_canonical_tool_tiers() -> dict[str, str]:
    raw = yaml.safe_load(_RISK_TIERS_FILE.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in raw.get("tool_tiers", {}).items()}


class GovernedMcpGatewayClient:
    """Routes runtime tool calls through agentgateway policy, token exchange, circuit breakers, and hash-pin checks."""

    def __init__(
        self,
        *,
        token_service: TokenExchangeService | None = None,
        confirmation_manager: ConfirmationTokenManager | None = None,
        allow_open_world: bool = False,
        write_tools_enabled: bool = True,
    ) -> None:
        self.token_service = token_service or TokenExchangeService()
        self.confirmation_manager = confirmation_manager or ConfirmationTokenManager()
        self.allow_open_world = allow_open_world
        self.write_tools_enabled = write_tools_enabled
        self._disabled_tools: set[str] = set()
        self._canonical_tool_tiers = _load_canonical_tool_tiers()
        self._servers: dict[str, StatelessMcpServer] = {
            "knowledge": create_knowledge_mcp_server(),
            "tax-facts": create_tax_facts_mcp_server(),
            "official-channels": create_official_channels_mcp_server(),
            "taxpayer": create_taxpayer_mcp_server(),
            "ledger": create_ledger_mcp_server(),
            "payments-info": create_payments_info_mcp_server(),
            "tcc": create_tcc_mcp_server(),
            "customs": create_customs_mcp_server(),
            "cases": create_cases_mcp_server(),
            "appointments": create_appointments_mcp_server(),
            "notifications": create_notifications_mcp_server(),
        }
        self._circuit_breakers: dict[str, UpstreamCircuitBreaker] = {
            srv_name: UpstreamCircuitBreaker(
                upstream_name=f"mcp-{srv_name}",
                failure_threshold=3,
                recovery_timeout_seconds=30,
                max_half_open_probes=1,
            )
            for srv_name in self._servers
        }
        # Share the same token and confirmation manager across governed servers
        for srv in self._servers.values():
            srv.token_service = self.token_service
            srv.confirmation_manager = self.confirmation_manager

        # Pin tool description SHA-256 hashes & scan for MCP03:2025 tool poisoning, shadowing, and tier drift at startup
        self._pinned_description_hashes: dict[str, str] = {}
        self.verify_no_cross_server_tool_shadowing()
        for srv_name, srv in self._servers.items():
            for tool_name, tool in srv.tools.items():
                tool_key = f"{srv_name}.{tool_name}"
                self.scan_tool_metadata_for_poisoning(
                    srv_name,
                    tool_name,
                    tool.description,
                    tool.input_schema,
                    tool.output_schema,
                )
                if self._canonical_tool_tiers:
                    expected_tier = self._canonical_tool_tiers.get(tool_key)
                    if expected_tier != tool.tier.value:
                        raise SSRAError(
                            McpErrorCode.NOT_AUTHORIZED,
                            f"Tool tier drift detected for '{tool_key}': server declared '{tool.tier.value}', policy requires '{expected_tier}'",
                            status_code=403,
                        )
                self._pinned_description_hashes[tool_key] = tool.description_sha256

    def verify_no_cross_server_tool_shadowing(self) -> None:
        """Prevent duplicate tool names or cross-server tool shadowing across the 11 MCP servers (CVE-2026-30856 / MCP03)."""
        seen_tools: dict[str, str] = {}
        for srv_name, srv in self._servers.items():
            for tool_name in srv.tools:
                if tool_name in seen_tools:
                    raise SSRAError(
                        McpErrorCode.NOT_AUTHORIZED,
                        f"Cross-server tool name collision/shadowing detected: '{tool_name}' on both '{seen_tools[tool_name]}' and '{srv_name}' (CVE-2026-30856)",
                        status_code=403,
                    )
                seen_tools[tool_name] = srv_name

    @staticmethod
    def scan_tool_metadata_for_poisoning(
        srv_name: str,
        tool_name: str,
        description: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any] | None = None,
    ) -> None:
        """Scan MCP tool descriptions and JSON schemas for embedded prompt injection (CSA July 2026 MCP03:2025)."""
        desc_scan = check_prompt_injection(description)
        in_scan = check_prompt_injection(json.dumps(input_schema, sort_keys=True))
        out_scan = (
            check_prompt_injection(json.dumps(output_schema, sort_keys=True))
            if output_schema is not None
            else None
        )
        if desc_scan.is_blocked or in_scan.is_blocked or (out_scan and out_scan.is_blocked):
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                f"MCP03 tool metadata poisoning detected in '{srv_name}.{tool_name}'",
                status_code=403,
            )

    @property
    def servers(self) -> dict[str, StatelessMcpServer]:
        return dict(self._servers)

    @property
    def circuit_breakers(self) -> dict[str, UpstreamCircuitBreaker]:
        return dict(self._circuit_breakers)

    @property
    def pinned_description_hashes(self) -> dict[str, str]:
        return dict(self._pinned_description_hashes)

    def override_pinned_hash_for_testing(self, tool_key: str, new_hash: str) -> None:
        self._pinned_description_hashes[tool_key] = new_hash

    @property
    def disabled_tools(self) -> set[str]:
        """Return the set of tool keys currently disabled by gateway kill-switches."""
        return set(self._disabled_tools)

    def set_tool_kill_switch(self, tool_key: str, *, disabled: bool) -> None:
        """Runtime kill-switch for disabling a specific MCP tool (`server.tool`) at agentgateway."""
        if disabled:
            self._disabled_tools.add(tool_key)
        else:
            self._disabled_tools.discard(tool_key)

    def invoke_tool(
        self,
        *,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        auth_level: AuthLevel = AuthLevel.ANONYMOUS,
        subject_ref: str | None = None,
        traceparent: str | None = None,
        budget: TurnBudget | None = None,
    ) -> ToolArtifact:
        """Invoke an MCP tool through agentgateway policy, token exchange, and circuit-breaker guards."""
        if budget is not None:
            if budget.tool_calls_used >= budget.max_tool_calls:
                raise SSRAError(
                    McpErrorCode.RATE_LIMITED,
                    f"Turn tool-call budget ({budget.max_tool_calls}) exceeded (ASI08/ASI10 guard)",
                    status_code=429,
                )
            budget.tool_calls_used += 1
        srv = self._servers.get(server_name)
        if srv is None:
            raise SSRAError(
                McpErrorCode.NOT_FOUND,
                f"Unknown MCP server '{server_name}' at agentgateway",
                status_code=404,
            )
        tool = srv.tools.get(tool_name)
        if tool is None:
            raise SSRAError(
                McpErrorCode.NOT_FOUND,
                f"Unknown MCP tool '{server_name}.{tool_name}'",
                status_code=404,
            )

        tool_key = f"{server_name}.{tool_name}"
        if tool_key in self._disabled_tools:
            raise SSRAError(
                McpErrorCode.UPSTREAM_UNAVAILABLE,
                f"MCP tool '{tool_key}' is disabled by active gateway kill-switch",
                status_code=503,
            )

        # Verify tool description hash has not drifted (Section 8.3)
        expected_hash = self._pinned_description_hashes.get(tool_key)
        if expected_hash != tool.description_sha256:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                f"Tool description hash drift detected for '{tool_key}'",
                status_code=403,
            )

        # Enforce tool annotations at the gateway (Section 8.3)
        if tool.annotations.openWorldHint and not self.allow_open_world:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                f"Gateway blocked openWorldHint=True tool '{tool_key}' under sovereign egress policy",
                status_code=403,
            )
        is_state_changing = (
            not tool.annotations.readOnlyHint
            or tool.annotations.destructiveHint
            or tool.tier in (RiskTier.T2, RiskTier.T3)
        )
        if is_state_changing:
            if not self.write_tools_enabled:
                raise SSRAError(
                    McpErrorCode.UPSTREAM_UNAVAILABLE,
                    f"Write tool '{tool_key}' blocked: gateway write_tools kill-switch is active",
                    status_code=503,
                )
            if not arguments.get("confirmation_token") or not arguments.get("idempotency_key"):
                raise SSRAError(
                    McpErrorCode.NOT_AUTHORIZED,
                    f"Gateway annotation policy: state-changing tool '{tool_key}' requires confirmation_token and idempotency_key",
                    status_code=403,
                )

        # Perform OAuth 2.1 RFC 8693 token exchange with progressive least-privilege scope for T1-T3 tools
        bearer: str | None = None
        if tool.tier in (RiskTier.T1, RiskTier.T2, RiskTier.T3):
            least_priv_scope = compute_least_privilege_mcp_scope(srv.audience, tool.tier)
            exchanged = self.token_service.mint_exchanged_token(
                audience=srv.audience,
                auth_level=auth_level,
                subject_ref=subject_ref,
                scope=least_priv_scope,
            )
            bearer = f"Bearer {exchanged}"

        resolved_tp = ensure_w3c_traceparent(traceparent)
        cb = self._circuit_breakers[server_name]
        is_retryable_read = bool(tool.annotations.readOnlyHint and tool.annotations.idempotentHint)

        def _call_once() -> dict[str, Any]:
            """Execute a single governed MCP tool call under circuit-breaker protection."""
            is_probe = cb.acquire_call_permission()
            try:
                res = srv.handle_call_tool(
                    tool_name=tool_name,
                    arguments=arguments,
                    bearer_token=bearer,
                    traceparent=resolved_tp,
                )
                cb.record_success()
                return res
            except SSRAError as exc:
                if (
                    exc.code == McpErrorCode.UPSTREAM_UNAVAILABLE
                    and "disabled until SSRA confirms" not in exc.message
                ):
                    cb.record_failure()
                elif is_probe:
                    cb.release_half_open_probe()
                raise
            except Exception:
                cb.record_failure()
                raise

        envelope, _attempts = execute_with_idempotent_retry(
            _call_once,
            is_idempotent=is_retryable_read,
            max_attempts=2,
        )
        return ToolArtifact(
            id=new_id("art"),
            server=server_name,
            tool=tool_name,
            tier=tool.tier,
            structured_content=dict(envelope["structuredContent"]),
            provenance=dict(envelope["provenance"]),
            data_classification=str(envelope["data_classification"]),
        )
