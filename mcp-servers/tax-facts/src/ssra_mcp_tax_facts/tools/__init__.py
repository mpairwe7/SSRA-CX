"""Tool schemas and handlers for ssra_mcp_tax_facts."""

from __future__ import annotations

from datetime import date
from typing import Any

from ssra_core import RiskTier
from ssra_mcp import JSON_SCHEMA_2020_12, RegisteredTool, ToolAnnotations, ToolContext
from ssra_rules import TaxFactsRegistry


def build_tax_facts_tools(registry: TaxFactsRegistry) -> list[RegisteredTool]:
    def _get_tax_fact(args: dict[str, Any], _ctx: ToolContext) -> dict[str, Any]:
        as_of_str = args.get("as_of")
        as_of_date = date.fromisoformat(str(as_of_str)) if as_of_str else date(2026, 10, 16)
        fact = registry.get_fact(str(args["key"]), as_of=as_of_date)
        return {
            "fact": fact.model_dump(mode="json"),
            "record_id": f"tax_fact:{fact.key}:{fact.version}",
            "as_of": fact.effective_from.isoformat(),
        }

    def _list_tax_facts(args: dict[str, Any], _ctx: ToolContext) -> dict[str, Any]:
        prefix = args.get("prefix")
        facts = registry.list_facts(
            prefix=str(prefix) if prefix else None,
            as_of=date(2026, 10, 16),
        )
        return {
            "snapshot_version": registry.snapshot_version,
            "facts": [f.model_dump(mode="json") for f in facts],
            "record_id": f"tax_facts:{registry.snapshot_version}",
            "as_of": "2026-10-16",
        }

    def _calculate_paye(args: dict[str, Any], _ctx: ToolContext) -> dict[str, Any]:
        res = registry.calculate_paye_estimate(
            str(args["gross_monthly_ssp"]),
            as_of=date(2026, 10, 16),
        )
        payload = res.model_dump(mode="json")
        payload["record_id"] = f"calc:paye:{res.gross_monthly_ssp}:{res.snapshot_version}"
        return payload

    def _calculate_withholding(args: dict[str, Any], _ctx: ToolContext) -> dict[str, Any]:
        category = str(args.get("category", "goods_and_services"))
        res = registry.calculate_withholding_estimate(
            str(args["gross_amount_ssp"]),
            category=category,  # type: ignore[arg-type]
            as_of=date(2026, 10, 16),
        )
        payload = res.model_dump(mode="json")
        payload["record_id"] = f"calc:wht:{category}:{res.gross_amount_ssp}:{res.snapshot_version}"
        return payload

    return [
        RegisteredTool(
            name="get_tax_fact",
            description="Retrieve an exact versioned SSRA TaxFact (rate, threshold, deadline, or fee) with its statutory citation.",
            tier=RiskTier.T0,
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["key"],
                "properties": {
                    "key": {"type": "string", "minLength": 2},
                    "as_of": {"type": "string", "format": "date"},
                },
            },
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["fact", "record_id", "as_of"],
                "properties": {
                    "fact": {"type": "object"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="PUBLIC",
            upstream_system="ssra-rules-engine",
            handler=_get_tax_fact,
        ),
        RegisteredTool(
            name="list_tax_facts",
            description="List active SSRA TaxFact records filtered by optional key prefix.",
            tier=RiskTier.T0,
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "prefix": {"type": "string"},
                },
            },
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["snapshot_version", "facts", "record_id", "as_of"],
                "properties": {
                    "snapshot_version": {"type": "string"},
                    "facts": {"type": "array"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="PUBLIC",
            upstream_system="ssra-rules-engine",
            handler=_list_tax_facts,
        ),
        RegisteredTool(
            name="calculate_paye_estimate",
            description="Deterministically calculate a monthly Personal Income Tax (PAYE) estimate in SSP from published Tax Facts.",
            tier=RiskTier.T0,
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["gross_monthly_ssp"],
                "properties": {
                    "gross_monthly_ssp": {
                        "type": ["string", "number"],
                        "description": "Gross monthly salary in SSP",
                    },
                },
            },
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": True,
                "required": [
                    "gross_monthly_ssp",
                    "estimated_tax_ssp",
                    "net_monthly_ssp",
                    "effective_rate_percent",
                    "filing_deadline_day",
                    "is_estimate",
                    "disclaimer",
                    "numeric_claims",
                    "record_id",
                    "as_of",
                ],
                "properties": {
                    "gross_monthly_ssp": {"type": "string"},
                    "estimated_tax_ssp": {"type": "string"},
                    "net_monthly_ssp": {"type": "string"},
                    "effective_rate_percent": {"type": "string"},
                    "filing_deadline_day": {"type": "integer"},
                    "is_estimate": {"type": "boolean", "const": True},
                    "disclaimer": {"type": "string"},
                    "numeric_claims": {"type": "array"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="PUBLIC",
            upstream_system="ssra-rules-engine",
            handler=_calculate_paye,
        ),
        RegisteredTool(
            name="calculate_withholding_estimate",
            description="Deterministically calculate a Withholding Tax (WHT) estimate in SSP from published Tax Facts.",
            tier=RiskTier.T0,
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["gross_amount_ssp"],
                "properties": {
                    "gross_amount_ssp": {"type": ["string", "number"]},
                    "category": {
                        "type": "string",
                        "enum": ["goods_and_services", "rent", "technical_fees"],
                    },
                },
            },
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": True,
                "required": [
                    "category",
                    "gross_amount_ssp",
                    "rate_percent",
                    "withholding_tax_ssp",
                    "net_payable_ssp",
                    "is_estimate",
                    "disclaimer",
                    "numeric_claims",
                    "record_id",
                    "as_of",
                ],
                "properties": {
                    "category": {"type": "string"},
                    "gross_amount_ssp": {"type": "string"},
                    "rate_percent": {"type": "string"},
                    "withholding_tax_ssp": {"type": "string"},
                    "net_payable_ssp": {"type": "string"},
                    "is_estimate": {"type": "boolean", "const": True},
                    "disclaimer": {"type": "string"},
                    "numeric_claims": {"type": "array"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="PUBLIC",
            upstream_system="ssra-rules-engine",
            handler=_calculate_withholding,
        ),
    ]
