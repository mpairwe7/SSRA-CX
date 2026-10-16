# MCP Server Template (`mcp-servers/_template/`)

Every SSRA Assist MCP server follows this exact layout (Section 16):

```text
mcp-servers/<domain>/
├── pyproject.toml
├── Dockerfile
├── src/ssra_mcp_<domain>/
│   ├── __init__.py
│   ├── server.py        # Stateless MCP 2026-07-28 server & FastAPI app
│   ├── tools/           # JSON Schema 2020-12 definitions & tool handlers
│   ├── adapters.py      # Anti-corruption port -> upstream adapter or mock
│   └── settings.py
└── tests/               # Unit, schema conformance, and stateless 2026-07-28 contract tests
```
