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

MAX_APPOINTMENTS = 1024
_ALLOWED_OFFICE_CODES: frozenset[str] = frozenset(
    {"JUBA_HQ", "NIMULE_CUSTOMS", "WAU_BRANCH", "MALAKAL_BRANCH"}
)


def create_appointments_mcp_server() -> StatelessMcpServer:
    """Create the stateless MCP 2026-07-28 server for SSRA appointments with bounded state and ownership guards."""
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
        """List available Africa/Juba appointment slots for an approved SSRA office."""
        office = str(args.get("office_code", "JUBA_HQ")).strip().upper()
        if office not in _ALLOWED_OFFICE_CODES:
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                f"Unknown SSRA office_code '{office}'",
                status_code=400,
            )
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
        """Book a confirmed in-person appointment bound to the authenticated taxpayer's subject_ref."""
        sub = require_subject_ref(ctx)
        office = str(args["office_code"]).strip().upper()
        if office not in _ALLOWED_OFFICE_CODES:
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                f"Unknown SSRA office_code '{office}'",
                status_code=400,
            )
        slot = str(args["slot_id"]).strip()
        if len(appointment_store) >= MAX_APPOINTMENTS:
            appointment_store.pop(next(k for k in appointment_store if k != "appt_seed_01"), None)
        appt_id = new_id("appt")
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
        """Cancel an appointment after verifying the caller owns the appointment_id state handle."""
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
