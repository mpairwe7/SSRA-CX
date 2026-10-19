"""Stateless MCP 2026-07-28 server for SSRA payments-info (T0 + feature-flagged T3 generate_payment_reference)."""

from __future__ import annotations

import os
from typing import Any

from ssra_core import McpErrorCode, RiskTier, SSRAError, juba_today, new_id
from ssra_mcp import (
    JSON_SCHEMA_2020_12,
    RegisteredTool,
    StatelessMcpServer,
    ToolAnnotations,
    ToolContext,
    require_subject_ref,
)


def create_payments_info_mcp_server(
    *, enable_t3_payment_ref: bool | None = None
) -> StatelessMcpServer:
    t3_enabled = (
        enable_t3_payment_ref
        if enable_t3_payment_ref is not None
        else os.getenv("SSRA_ENABLE_UPSTREAM_T3_PAYMENT_REF") == "1"
    )
    server = StatelessMcpServer(server_name="payments-info")
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
        "required": ["portal_url", "directive_ref", "instructions", "record_id", "as_of"],
        "properties": {
            "portal_url": {"type": "string"},
            "directive_ref": {"type": "string"},
            "instructions": {"type": "string"},
            "channels": {"type": "array", "items": {"type": "string"}},
            "record_id": {"type": "string"},
            "as_of": {"type": "string"},
        },
    }

    def _list_channels(_args: dict[str, Any], _ctx: ToolContext) -> dict[str, Any]:
        return {
            "portal_url": "https://etax.nra.gov.ss/",
            "directive_ref": "SSRA March 2026 Exclusive e-Tax & Cash-Free Bank Collection Directive",
            "instructions": (
                "Generate an official e-Tax payment assessment slip at https://etax.nra.gov.ss/ "
                "and remit via designated commercial banks into the Treasury Single Account (TSA)."
            ),
            "channels": [
                "National e-Tax Portal (https://etax.nra.gov.ss/) -> Designated Commercial Bank -> TSA"
            ],
            "record_id": "payments-info:channels:tsa-etax-2026",
            "as_of": juba_today().isoformat(),
        }

    def _instructions(_args: dict[str, Any], _ctx: ToolContext) -> dict[str, Any]:
        return {
            "portal_url": "https://etax.nra.gov.ss/",
            "directive_ref": "SSRA March 2026 Exclusive e-Tax & Cash-Free Bank Collection Directive",
            "instructions": (
                "Log in to https://etax.nra.gov.ss/, file your return to generate an official e-Tax "
                "payment assessment slip, and pay strictly into designated commercial banks remitting "
                "to the Treasury Single Account (TSA). Never pay cash to an individual collector."
            ),
            "record_id": "payments-info:tsa-etax-2026",
            "as_of": juba_today().isoformat(),
        }

    def _generate_payment_ref(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        if not t3_enabled:
            raise SSRAError(
                McpErrorCode.UPSTREAM_UNAVAILABLE,
                "generate_payment_reference is disabled until SSRA confirms upstream e-Tax capability (OQ-006)",
                status_code=503,
            )
        sub = require_subject_ref(ctx)
        ref_id = new_id("prn")
        return {
            "payment_reference": ref_id,
            "tax_type": str(args["tax_type"]),
            "amount_ssp": str(args["amount_ssp"]),
            "portal_url": "https://etax.nra.gov.ss/",
            "record_id": f"etax:prn:{sub}:{ref_id}",
            "as_of": juba_today().isoformat(),
        }

    for tool_name, desc, handler_fn in [
        (
            "list_payment_channels",
            "List official SSRA cash-free bank payment channels via the National e-Tax System.",
            _list_channels,
        ),
        (
            "get_payment_instructions",
            "Retrieve step-by-step instructions for paying taxes through e-Tax into designated banks.",
            _instructions,
        ),
    ]:
        server.register_tool(
            RegisteredTool(
                name=tool_name,
                description=desc,
                tier=RiskTier.T0,
                annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
                input_schema=empty_in,
                output_schema=out_schema,
                data_classification="PUBLIC",
                upstream_system="ssra-official-channels-registry",
                handler=handler_fn,
            )
        )

    server.register_tool(
        RegisteredTool(
            name="generate_payment_reference",
            description="Generate an official e-Tax bank payment reference slip (Tier T3, step-up & confirmation required, OQ-006).",
            tier=RiskTier.T3,
            annotations=ToolAnnotations(
                readOnlyHint=False, destructiveHint=False, idempotentHint=True
            ),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["tax_type", "amount_ssp"],
                "properties": {
                    "tax_type": {"type": "string", "enum": ["PAYE", "BPT", "WHT", "EXCISE"]},
                    "amount_ssp": {"type": "string", "minLength": 1},
                },
            },
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "payment_reference",
                    "tax_type",
                    "amount_ssp",
                    "portal_url",
                    "record_id",
                    "as_of",
                ],
                "properties": {
                    "payment_reference": {"type": "string"},
                    "tax_type": {"type": "string"},
                    "amount_ssp": {"type": "string"},
                    "portal_url": {"type": "string"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="CONFIDENTIAL_TAXPAYER",
            upstream_system="ssra-etax-adapter",
            handler=_generate_payment_ref,
        )
    )
    return server


mcp_server = create_payments_info_mcp_server()
app = mcp_server.create_fastapi_app()
