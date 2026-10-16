"""API Conventions Middleware: W3C traceparent, ETag / If-None-Match, Idempotency-Key replay, and Cursor Pagination (Section 10.4)."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel, ConfigDict


class CursorPage[T](BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False


def generate_w3c_traceparent() -> str:
    trace_id = os.urandom(16).hex()
    span_id = os.urandom(8).hex()
    return f"00-{trace_id}-{span_id}-01"


def install_api_conventions_middleware(app: FastAPI) -> None:
    idempotency_cache: dict[str, tuple[int, bytes, str]] = {}

    @app.middleware("http")
    async def api_conventions_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        traceparent = request.headers.get("traceparent") or generate_w3c_traceparent()
        idem_key = request.headers.get("Idempotency-Key")
        cache_key = (
            f"{request.method}:{request.url.path}:{idem_key}"
            if request.method == "POST" and idem_key
            else None
        )

        if cache_key and cache_key in idempotency_cache:
            status_code, cached_body, media_type = idempotency_cache[cache_key]
            return Response(
                content=cached_body,
                status_code=status_code,
                media_type=media_type,
                headers={
                    "traceparent": traceparent,
                    "X-Idempotency-Replayed": "true",
                },
            )

        response = await call_next(request)
        response.headers["traceparent"] = traceparent

        # Buffer response body for GET ETag or POST Idempotency-Key caching
        if (request.method == "GET" and request.url.path.startswith("/v1/")) or (
            cache_key and 200 <= response.status_code < 300
        ):
            body_chunks: list[bytes] = []
            async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                if isinstance(chunk, str):
                    body_chunks.append(chunk.encode("utf-8"))
                else:
                    body_chunks.append(bytes(chunk))
            raw_body = b"".join(body_chunks)

            if request.method == "GET":
                etag = f'"{hashlib.sha256(raw_body).hexdigest()[:32]}"'
                if request.headers.get("If-None-Match") == etag:
                    return Response(
                        status_code=304,
                        headers={"ETag": etag, "traceparent": traceparent},
                    )
                response.headers["ETag"] = etag

            if cache_key and 200 <= response.status_code < 300:
                idempotency_cache[cache_key] = (
                    response.status_code,
                    raw_body,
                    response.media_type or "application/json",
                )
                response.headers["X-Idempotency-Replayed"] = "false"

            return Response(
                content=raw_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        return response
