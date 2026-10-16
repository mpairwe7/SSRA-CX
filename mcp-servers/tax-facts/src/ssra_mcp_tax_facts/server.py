"""Stateless MCP 2026-07-28 server for SSRA tax-facts."""

from __future__ import annotations

from ssra_mcp import StatelessMcpServer

from ssra_mcp_tax_facts.adapters import get_tax_facts_adapter
from ssra_mcp_tax_facts.settings import TaxFactsServerSettings
from ssra_mcp_tax_facts.tools import build_tax_facts_tools


def create_tax_facts_mcp_server() -> StatelessMcpServer:
    settings = TaxFactsServerSettings()
    registry = get_tax_facts_adapter()
    server = StatelessMcpServer(server_name=settings.server_name)
    for tool in build_tax_facts_tools(registry):
        server.register_tool(tool)
    return server


mcp_server = create_tax_facts_mcp_server()
app = mcp_server.create_fastapi_app()
