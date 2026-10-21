"""Synchronous test access to ASGI applications without Starlette's portal adapter."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterable
from typing import Any, cast

import httpx


class AsgiTestClient:
    """Run synchronous tests against an ASGI app through httpx's ASGI transport.

    This keeps tests deterministic when an application returns before consuming
    a request body, which can block Starlette's synchronous ``TestClient``
    adapter in the current dependency stack.
    """

    def __init__(self, app: Any, *, base_url: str = "http://testserver") -> None:
        self._app = app
        self._base_url = base_url

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Make one request using a fresh client to isolate application state."""
        return asyncio.run(self._request(method, url, **kwargs))

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        content = kwargs.get("content")
        if isinstance(content, Iterable) and not isinstance(
            content, (bytes, bytearray, memoryview, str)
        ):
            kwargs["content"] = self._as_async_stream(cast(Iterable[bytes], content))
        transport = httpx.ASGITransport(app=self._app)
        async with httpx.AsyncClient(transport=transport, base_url=self._base_url) as client:
            return await client.request(method, url, **kwargs)

    @staticmethod
    async def _as_async_stream(chunks: Iterable[bytes]) -> AsyncIterator[bytes]:
        for chunk in chunks:
            yield chunk
