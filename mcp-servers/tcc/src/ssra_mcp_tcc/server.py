"""Stateless MCP 2026-07-28 server for SSRA tcc (get_tcc_status T1 & request_tcc T3)."""

from __future__ import annotations

import os
from typing import Any

from ssra_adapters import MockETaxAdapter
from ssra_core import McpErrorCode, RiskTier, SSRAError, juba_today, new_id
from ssra_mcp import (
    JSON_SCHEMA_2020_12,
    RegisteredTool,
    StatelessMcpServer,
    ToolAnnotations,
    ToolContext,
    require_subject_ref,
)


def create_tcc_mcp_server(*, enable_t3_request_tcc: bool | None = None) -> StatelessMcpServer:
    t3_enabled = (
        enable_t3_request_tcc
        if enable_t3_request_tcc is not None
        else os.getenv("SSRA_ENABLE_UPSTREAM_T3_TCC") == "1"
    )
    adapter = MockETaxAdapter()
    server = StatelessMcpServer(server_name="tcc")

    def _get_tcc_status(_args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        sub = require_subject_ref(ctx)
        rec = adapter.get_ledger_balance(subject_ref=sub)
        return {
            "tin_masked": rec.tin_masked,
            "tcc_status": rec.tcc_status,
            "tcc_expiry_date": rec.tcc_expiry_date,
            "portal_url": "https://etax.nra.gov.ss/",
            "record_id": f"etax:tcc:{sub}",
            "as_of": rec.as_of.date().isoformat(),
        }

    def _request_tcc(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        if not t3_enabled:
            raise SSRAError(
                McpErrorCode.UPSTREAM_UNAVAILABLE,
                "request_tcc is disabled until SSRA confirms upstream e-Tax API capability (OQ-001)",
                status_code=503,
            )
        sub = require_subject_ref(ctx)
        rec = adapter.get_ledger_balance(subject_ref=sub)
        app_id = new_id("tcc_req")
        return {
            "application_id": app_id,
            "tin_masked": rec.tin_masked,
            "purpose": str(args["purpose"]),
            "status": "SUBMITTED_ON_ETAX",
            "record_id": app_id,
            "as_of": juba_today().isoformat(),
        }

    server.register_tool(
        RegisteredTool(
            name="get_tcc_status",
            description="Retrieve the authenticated taxpayer's Tax Compliance Certificate (TCC) status from e-Tax.",
            tier=RiskTier.T1,
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            },
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "tin_masked",
                    "tcc_status",
                    "tcc_expiry_date",
                    "portal_url",
                    "record_id",
                    "as_of",
                ],
                "properties": {
                    "tin_masked": {"type": "string"},
                    "tcc_status": {"type": "string"},
                    "tcc_expiry_date": {"type": ["string", "null"]},
                    "portal_url": {"type": "string"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="CONFIDENTIAL_TAXPAYER",
            upstream_system="ssra-etax-adapter",
            handler=_get_tcc_status,
        )
    )

    server.register_tool(
        RegisteredTool(
            name="request_tcc",
            description="Submit an electronic Tax Compliance Certificate (TCC) application on e-Tax (Tier T3, step-up & confirmation required).",
            tier=RiskTier.T3,
            annotations=ToolAnnotations(
                readOnlyHint=False, destructiveHint=False, idempotentHint=True
            ),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["purpose"],
                "properties": {
                    "purpose": {
                        "type": "string",
                        "enum": ["TENDER", "CUSTOMS_CLEARANCE", "LICENSE_RENEWAL", "GENERAL"],
                    }
                },
            },
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "application_id",
                    "tin_masked",
                    "purpose",
                    "status",
                    "record_id",
                    "as_of",
                ],
                "properties": {
                    "application_id": {"type": "string"},
                    "tin_masked": {"type": "string"},
                    "purpose": {"type": "string"},
                    "status": {"type": "string"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="CONFIDENTIAL_TAXPAYER",
            upstream_system="ssra-etax-adapter",
            handler=_request_tcc,
        )
    )
    return server


mcp_server = create_tcc_mcp_server()
app = mcp_server.create_fastapi_app()
