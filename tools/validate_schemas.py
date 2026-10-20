#!/usr/bin/env python3
"""CI validator for JSON Schema 2020-12 contracts, MCP tool schemas, and risk-tier invariants."""

from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
from ssra_core import RiskTier
from ssra_mcp import JSON_SCHEMA_2020_12, MCP_PROTOCOL_VERSION
from ssra_runtime.tools import GovernedMcpGatewayClient

ROOT = Path(__file__).resolve().parents[1]
_RFC9110_TOKEN_RE = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")


def main() -> None:
    """Validate canonical JSON Schemas and all 11 Stateless MCP 2026-07-28 servers and tools."""
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

    # 2. Validate every registered MCP server and tool across all 11 servers
    gateway = GovernedMcpGatewayClient()
    total_tools = 0
    for srv_name, srv in gateway.servers.items():
        discover = srv.handle_server_discover()
        assert discover["resultType"] == "complete", (
            f"{srv_name} server/discover missing resultType"
        )
        assert MCP_PROTOCOL_VERSION in discover["supportedProtocolVersions"]

        listing = srv.handle_list_tools()
        assert listing["resultType"] == "complete", f"{srv_name} tools/list missing resultType"
        assert listing["cacheScope"] == "private", f"{srv_name} tools/list missing cacheScope"
        listed_names = [t["name"] for t in listing["tools"]]
        assert listed_names == sorted(listed_names), (
            f"{srv_name} tools/list must return deterministic sorted order"
        )

        for tool_name, tool in srv.tools.items():
            assert tool.tier != RiskTier.T4, f"Forbidden T4 tool: {srv_name}.{tool_name}"
            assert tool.input_schema.get("$schema") == JSON_SCHEMA_2020_12
            assert tool.output_schema.get("$schema") == JSON_SCHEMA_2020_12
            assert tool.input_schema.get("additionalProperties") is False, (
                f"{srv_name}.{tool_name} input_schema must set additionalProperties: False"
            )
            assert tool.output_schema.get("additionalProperties") is False, (
                f"{srv_name}.{tool_name} output_schema must set additionalProperties: False"
            )
            req_out = set(tool.output_schema.get("required", []))
            assert {"record_id", "as_of"}.issubset(req_out), (
                f"{srv_name}.{tool_name} output_schema must require 'record_id' and 'as_of'"
            )
            for prop_spec in tool.input_schema.get("properties", {}).values():
                if isinstance(prop_spec, dict) and "x-mcp-header" in prop_spec:
                    hdr_tok = str(prop_spec["x-mcp-header"])
                    assert _RFC9110_TOKEN_RE.match(hdr_tok), (
                        f"Invalid x-mcp-header token '{hdr_tok}' on {srv_name}.{tool_name}"
                    )
            jsonschema.Draft202012Validator.check_schema(tool.input_schema)
            jsonschema.Draft202012Validator.check_schema(tool.output_schema)
            total_tools += 1

    # 3. Verify offline-resilience.ts PAYE & WHT constants match TaxFactsRegistry (seed-2026.10.1.yaml)
    from ssra_rules import TaxFactsRegistry

    reg = TaxFactsRegistry.from_yaml_file()
    offline_ts = (ROOT / "packages" / "chat-ui" / "src" / "offline-resilience.ts").read_text(
        encoding="utf-8"
    )
    assert f"b1MaxSsp: {int(reg.get_fact('paye.bracket.1.max_monthly_ssp').value):_}" in offline_ts
    assert f"b2MaxSsp: {int(reg.get_fact('paye.bracket.2.max_monthly_ssp').value):_}" in offline_ts
    assert f"b3MaxSsp: {int(reg.get_fact('paye.bracket.3.max_monthly_ssp').value):_}" in offline_ts
    for wht_cat in (
        "goods_and_services",
        "rent",
        "technical_fees",
        "government_contractors_resident",
        "government_contractors_non_resident",
        "mobile_money_commissions",
        "end_of_service_benefits",
    ):
        expected_rate = int(reg.get_fact(f"wht.{wht_cat}.rate_percent").value)
        assert f"{wht_cat}: {expected_rate}" in offline_ts, (
            f"Offline WHT rate drift for {wht_cat} in offline-resilience.ts"
        )

    print(
        f"Schema validation passed: {len(schema_files)} contract schemas and {total_tools} MCP tools across 11 servers."
    )


if __name__ == "__main__":
    main()
