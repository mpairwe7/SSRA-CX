#!/usr/bin/env python3
"""Generator for new Stateless MCP 2026-07-28 servers from `mcp-servers/_template/` (Section 16)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_FILE = ROOT / "mcp-servers" / "_template" / "server.py.tmpl"


def render_mcp_server_code(
    *,
    server_name: str,
    tool_name: str,
    tool_description: str,
    tier: str = "T0",
) -> str:
    if tier == "T4":
        raise ValueError("Principle 3: T4 is human-only; cannot generate a T4 MCP tool.")
    pkg_suffix = server_name.replace("-", "_")
    raw = TEMPLATE_FILE.read_text(encoding="utf-8")
    return (
        raw.replace("{{SERVER_NAME}}", server_name)
        .replace("{{PACKAGE_SUFFIX}}", pkg_suffix)
        .replace("{{TOOL_NAME}}", tool_name)
        .replace("{{TOOL_DESCRIPTION}}", tool_description)
        .replace("{{TIER}}", tier)
    )


if __name__ == "__main__":
    print(
        render_mcp_server_code(
            server_name="eservices-bridge",
            tool_name="verify_business_registry",
            tool_description="Verify Ministry of Justice business registry entry.",
            tier="T0",
        )
    )
