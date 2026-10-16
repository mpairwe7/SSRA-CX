#!/usr/bin/env python3
"""End-to-end AG-UI hello-world smoke test through runtime -> agentgateway -> MCP server."""

from __future__ import annotations

from fastapi.testclient import TestClient
from ssra_api import create_api_app
from ssra_runtime import create_runtime_app


def main() -> None:
    api_client = TestClient(create_api_app())
    rt_client = TestClient(create_runtime_app())

    assert api_client.get("/healthz").status_code == 200
    assert rt_client.get("/healthz").status_code == 200

    stream_res = rt_client.post(
        "/v1/agui/stream",
        json={
            "message": "How much is PAYE on 250,000 SSP per month and how do I register for a TIN?",
            "locale": "en",
            "channel": "web",
        },
    )
    assert stream_res.status_code == 200
    assert "RUN_STARTED" in stream_res.text
    assert "TOOL_CALL_START" in stream_res.text
    assert "TEXT_MESSAGE_CONTENT" in stream_res.text
    assert "RUN_FINISHED" in stream_res.text
    print("End-to-end AG-UI hello-world smoke test passed.")


if __name__ == "__main__":
    main()
