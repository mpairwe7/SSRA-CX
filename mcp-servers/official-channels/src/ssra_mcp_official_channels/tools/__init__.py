"""Tools for ssra_mcp_official_channels (verify_payment_account, verify_sender, report_scam)."""

from __future__ import annotations

from typing import Any

from ssra_adapters import MockOfficialChannelsAdapter
from ssra_core import RiskTier, juba_today, new_id
from ssra_mcp import JSON_SCHEMA_2020_12, RegisteredTool, ToolAnnotations, ToolContext


def build_official_channels_tools(adapter: MockOfficialChannelsAdapter) -> list[RegisteredTool]:
    def _verify_payment_account(args: dict[str, Any], _ctx: ToolContext) -> dict[str, Any]:
        entry = adapter.verify_identifier(str(args["account_or_portal"]))
        return {
            "identifier": entry.identifier,
            "status": entry.status,
            "guidance": entry.guidance,
            "record_id": f"official_channel:{entry.identifier}",
            "as_of": juba_today().isoformat(),
        }

    def _verify_sender(args: dict[str, Any], _ctx: ToolContext) -> dict[str, Any]:
        entry = adapter.verify_identifier(str(args["sender_id_or_url"]))
        return {
            "identifier": entry.identifier,
            "status": entry.status,
            "guidance": entry.guidance,
            "record_id": f"official_sender:{entry.identifier}",
            "as_of": juba_today().isoformat(),
        }

    def _report_scam(args: dict[str, Any], _ctx: ToolContext) -> dict[str, Any]:
        report_id = new_id("scam")
        return {
            "report_id": report_id,
            "status": "RECEIVED_BY_SSRA_SECOPS",
            "suspected_identifier": str(args["suspected_identifier"]),
            "record_id": report_id,
            "as_of": juba_today().isoformat(),
        }

    return [
        RegisteredTool(
            name="verify_payment_account",
            description="Verify whether a payment portal or bank collection path is an official SSRA channel under the March 2026 cash-free directive.",
            tier=RiskTier.T0,
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["account_or_portal"],
                "properties": {
                    "account_or_portal": {"type": "string", "minLength": 2},
                },
            },
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["identifier", "status", "guidance", "record_id", "as_of"],
                "properties": {
                    "identifier": {"type": "string"},
                    "status": {"type": "string"},
                    "guidance": {"type": "string"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="PUBLIC",
            upstream_system="ssra-official-channels-registry",
            handler=_verify_payment_account,
        ),
        RegisteredTool(
            name="verify_sender",
            description="Verify whether an SMS sender ID, WhatsApp number, or website domain belongs to SSRA.",
            tier=RiskTier.T0,
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["sender_id_or_url"],
                "properties": {
                    "sender_id_or_url": {"type": "string", "minLength": 2},
                },
            },
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["identifier", "status", "guidance", "record_id", "as_of"],
                "properties": {
                    "identifier": {"type": "string"},
                    "status": {"type": "string"},
                    "guidance": {"type": "string"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="PUBLIC",
            upstream_system="ssra-official-channels-registry",
            handler=_verify_sender,
        ),
        RegisteredTool(
            name="report_scam",
            description="Submit an impersonation or fake tax collector scam report to SSRA Compliance & SecOps.",
            tier=RiskTier.T2,
            annotations=ToolAnnotations(
                readOnlyHint=False, destructiveHint=False, idempotentHint=True
            ),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["suspected_identifier", "summary"],
                "properties": {
                    "suspected_identifier": {"type": "string", "minLength": 2},
                    "summary": {"type": "string", "minLength": 5, "maxLength": 1000},
                },
            },
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "report_id",
                    "status",
                    "suspected_identifier",
                    "record_id",
                    "as_of",
                ],
                "properties": {
                    "report_id": {"type": "string"},
                    "status": {"type": "string"},
                    "suspected_identifier": {"type": "string"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="CONFIDENTIAL_TAXPAYER",
            upstream_system="ssra-case-service",
            handler=_report_scam,
        ),
    ]
