"""Stateless MCP 2026-07-28 server for SSRA taxpayer (Tier T1)."""

from __future__ import annotations

from typing import Any

from ssra_adapters import MockETaxAdapter
from ssra_core import McpErrorCode, RiskTier, SSRAError
from ssra_mcp import (
    JSON_SCHEMA_2020_12,
    RegisteredTool,
    StatelessMcpServer,
    ToolAnnotations,
    ToolContext,
)


def create_taxpayer_mcp_server() -> StatelessMcpServer:
    adapter = MockETaxAdapter()
    server = StatelessMcpServer(server_name="taxpayer")
    empty_in = {
        "$schema": JSON_SCHEMA_2020_12,
        "type": "object",
        "additionalProperties": False,
        "properties": {},
    }
    out_schema = {
        "$schema": JSON_SCHEMA_2020_12,
        "type": "object",
        "additionalProperties": True,
        "required": ["tin_masked", "registration_status", "record_id", "as_of"],
        "properties": {
            "tin_masked": {"type": "string"},
            "registration_status": {"type": "string"},
            "record_id": {"type": "string"},
            "as_of": {"type": "string"},
        },
    }

    def _profile_handler(_args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        if not ctx.claims.sub:
            raise SSRAError(McpErrorCode.NOT_AUTHORIZED, "Missing subject_ref", status_code=403)
        prof = adapter.get_profile_masked(subject_ref=ctx.claims.sub)
        return {
            "tin_masked": prof.tin_masked,
            "taxpayer_type": prof.taxpayer_type,
            "display_name_masked": prof.display_name_masked,
            "registration_status": prof.registration_status,
            "tax_office": prof.tax_office,
            "record_id": f"etax:profile:{ctx.claims.sub}",
            "as_of": prof.as_of.date().isoformat(),
        }

    for tool_name, desc in [
        ("verify_tin", "Verify the authenticated taxpayer's TIN binding status."),
        (
            "get_registration_status",
            "Retrieve the authenticated taxpayer's e-Tax registration status.",
        ),
        ("get_profile_masked", "Retrieve the authenticated taxpayer's masked profile summary."),
    ]:
        server.register_tool(
            RegisteredTool(
                name=tool_name,
                description=desc,
                tier=RiskTier.T1,
                annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
                input_schema=empty_in,
                output_schema=out_schema,
                data_classification="CONFIDENTIAL_TAXPAYER",
                upstream_system="ssra-etax-adapter",
                handler=_profile_handler,
            )
        )
    return server


mcp_server = create_taxpayer_mcp_server()
app = mcp_server.create_fastapi_app()
