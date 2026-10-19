"""Stateless MCP 2026-07-28 server for SSRA cases (create_case, get_case_status, add_case_note)."""

from __future__ import annotations

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


def create_cases_mcp_server() -> StatelessMcpServer:
    server = StatelessMcpServer(server_name="cases")
    case_store: dict[str, dict[str, Any]] = {
        "case_seed_001": {
            "case_id": "case_seed_001",
            "subject_ref": "sub_taxpayer_amina_01",
            "case_type": "INQUIRY",
            "status": "IN_PROGRESS",
            "notes_count": 1,
        }
    }

    def _create_case(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        sub = require_subject_ref(ctx)
        cid = new_id("case")
        case_store[cid] = {
            "case_id": cid,
            "subject_ref": sub,
            "case_type": str(args.get("case_type", "INQUIRY")),
            "status": "OPEN",
            "notes_count": 1,
        }
        return {
            "case_id": cid,
            "case_type": str(args.get("case_type", "INQUIRY")),
            "status": "OPEN",
            "record_id": cid,
            "as_of": juba_today().isoformat(),
        }

    def _get_case_status(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        sub = require_subject_ref(ctx)
        cid = str(args["case_id"])
        rec = case_store.get(cid)
        if rec is None or rec.get("subject_ref") != sub:
            raise SSRAError(
                McpErrorCode.NOT_FOUND,
                f"Case '{cid}' not found for authenticated subject",
                status_code=404,
            )
        return {
            "case_id": cid,
            "case_type": str(rec["case_type"]),
            "status": str(rec["status"]),
            "record_id": cid,
            "as_of": juba_today().isoformat(),
        }

    def _add_case_note(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        sub = require_subject_ref(ctx)
        cid = str(args["case_id"])
        rec = case_store.get(cid)
        if rec is None or rec.get("subject_ref") != sub:
            raise SSRAError(
                McpErrorCode.NOT_FOUND,
                f"Case '{cid}' not found for authenticated subject",
                status_code=404,
            )
        rec["notes_count"] = int(rec.get("notes_count", 1)) + 1
        return {
            "case_id": cid,
            "notes_count": int(rec["notes_count"]),
            "status": str(rec["status"]),
            "record_id": f"{cid}:note:{rec['notes_count']}",
            "as_of": juba_today().isoformat(),
        }

    case_out_schema = {
        "$schema": JSON_SCHEMA_2020_12,
        "type": "object",
        "additionalProperties": False,
        "required": ["case_id", "case_type", "status", "record_id", "as_of"],
        "properties": {
            "case_id": {"type": "string"},
            "case_type": {"type": "string"},
            "status": {"type": "string"},
            "record_id": {"type": "string"},
            "as_of": {"type": "string"},
        },
    }

    server.register_tool(
        RegisteredTool(
            name="create_case",
            description="Create a taxpayer support or complaint case with SLA tracking.",
            tier=RiskTier.T2,
            annotations=ToolAnnotations(
                readOnlyHint=False, destructiveHint=False, idempotentHint=True
            ),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["case_type", "summary"],
                "properties": {
                    "case_type": {
                        "type": "string",
                        "enum": ["INQUIRY", "COMPLAINT", "SCAM_REPORT", "CALLBACK"],
                    },
                    "summary": {"type": "string", "minLength": 5, "maxLength": 1000},
                },
            },
            output_schema=case_out_schema,
            data_classification="CONFIDENTIAL_TAXPAYER",
            upstream_system="ssra-case-service",
            handler=_create_case,
        )
    )

    server.register_tool(
        RegisteredTool(
            name="get_case_status",
            description="Retrieve the status of a support case owned by the authenticated taxpayer.",
            tier=RiskTier.T1,
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["case_id"],
                "properties": {"case_id": {"type": "string", "minLength": 3}},
            },
            output_schema=case_out_schema,
            data_classification="CONFIDENTIAL_TAXPAYER",
            upstream_system="ssra-case-service",
            handler=_get_case_status,
        )
    )

    server.register_tool(
        RegisteredTool(
            name="add_case_note",
            description="Append a note to an existing taxpayer case owned by the authenticated subject.",
            tier=RiskTier.T2,
            annotations=ToolAnnotations(
                readOnlyHint=False, destructiveHint=False, idempotentHint=True
            ),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["case_id", "note"],
                "properties": {
                    "case_id": {"type": "string", "minLength": 3},
                    "note": {"type": "string", "minLength": 3, "maxLength": 1000},
                },
            },
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["case_id", "notes_count", "status", "record_id", "as_of"],
                "properties": {
                    "case_id": {"type": "string"},
                    "notes_count": {"type": "integer"},
                    "status": {"type": "string"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="CONFIDENTIAL_TAXPAYER",
            upstream_system="ssra-case-service",
            handler=_add_case_note,
        )
    )
    return server


mcp_server = create_cases_mcp_server()
app = mcp_server.create_fastapi_app()
