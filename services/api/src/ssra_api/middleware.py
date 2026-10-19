"""API Conventions & Security Middleware (Section 10.4, RFC 9457, CVE-2026-48710, CVE-2026-54283).

Enforces:
1. W3C `traceparent` generation & propagation
2. RFC 9112 §3.2 `Host` header validation and raw ASGI `scope["path"]` routing (`CVE-2026-48710` / `CVE-2026-54282`)
3. Request payload size cap (`MAX_REQUEST_BODY_BYTES = 1_048_576`, `CVE-2026-54283`)
4. IETF `Idempotency-Key` replay with SHA-256 request-body binding (`422` on mutated payload) and bounded FIFO cache
5. Strong `ETag` / `If-None-Match` (`304 Not Modified`)
6. Standard government HTTP security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict
from ssra_core import ensure_w3c_traceparent

MAX_REQUEST_BODY_BYTES = 1_048_576
MAX_IDEMPOTENCY_ENTRIES = 2048
_VALID_HOST_RE = re.compile(r"^[A-Za-z0-9.\[\]:-]+$")

SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


class CursorPage[T](BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False


def generate_w3c_traceparent() -> str:
    trace_id = os.urandom(16).hex()
    span_id = os.urandom(8).hex()
    return f"00-{trace_id}-{span_id}-01"


def _problem_response(
    *,
    status_code: int,
    code: str,
    title: str,
    detail: str,
    instance: str,
    traceparent: str,
) -> Response:
    body = json.dumps(
        {
            "type": f"https://ssra.gov.ss/problems/{code.lower()}",
            "title": title,
            "status": status_code,
            "detail": detail,
            "instance": instance,
            "code": code,
            "trace_id": traceparent,
            "retriable": False,
        }
    ).encode("utf-8")
    return Response(
        content=body,
        status_code=status_code,
        media_type="application/problem+json",
        headers={"traceparent": traceparent, **SECURITY_HEADERS},
    )


def install_api_conventions_middleware(app: FastAPI) -> None:
    idempotency_cache: dict[str, tuple[str, int, bytes, str]] = {}

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> Response:
        raw_path = str(request.scope.get("path", "/"))
        traceparent = ensure_w3c_traceparent(request.headers.get("traceparent"))
        return _problem_response(
            status_code=422,
            code="VALIDATION_FAILED",
            title="Request Validation Failed",
            detail=f"Invalid request parameters ({len(exc.errors())} validation error(s)).",
            instance=raw_path,
            traceparent=traceparent,
        )

    @app.middleware("http")
    async def api_conventions_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        raw_path = str(request.scope.get("path", "/"))
        traceparent = ensure_w3c_traceparent(request.headers.get("traceparent"))

        # 1. Validate Host header per RFC 9112 §3.2 (CVE-2026-48710 & CVE-2026-54282)
        host_header = request.headers.get("host", "localhost")
        if not host_header or not _VALID_HOST_RE.match(host_header):
            return _problem_response(
                status_code=400,
                code="INVALID_HOST_HEADER",
                title="Invalid Host Header",
                detail="Malformed HTTP Host header rejected per RFC 9112 §3.2.",
                instance=raw_path,
                traceparent=traceparent,
            )

        # 2. Enforce request payload cap on both Content-Length and chunked body (CVE-2026-54283)
        req_bytes = await request.body() if request.method in ("POST", "PUT", "PATCH") else b""
        content_len_str = request.headers.get("content-length")
        declared_len = int(content_len_str) if content_len_str and content_len_str.isdigit() else 0
        if max(declared_len, len(req_bytes)) > MAX_REQUEST_BODY_BYTES:
            return _problem_response(
                status_code=413,
                code="PAYLOAD_TOO_LARGE",
                title="Content Too Large",
                detail=f"Request body exceeds maximum allowed size of {MAX_REQUEST_BODY_BYTES} bytes.",
                instance=raw_path,
                traceparent=traceparent,
            )

        idem_key = request.headers.get("Idempotency-Key")
        caller_ctx = (
            f"{request.headers.get('authorization', '')}:"
            f"{request.headers.get('x-ssra-subject-ref', '')}"
        )
        caller_scope = hashlib.sha256(caller_ctx.encode("utf-8")).hexdigest()[:16]
        cache_key = (
            f"{caller_scope}:{request.method}:{raw_path}:{idem_key}"
            if request.method == "POST" and idem_key
            else None
        )
        req_body_sha256 = ""
        if cache_key:
            req_body_sha256 = hashlib.sha256(req_bytes).hexdigest()
            if cache_key in idempotency_cache:
                stored_sha, status_code, cached_body, media_type = idempotency_cache[cache_key]
                if stored_sha != req_body_sha256:
                    return _problem_response(
                        status_code=422,
                        code="IDEMPOTENCY_KEY_PAYLOAD_MISMATCH",
                        title="Idempotency-Key Payload Mismatch",
                        detail="Idempotency-Key was reused with a different request payload.",
                        instance=raw_path,
                        traceparent=traceparent,
                    )
                return Response(
                    content=cached_body,
                    status_code=status_code,
                    media_type=media_type,
                    headers={
                        "traceparent": traceparent,
                        "X-Idempotency-Replayed": "true",
                        **SECURITY_HEADERS,
                    },
                )

        response = await call_next(request)
        response.headers["traceparent"] = traceparent
        for hk, hv in SECURITY_HEADERS.items():
            response.headers.setdefault(hk, hv)

        content_type = (response.media_type or response.headers.get("content-type", "")).lower()
        if content_type.startswith("text/event-stream"):
            response.headers.setdefault("Cache-Control", "no-cache, no-transform")
            response.headers.setdefault("X-Accel-Buffering", "no")
            return response

        if (request.method == "GET" and raw_path.startswith("/v1/")) or (
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
                        headers={"ETag": etag, "traceparent": traceparent, **SECURITY_HEADERS},
                    )
                response.headers["ETag"] = etag

            if cache_key and 200 <= response.status_code < 300:
                if len(idempotency_cache) >= MAX_IDEMPOTENCY_ENTRIES:
                    oldest_key = next(iter(idempotency_cache))
                    idempotency_cache.pop(oldest_key, None)
                idempotency_cache[cache_key] = (
                    req_body_sha256,
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
