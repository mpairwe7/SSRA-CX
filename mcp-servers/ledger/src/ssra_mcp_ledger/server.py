"""Stateless MCP 2026-07-28 server for SSRA ledger."""

from __future__ import annotations

from ssra_mcp import StatelessMcpServer

from ssra_mcp_ledger.adapters import get_ledger_adapter
from ssra_mcp_ledger.settings import LedgerServerSettings
from ssra_mcp_ledger.tools import build_ledger_tools


def create_ledger_mcp_server() -> StatelessMcpServer:
    settings = LedgerServerSettings()
    adapter = get_ledger_adapter()
    server = StatelessMcpServer(server_name=settings.server_name)
    for tool in build_ledger_tools(adapter):
        server.register_tool(tool)
    return server


mcp_server = create_ledger_mcp_server()
app = mcp_server.create_fastapi_app()
