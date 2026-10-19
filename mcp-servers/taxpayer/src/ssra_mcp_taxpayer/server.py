"""Stateless MCP 2026-07-28 server for SSRA taxpayer (Tier T1)."""

from __future__ import annotations

from typing import Any

from ssra_adapters import MockETaxAdapter
from ssra_core import RiskTier
from ssra_mcp import (
    JSON_SCHEMA_2020_12,
    RegisteredTool,
    StatelessMcpServer,
    ToolAnnotations,
    ToolContext,
    require_subject_ref,
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
        "additionalProperties": False,
        "required": ["tin_masked", "registration_status", "record_id", "as_of"],
        "properties": {
            "tin_masked": {"type": "string"},
            "taxpayer_type": {"type": "string"},
            "display_name_masked": {"type": "string"},
            "registration_status": {"type": "string"},
            "tax_office": {"type": "string"},
            "tin_verified": {"type": "boolean"},
            "active_tax_types": {"type": "array", "items": {"type": "string"}},
            "record_id": {"type": "string"},
            "as_of": {"type": "string"},
        },
    }

    def _verify_tin_handler(_args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        sub = require_subject_ref(ctx)
        prof = adapter.get_profile_masked(subject_ref=sub)
        return {
            "tin_masked": prof.tin_masked,
            "taxpayer_type": prof.taxpayer_type,
            "display_name_masked": prof.display_name_masked,
            "registration_status": prof.registration_status,
            "tax_office": prof.tax_office,
            "tin_verified": prof.registration_status == "ACTIVE",
            "record_id": f"etax:verify_tin:{sub}",
            "as_of": prof.as_of.date().isoformat(),
        }

    def _registration_status_handler(_args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        sub = require_subject_ref(ctx)
        prof = adapter.get_profile_masked(subject_ref=sub)
        return {
            "tin_masked": prof.tin_masked,
            "taxpayer_type": prof.taxpayer_type,
            "display_name_masked": prof.display_name_masked,
            "registration_status": prof.registration_status,
            "tax_office": prof.tax_office,
            "active_tax_types": ["PAYE", "BPT", "WHT"],
            "record_id": f"etax:registration:{sub}",
            "as_of": prof.as_of.date().isoformat(),
        }

    def _profile_handler(_args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        sub = require_subject_ref(ctx)
        prof = adapter.get_profile_masked(subject_ref=sub)
        return {
            "tin_masked": prof.tin_masked,
            "taxpayer_type": prof.taxpayer_type,
            "display_name_masked": prof.display_name_masked,
            "registration_status": prof.registration_status,
            "tax_office": prof.tax_office,
            "record_id": f"etax:profile:{sub}",
            "as_of": prof.as_of.date().isoformat(),
        }

    for tool_name, desc, handler_fn in [
        (
            "verify_tin",
            "Verify the authenticated taxpayer's TIN binding status.",
            _verify_tin_handler,
        ),
        (
            "get_registration_status",
            "Retrieve the authenticated taxpayer's e-Tax registration status.",
            _registration_status_handler,
        ),
        (
            "get_profile_masked",
            "Retrieve the authenticated taxpayer's masked profile summary.",
            _profile_handler,
        ),
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
                handler=handler_fn,
            )
        )
    return server


mcp_server = create_taxpayer_mcp_server()
app = mcp_server.create_fastapi_app()
