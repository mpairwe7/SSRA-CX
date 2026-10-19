"""Subject-bound Tier T1 tools for ssra_mcp_ledger (Section 8.4 & 16).

Security Invariant (Section 12.3): Notice that input_schema does NOT accept a `tin` or `subject_ref`
argument from the LLM. Ownership is enforced strictly from `ctx.claims.sub` (OAuth 2.1 RFC 8693 token exchange).
"""

from __future__ import annotations

from typing import Any

from ssra_adapters import MockETaxAdapter
from ssra_core import RiskTier
from ssra_mcp import (
    JSON_SCHEMA_2020_12,
    RegisteredTool,
    ToolAnnotations,
    ToolContext,
    require_subject_ref,
)


def build_ledger_tools(adapter: MockETaxAdapter) -> list[RegisteredTool]:
    def _get_balance(_args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        subject_ref = require_subject_ref(ctx)
        rec = adapter.get_ledger_balance(subject_ref=subject_ref)
        return {
            "tin_masked": rec.tin_masked,
            "total_outstanding_ssp": rec.total_outstanding_ssp,
            "currency": rec.currency,
            "filing_status": rec.filing_status,
            "official_payment_channel": "https://etax.nra.gov.ss/ (Bank remittance to TSA only)",
            "record_id": f"etax:balance:{subject_ref}",
            "as_of": rec.as_of.date().isoformat(),
        }

    def _get_filing_status(_args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        subject_ref = require_subject_ref(ctx)
        rec = adapter.get_ledger_balance(subject_ref=subject_ref)
        return {
            "tin_masked": rec.tin_masked,
            "filing_status": rec.filing_status,
            "last_filed_period": rec.last_filed_period,
            "record_id": f"etax:filing:{subject_ref}",
            "as_of": rec.as_of.date().isoformat(),
        }

    def _list_assessments(_args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        subject_ref = require_subject_ref(ctx)
        rec = adapter.get_ledger_balance(subject_ref=subject_ref)
        return {
            "tin_masked": rec.tin_masked,
            "assessments": [
                {
                    "period": rec.last_filed_period,
                    "outstanding_ssp": rec.total_outstanding_ssp,
                    "currency": "SSP",
                }
            ],
            "record_id": f"etax:assessments:{subject_ref}",
            "as_of": rec.as_of.date().isoformat(),
        }

    def _list_payments(_args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        subject_ref = require_subject_ref(ctx)
        rec = adapter.get_ledger_balance(subject_ref=subject_ref)
        return {
            "tin_masked": rec.tin_masked,
            "payments": [
                {
                    "period": rec.last_filed_period,
                    "channel": "TSA Commercial Bank via e-Tax",
                    "status": "POSTED",
                }
            ],
            "record_id": f"etax:payments:{subject_ref}",
            "as_of": rec.as_of.date().isoformat(),
        }

    empty_subject_bound_input = {
        "$schema": JSON_SCHEMA_2020_12,
        "type": "object",
        "additionalProperties": False,
        "properties": {},
    }

    return [
        RegisteredTool(
            name="get_balance",
            description="Retrieve the authenticated taxpayer's masked e-Tax balance in SSP (subject-bound via RFC 8693 token).",
            tier=RiskTier.T1,
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            input_schema=empty_subject_bound_input,
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "tin_masked",
                    "total_outstanding_ssp",
                    "currency",
                    "filing_status",
                    "official_payment_channel",
                    "record_id",
                    "as_of",
                ],
                "properties": {
                    "tin_masked": {"type": "string"},
                    "total_outstanding_ssp": {"type": "string"},
                    "currency": {"type": "string", "const": "SSP"},
                    "filing_status": {"type": "string"},
                    "official_payment_channel": {"type": "string"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="CONFIDENTIAL_TAXPAYER",
            upstream_system="ssra-etax-adapter",
            handler=_get_balance,
        ),
        RegisteredTool(
            name="get_filing_status",
            description="Retrieve the authenticated taxpayer's e-Tax return filing status.",
            tier=RiskTier.T1,
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            input_schema=empty_subject_bound_input,
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "tin_masked",
                    "filing_status",
                    "last_filed_period",
                    "record_id",
                    "as_of",
                ],
                "properties": {
                    "tin_masked": {"type": "string"},
                    "filing_status": {"type": "string"},
                    "last_filed_period": {"type": "string"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="CONFIDENTIAL_TAXPAYER",
            upstream_system="ssra-etax-adapter",
            handler=_get_filing_status,
        ),
        RegisteredTool(
            name="list_assessments",
            description="List the authenticated taxpayer's e-Tax assessments.",
            tier=RiskTier.T1,
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            input_schema=empty_subject_bound_input,
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["tin_masked", "assessments", "record_id", "as_of"],
                "properties": {
                    "tin_masked": {"type": "string"},
                    "assessments": {"type": "array"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="CONFIDENTIAL_TAXPAYER",
            upstream_system="ssra-etax-adapter",
            handler=_list_assessments,
        ),
        RegisteredTool(
            name="list_payments",
            description="List the authenticated taxpayer's posted e-Tax bank payments.",
            tier=RiskTier.T1,
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            input_schema=empty_subject_bound_input,
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["tin_masked", "payments", "record_id", "as_of"],
                "properties": {
                    "tin_masked": {"type": "string"},
                    "payments": {"type": "array"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="CONFIDENTIAL_TAXPAYER",
            upstream_system="ssra-etax-adapter",
            handler=_list_payments,
        ),
    ]
