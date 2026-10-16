"""Stateless MCP 2026-07-28 server for SSRA knowledge."""

from __future__ import annotations

from ssra_mcp import StatelessMcpServer

from ssra_mcp_knowledge.adapters import KnowledgeCorpusAdapter
from ssra_mcp_knowledge.settings import KnowledgeServerSettings
from ssra_mcp_knowledge.tools import build_knowledge_tools


def create_knowledge_mcp_server() -> StatelessMcpServer:
    settings = KnowledgeServerSettings()
    adapter = KnowledgeCorpusAdapter()
    server = StatelessMcpServer(server_name=settings.server_name)
    for tool in build_knowledge_tools(adapter):
        server.register_tool(tool)
    return server


mcp_server = create_knowledge_mcp_server()
app = mcp_server.create_fastapi_app()
