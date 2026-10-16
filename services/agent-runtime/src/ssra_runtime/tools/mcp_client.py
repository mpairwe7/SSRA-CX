"""Governed MCP 2026-07-28 client routing all calls through agentgateway (Section 5, 6.1, 8).

Enforces:
- Stateless MCP 2026-07-28 headers (`Mcp-Method`, `Mcp-Name`, `traceparent`)
- RFC 8693 OAuth 2.1 subject token exchange for T1-T3 tools
- Tool description SHA-256 hash pinning to block description drift / rug-pull attacks
- Typed `ToolArtifact` storage
"""

from __future__ import annotations

import json
from typing import Any

from ssra_core import AuthLevel, McpErrorCode, RiskTier, SSRAError, new_id
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
from ssra_security import ConfirmationTokenManager, TokenExchangeService

from ssra_runtime.guardrails.injection import check_prompt_injection
from ssra_runtime.schemas import ToolArtifact, TurnBudget


class GovernedMcpGatewayClient:
    """Routes runtime tool calls through agentgateway policy, token exchange, and hash-pin checks."""

    def __init__(
        self,
        *,
        token_service: TokenExchangeService | None = None,
        confirmation_manager: ConfirmationTokenManager | None = None,
    ) -> None:
        self.token_service = token_service or TokenExchangeService()
        self.confirmation_manager = confirmation_manager or ConfirmationTokenManager()
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
        # Share the same token and confirmation manager across governed servers
        for srv in self._servers.values():
            srv.token_service = self.token_service
            srv.confirmation_manager = self.confirmation_manager

        # Pin tool description SHA-256 hashes & scan for MCP03:2025 tool poisoning and shadowing at startup (Section 8.3 & ASI02/ASI04)
        self._pinned_description_hashes: dict[str, str] = {}
        self.verify_no_cross_server_tool_shadowing()
        for srv_name, srv in self._servers.items():
            for tool_name, tool in srv.tools.items():
                self.scan_tool_metadata_for_poisoning(
                    srv_name, tool_name, tool.description, tool.input_schema
                )
                self._pinned_description_hashes[f"{srv_name}.{tool_name}"] = tool.description_sha256

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
    ) -> None:
        """Scan MCP tool descriptions and JSON schemas for embedded prompt injection (CSA July 2026 MCP03:2025)."""
        desc_scan = check_prompt_injection(description)
        schema_scan = check_prompt_injection(json.dumps(input_schema, sort_keys=True))
        if desc_scan.is_blocked or schema_scan.is_blocked:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                f"MCP03 tool metadata poisoning detected in '{srv_name}.{tool_name}'",
                status_code=403,
            )

    @property
    def servers(self) -> dict[str, StatelessMcpServer]:
        return dict(self._servers)

    @property
    def pinned_description_hashes(self) -> dict[str, str]:
        return dict(self._pinned_description_hashes)

    def override_pinned_hash_for_testing(self, tool_key: str, new_hash: str) -> None:
        self._pinned_description_hashes[tool_key] = new_hash

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

        # Verify tool description hash has not drifted (Section 8.3)
        expected_hash = self._pinned_description_hashes.get(f"{server_name}.{tool_name}")
        if expected_hash != tool.description_sha256:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                f"Tool description hash drift detected for '{server_name}.{tool_name}'",
                status_code=403,
            )

        # Perform OAuth 2.1 RFC 8693 token exchange at the gateway for T1-T3 tools
        bearer: str | None = None
        if tool.tier in (RiskTier.T1, RiskTier.T2, RiskTier.T3):
            exchanged = self.token_service.mint_exchanged_token(
                audience=srv.audience,
                auth_level=auth_level,
                subject_ref=subject_ref,
            )
            bearer = f"Bearer {exchanged}"

        envelope = srv.handle_call_tool(
            tool_name=tool_name,
            arguments=arguments,
            bearer_token=bearer,
            traceparent=traceparent,
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
