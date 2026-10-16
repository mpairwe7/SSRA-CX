"""Stateless MCP 2026-07-28 server for SSRA customs (get_declaration_status, lookup_tariff, estimate_duties — OQ-002)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from ssra_adapters import MockECustomsAdapter
from ssra_core import McpErrorCode, RiskTier, SSRAError
from ssra_mcp import (
    JSON_SCHEMA_2020_12,
    RegisteredTool,
    StatelessMcpServer,
    ToolAnnotations,
    ToolContext,
)


def create_customs_mcp_server() -> StatelessMcpServer:
    adapter = MockECustomsAdapter()
    server = StatelessMcpServer(server_name="customs")

    def _lookup_tariff(args: dict[str, Any], _ctx: ToolContext) -> dict[str, Any]:
        t = adapter.lookup_tariff(str(args["hs_code"]))
        return {
            "hs_code": t.hs_code,
            "description": t.description,
            "duty_rate_percent": t.duty_rate_percent,
            "excise_rate_percent": t.excise_rate_percent,
            "legal_ref": t.legal_ref,
            "boss_official_fx_rate_ssp_per_usd": t.boss_official_fx_rate_ssp_per_usd,
            "record_id": f"ecustoms:tariff:{t.hs_code}",
            "as_of": t.as_of.date().isoformat(),
        }

    def _estimate_duties(args: dict[str, Any], _ctx: ToolContext) -> dict[str, Any]:
        # Principle 2 & Section 2: Foreign-currency customs values convert to SSP strictly at the
        # official Bank of South Sudan (BoSS) rate from the adapter—never guessed by the LLM.
        t = adapter.lookup_tariff(str(args["hs_code"]))
        cif_usd = Decimal(str(args["cif_value_usd"]))
        if cif_usd < Decimal("0"):
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                "cif_value_usd must be non-negative",
                status_code=400,
            )
        fx = Decimal(t.boss_official_fx_rate_ssp_per_usd)
        cif_ssp = (cif_usd * fx).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        duty_rate = Decimal(t.duty_rate_percent)
        duty_ssp = (cif_ssp * duty_rate / Decimal("100")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        return {
            "hs_code": t.hs_code,
            "cif_value_usd": str(cif_usd),
            "boss_official_fx_rate_ssp_per_usd": str(fx),
            "customs_value_ssp": str(cif_ssp),
            "duty_rate_percent": str(duty_rate),
            "estimated_duty_ssp": str(duty_ssp),
            "is_estimate": True,
            "disclaimer": "ESTIMATE ONLY using official BoSS FX feed (OQ-002). Final assessment is issued by SSRA Customs.",
            "record_id": f"ecustoms:estimate:{t.hs_code}:{cif_usd}",
            "as_of": t.as_of.date().isoformat(),
        }

    def _get_declaration_status(_args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        if not ctx.claims.sub:
            raise SSRAError(McpErrorCode.NOT_AUTHORIZED, "Missing subject_ref", status_code=403)
        dec = adapter.get_declaration_status(subject_ref=ctx.claims.sub)
        return {
            "declaration_ref_masked": dec.declaration_ref_masked,
            "port_of_entry": dec.port_of_entry,
            "status": dec.status,
            "assessed_duty_ssp": dec.assessed_duty_ssp,
            "boss_official_fx_rate_used": dec.boss_official_fx_rate_used,
            "record_id": f"ecustoms:dec:{ctx.claims.sub}",
            "as_of": dec.as_of.date().isoformat(),
        }

    server.register_tool(
        RegisteredTool(
            name="lookup_tariff",
            description="Look up published SSRA customs tariff rates and official Bank of South Sudan FX rate by HS code.",
            tier=RiskTier.T0,
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["hs_code"],
                "properties": {"hs_code": {"type": "string", "minLength": 4}},
            },
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "hs_code",
                    "description",
                    "duty_rate_percent",
                    "excise_rate_percent",
                    "legal_ref",
                    "boss_official_fx_rate_ssp_per_usd",
                    "record_id",
                    "as_of",
                ],
                "properties": {
                    "hs_code": {"type": "string"},
                    "description": {"type": "string"},
                    "duty_rate_percent": {"type": "string"},
                    "excise_rate_percent": {"type": "string"},
                    "legal_ref": {"type": "string"},
                    "boss_official_fx_rate_ssp_per_usd": {"type": "string"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="PUBLIC",
            upstream_system="ssra-ecustoms-adapter",
            handler=_lookup_tariff,
        )
    )

    server.register_tool(
        RegisteredTool(
            name="estimate_duties",
            description="Deterministically estimate customs duties in SSP using the official Bank of South Sudan (BoSS) FX rate.",
            tier=RiskTier.T0,
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["hs_code", "cif_value_usd"],
                "properties": {
                    "hs_code": {"type": "string", "minLength": 4},
                    "cif_value_usd": {"type": ["string", "number"]},
                },
            },
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "hs_code",
                    "cif_value_usd",
                    "boss_official_fx_rate_ssp_per_usd",
                    "customs_value_ssp",
                    "duty_rate_percent",
                    "estimated_duty_ssp",
                    "is_estimate",
                    "disclaimer",
                    "record_id",
                    "as_of",
                ],
                "properties": {
                    "hs_code": {"type": "string"},
                    "cif_value_usd": {"type": "string"},
                    "boss_official_fx_rate_ssp_per_usd": {"type": "string"},
                    "customs_value_ssp": {"type": "string"},
                    "duty_rate_percent": {"type": "string"},
                    "estimated_duty_ssp": {"type": "string"},
                    "is_estimate": {"type": "boolean", "const": True},
                    "disclaimer": {"type": "string"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="PUBLIC",
            upstream_system="ssra-ecustoms-adapter",
            handler=_estimate_duties,
        )
    )

    server.register_tool(
        RegisteredTool(
            name="get_declaration_status",
            description="Retrieve the authenticated importer's customs declaration status (OQ-002 mock adapter).",
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
                    "declaration_ref_masked",
                    "port_of_entry",
                    "status",
                    "assessed_duty_ssp",
                    "boss_official_fx_rate_used",
                    "record_id",
                    "as_of",
                ],
                "properties": {
                    "declaration_ref_masked": {"type": "string"},
                    "port_of_entry": {"type": "string"},
                    "status": {"type": "string"},
                    "assessed_duty_ssp": {"type": "string"},
                    "boss_official_fx_rate_used": {"type": "string"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="CONFIDENTIAL_TAXPAYER",
            upstream_system="ssra-ecustoms-adapter",
            handler=_get_declaration_status,
        )
    )
    return server


mcp_server = create_customs_mcp_server()
app = mcp_server.create_fastapi_app()
