"""Stateless MCP 2026-07-28 server for SSRA appointments (list_slots, book_appointment, cancel_appointment)."""

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


def create_appointments_mcp_server() -> StatelessMcpServer:
    server = StatelessMcpServer(server_name="appointments")
    appointment_store: dict[str, dict[str, Any]] = {
        "appt_seed_01": {
            "appointment_id": "appt_seed_01",
            "subject_ref": "sub_taxpayer_amina_01",
            "office_code": "JUBA_HQ",
            "slot_id": "slot_2026_10_20_0900",
            "status": "CONFIRMED",
        }
    }

    def _list_slots(args: dict[str, Any], _ctx: ToolContext) -> dict[str, Any]:
        office = str(args.get("office_code", "JUBA_HQ"))
        return {
            "office_code": office,
            "slots": [
                {"slot_id": "slot_2026_10_20_0900", "start_eat": "2026-10-20T09:00:00+02:00"},
                {"slot_id": "slot_2026_10_20_1100", "start_eat": "2026-10-20T11:00:00+02:00"},
            ],
            "record_id": f"slots:{office}",
            "as_of": juba_today().isoformat(),
        }

    def _book_appointment(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        sub = require_subject_ref(ctx)
        appt_id = new_id("appt")
        office = str(args["office_code"])
        slot = str(args["slot_id"])
        appointment_store[appt_id] = {
            "appointment_id": appt_id,
            "subject_ref": sub,
            "office_code": office,
            "slot_id": slot,
            "status": "CONFIRMED",
        }
        return {
            "appointment_id": appt_id,
            "office_code": office,
            "slot_id": slot,
            "status": "CONFIRMED",
            "record_id": appt_id,
            "as_of": juba_today().isoformat(),
        }

    def _cancel_appointment(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        sub = require_subject_ref(ctx)
        appt_id = str(args["appointment_id"])
        rec = appointment_store.get(appt_id)
        if rec is None:
            raise SSRAError(
                McpErrorCode.NOT_FOUND,
                f"Appointment '{appt_id}' not found",
                status_code=404,
            )
        if rec.get("subject_ref") != sub:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                f"State-handle hijacking blocked: caller does not own appointment '{appt_id}'",
                status_code=403,
            )
        rec["status"] = "CANCELLED"
        return {
            "appointment_id": appt_id,
            "status": "CANCELLED",
            "record_id": appt_id,
            "as_of": juba_today().isoformat(),
        }

    server.register_tool(
        RegisteredTool(
            name="list_slots",
            description="List available appointment slots at an SSRA office in Africa/Juba time.",
            tier=RiskTier.T0,
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "properties": {"office_code": {"type": "string"}},
            },
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["office_code", "slots", "record_id", "as_of"],
                "properties": {
                    "office_code": {"type": "string"},
                    "slots": {"type": "array"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="PUBLIC",
            upstream_system="ssra-scheduling-service",
            handler=_list_slots,
        )
    )
    server.register_tool(
        RegisteredTool(
            name="book_appointment",
            description="Book a confirmed in-person appointment at an SSRA office (Tier T2).",
            tier=RiskTier.T2,
            annotations=ToolAnnotations(
                readOnlyHint=False, destructiveHint=False, idempotentHint=True
            ),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["office_code", "slot_id"],
                "properties": {
                    "office_code": {"type": "string", "minLength": 2},
                    "slot_id": {"type": "string", "minLength": 2},
                },
            },
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "appointment_id",
                    "office_code",
                    "slot_id",
                    "status",
                    "record_id",
                    "as_of",
                ],
                "properties": {
                    "appointment_id": {"type": "string"},
                    "office_code": {"type": "string"},
                    "slot_id": {"type": "string"},
                    "status": {"type": "string"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="CONFIDENTIAL_TAXPAYER",
            upstream_system="ssra-scheduling-service",
            handler=_book_appointment,
        )
    )
    server.register_tool(
        RegisteredTool(
            name="cancel_appointment",
            description="Cancel an existing SSRA office appointment owned by the authenticated taxpayer (Tier T2).",
            tier=RiskTier.T2,
            annotations=ToolAnnotations(
                readOnlyHint=False, destructiveHint=True, idempotentHint=True
            ),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["appointment_id"],
                "properties": {"appointment_id": {"type": "string", "minLength": 3}},
            },
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["appointment_id", "status", "record_id", "as_of"],
                "properties": {
                    "appointment_id": {"type": "string"},
                    "status": {"type": "string"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="CONFIDENTIAL_TAXPAYER",
            upstream_system="ssra-scheduling-service",
            handler=_cancel_appointment,
        )
    )
    return server


mcp_server = create_appointments_mcp_server()
app = mcp_server.create_fastapi_app()
