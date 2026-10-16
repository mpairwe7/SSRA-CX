"""Tool schemas and handlers for ssra_mcp_knowledge."""

from __future__ import annotations

from typing import Any

from ssra_core import RiskTier
from ssra_mcp import JSON_SCHEMA_2020_12, RegisteredTool, ToolAnnotations, ToolContext

from ssra_mcp_knowledge.adapters import KnowledgeCorpusAdapter


def build_knowledge_tools(adapter: KnowledgeCorpusAdapter) -> list[RegisteredTool]:
    def _search_knowledge(args: dict[str, Any], _ctx: ToolContext) -> dict[str, Any]:
        hits = adapter.search_knowledge(
            query=str(args["query"]),
            language=str(args.get("language", "en")),
            top_k=int(args.get("top_k", 3)),
        )
        return {
            "snapshot_version": adapter.snapshot_version,
            "results": hits,
            "record_id": f"snapshot:{adapter.snapshot_version}",
            "as_of": "2026-10-16",
        }

    def _get_section(args: dict[str, Any], _ctx: ToolContext) -> dict[str, Any]:
        sec = adapter.get_section(section_anchor=str(args["section_anchor"]))
        return {
            "snapshot_version": adapter.snapshot_version,
            "section": sec,
            "record_id": str(sec["id"]),
            "as_of": str(sec["effective_from"]),
        }

    def _list_forms(_args: dict[str, Any], _ctx: ToolContext) -> dict[str, Any]:
        return {
            "snapshot_version": adapter.snapshot_version,
            "forms": adapter.list_forms(),
            "record_id": "forms:directory",
            "as_of": "2026-10-16",
        }

    def _get_office_info(args: dict[str, Any], _ctx: ToolContext) -> dict[str, Any]:
        code = str(args.get("office_code", "JUBA_HQ"))
        office = adapter.get_office_info(office_code=code)
        return {
            "office": office,
            "record_id": f"office:{office['office_code']}",
            "as_of": "2026-10-16",
        }

    return [
        RegisteredTool(
            name="search_knowledge",
            description="Search published SSRA tax and customs legal knowledge chunks with citations and effective dates.",
            tier=RiskTier.T0,
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "minLength": 2, "maxLength": 500},
                    "language": {
                        "type": "string",
                        "enum": ["en", "pga", "ar", "din", "nus", "bfa", "zne", "shk"],
                    },
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 10},
                },
            },
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["snapshot_version", "results", "record_id", "as_of"],
                "properties": {
                    "snapshot_version": {"type": "string"},
                    "results": {"type": "array"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="PUBLIC",
            upstream_system="ssra-knowledge-pgvector",
            handler=_search_knowledge,
        ),
        RegisteredTool(
            name="get_section",
            description="Retrieve an exact published legal or procedural section by section_anchor or chunk ID.",
            tier=RiskTier.T0,
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["section_anchor"],
                "properties": {
                    "section_anchor": {"type": "string", "minLength": 1},
                },
            },
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["snapshot_version", "section", "record_id", "as_of"],
                "properties": {
                    "snapshot_version": {"type": "string"},
                    "section": {"type": "object"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="PUBLIC",
            upstream_system="ssra-knowledge-pgvector",
            handler=_get_section,
        ),
        RegisteredTool(
            name="list_forms",
            description="List official SSRA e-Tax forms and portal links.",
            tier=RiskTier.T0,
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
                "required": ["snapshot_version", "forms", "record_id", "as_of"],
                "properties": {
                    "snapshot_version": {"type": "string"},
                    "forms": {"type": "array"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="PUBLIC",
            upstream_system="ssra-knowledge-pgvector",
            handler=_list_forms,
        ),
        RegisteredTool(
            name="get_office_info",
            description="Get official SSRA office locations, Africa/Juba operating hours, and contact channels.",
            tier=RiskTier.T0,
            annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
            input_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "office_code": {"type": "string"},
                },
            },
            output_schema={
                "$schema": JSON_SCHEMA_2020_12,
                "type": "object",
                "additionalProperties": False,
                "required": ["office", "record_id", "as_of"],
                "properties": {
                    "office": {"type": "object"},
                    "record_id": {"type": "string"},
                    "as_of": {"type": "string"},
                },
            },
            data_classification="PUBLIC",
            upstream_system="ssra-knowledge-pgvector",
            handler=_get_office_info,
        ),
    ]
