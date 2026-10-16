"""Stateless MCP 2026-07-28 server for SSRA notifications (Tier T2, consent-checked)."""

from __future__ import annotations

from typing import Any

from ssra_core import McpErrorCode, RiskTier, SSRAError, new_id
from ssra_mcp import (
    JSON_SCHEMA_2020_12,
    RegisteredTool,
    StatelessMcpServer,
    ToolAnnotations,
    ToolContext,
)


def create_notifications_mcp_server() -> StatelessMcpServer:
    server = StatelessMcpServer(server_name="notifications")

    def _send_template(args: dict[str, Any], _ctx: ToolContext) -> dict[str, Any]:
        if not args.get("consent_verified", False):
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "Hard Non-Goal: No outbound messages without verified opt-in consent",
                status_code=403,
            )
        msg_id = new_id("ntf")
        return {
            "notification_id": msg_id,
            "template_id": str(args["template_id"]),
            "status": "QUEUED_WITH_VERIFICATION_FOOTER",
            "record_id": msg_id,
            "as_of": "2026-10-16",
        }

    server.register_tool(
        RegisteredTool(
            name="send_template_message",
            description="Send a pre-approved, consent-verified SSRA notification template (staff or system only).",
            tier=RiskTier.T2,
            annotations=ToolAnnotations(
                readOnlyHint=False, destructiveHint=False, idempotentHint=True
            ),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["template_id", "consent_verified"],
                "properties": {
                    "template_id": {"type": "string", "minLength": 3},
                    "consent_verified": {"type": "boolean"},
                },
            },
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "notification_id",
                    "template_id",
                    "status",
                    "record_id",
                    "as_of",
                ],
                "properties": {
                    "notification_id": {"type": "string"},
                    "template_id": {"type": "string"},
                    "status": {"type": "string"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="CONFIDENTIAL_TAXPAYER",
            upstream_system="ssra-channel-gateway",
            handler=_send_template,
        )
    )
    return server


mcp_server = create_notifications_mcp_server()
app = mcp_server.create_fastapi_app()
