"""Stateless MCP 2026-07-28 server for SSRA official-channels."""

from __future__ import annotations

from ssra_mcp import StatelessMcpServer

from ssra_mcp_official_channels.adapters import get_official_channels_adapter
from ssra_mcp_official_channels.settings import OfficialChannelsSettings
from ssra_mcp_official_channels.tools import build_official_channels_tools


def create_official_channels_mcp_server() -> StatelessMcpServer:
    settings = OfficialChannelsSettings()
    adapter = get_official_channels_adapter()
    server = StatelessMcpServer(server_name=settings.server_name)
    for tool in build_official_channels_tools(adapter):
        server.register_tool(tool)
    return server


mcp_server = create_official_channels_mcp_server()
app = mcp_server.create_fastapi_app()
