#!/usr/bin/env python3
"""CI validator for JSON Schema 2020-12 contracts, MCP tool schemas, and risk-tier invariants."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from ssra_core import RiskTier
from ssra_mcp import JSON_SCHEMA_2020_12
from ssra_runtime.tools import GovernedMcpGatewayClient

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    # 1. Validate all JSON Schemas in packages/contracts/schemas/
    schema_dir = ROOT / "packages" / "contracts" / "schemas"
    schema_files = sorted(schema_dir.glob("*.schema.json"))
    assert len(schema_files) >= 3, "Missing canonical JSON schemas in packages/contracts/schemas/"
    for path in schema_files:
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw.get("$schema") == JSON_SCHEMA_2020_12, (
            f"{path.name} must use JSON Schema 2020-12"
        )
        jsonschema.Draft202012Validator.check_schema(raw)

    # 2. Validate every registered MCP tool across all 11 servers
    gateway = GovernedMcpGatewayClient()
    total_tools = 0
    for srv_name, srv in gateway.servers.items():
        for tool_name, tool in srv.tools.items():
            assert tool.tier != RiskTier.T4, f"Forbidden T4 tool: {srv_name}.{tool_name}"
            assert tool.input_schema.get("$schema") == JSON_SCHEMA_2020_12
            assert tool.output_schema.get("$schema") == JSON_SCHEMA_2020_12
            jsonschema.Draft202012Validator.check_schema(tool.input_schema)
            jsonschema.Draft202012Validator.check_schema(tool.output_schema)
            total_tools += 1

    print(
        f"Schema validation passed: {len(schema_files)} contract schemas and {total_tools} MCP tools across 11 servers."
    )


if __name__ == "__main__":
    main()
