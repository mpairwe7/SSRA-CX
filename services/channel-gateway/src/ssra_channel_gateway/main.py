"""WhatsApp, SMS (GSM-7 vs UCS-2 segmentation), and USSD Channel Gateway (Section 5, 11)."""

from __future__ import annotations

import hashlib
import hmac
import math
import re
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from ssra_core import (
    ChannelName,
    ConversationEvent,
    LocaleCode,
    McpErrorCode,
    SSRAError,
    ensure_w3c_traceparent,
)
from ssra_testing import make_conversation_event

from ssra_channel_gateway.ussd import render_ussd_screen

_VALID_HOST_RE = re.compile(r"^[A-Za-z0-9.\[\]:-]+$")
_MAX_CHANNEL_BODY_BYTES = 1_048_576
_CHANNEL_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}

# 3GPP TS 23.038 / GSM 03.38 Basic (1 septet) and Extended (2 septets via 0x1B escape) character sets
_GSM7_BASIC_CHARS: frozenset[str] = frozenset(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
_GSM7_EXTENDED_CHARS: frozenset[str] = frozenset("^{}\\[~]|€\f")
MAX_SEEN_MESSAGE_IDS = 4096


def compute_sms_segments(text: str) -> dict[str, int | str]:
    """Compute SMS encoding (3GPP TS 23.038 GSM-7 + Extended vs UCS-2) and segment count (Section 11)."""
    is_gsm7 = all(ch in _GSM7_BASIC_CHARS or ch in _GSM7_EXTENDED_CHARS for ch in text)
    if is_gsm7:
        encoding = "GSM-7"
        single_limit = 160
        concat_limit = 153
        unit_count = sum(2 if ch in _GSM7_EXTENDED_CHARS else 1 for ch in text)
    else:
        encoding = "UCS-2"
        single_limit = 70
        concat_limit = 67
        unit_count = len(text)

    char_length = len(text)
    if unit_count == 0:
        segments = 0
    elif unit_count <= single_limit:
        segments = 1
    else:
        segments = math.ceil(unit_count / concat_limit)

    return {
        "encoding": encoding,
        "char_count": char_length,
        "septet_or_code_unit_count": unit_count,
        "segments": segments,
        "per_segment_limit": single_limit,
    }


def verify_webhook_hmac(payload: bytes, signature_header: str | None, secret: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    provided = signature_header.removeprefix("sha256=").strip()
    return hmac.compare_digest(expected, provided)


class InboundChannelWebhook(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    channel: ChannelName
    sender_ref: str
    text: str
    locale: LocaleCode = LocaleCode.EN


class UssdSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    ussd_input: str = ""
    elapsed_seconds: int = 0
    locale: str = "en"


def create_channel_gateway_app(
    webhook_secret: str | None = None,
    *,
    max_requests_per_sender: int = 25,
    require_signature: bool = False,
) -> FastAPI:
    active_secret = webhook_secret or "ssra-dev-webhook-key"
    app = FastAPI(title="SSRA Assist Channel Gateway", version="0.1.0")
    seen_message_ids: dict[str, None] = {}
    sender_counts: dict[str, int] = {}
    opted_out_senders: set[str] = set()

    @app.middleware("http")
    async def channel_security_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        raw_path = str(request.scope.get("path", "/"))
        tp = ensure_w3c_traceparent(request.headers.get("traceparent"))
        host_header = request.headers.get("host", "localhost")
        if not host_header or not _VALID_HOST_RE.match(host_header):
            err = SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                "Malformed HTTP Host header rejected per RFC 9112 §3.2 (CVE-2026-48710)",
                status_code=400,
            )
            return JSONResponse(
                status_code=400,
                content=err.to_problem_details(instance=raw_path, trace_id=tp).model_dump(
                    mode="json"
                ),
                media_type="application/problem+json",
                headers={"traceparent": tp, **_CHANNEL_SECURITY_HEADERS},
            )
        if request.method in ("POST", "PUT", "PATCH"):
            req_bytes = await request.body()
            if len(req_bytes) > _MAX_CHANNEL_BODY_BYTES:
                err = SSRAError(
                    McpErrorCode.VALIDATION_FAILED,
                    f"Request body exceeds maximum allowed size of {_MAX_CHANNEL_BODY_BYTES} bytes",
                    status_code=413,
                )
                return JSONResponse(
                    status_code=413,
                    content=err.to_problem_details(instance=raw_path, trace_id=tp).model_dump(
                        mode="json"
                    ),
                    media_type="application/problem+json",
                    headers={"traceparent": tp, **_CHANNEL_SECURITY_HEADERS},
                )
        response = await call_next(request)
        response.headers["traceparent"] = tp
        for hk, hv in _CHANNEL_SECURITY_HEADERS.items():
            response.headers.setdefault(hk, hv)
        return response

    @app.exception_handler(SSRAError)
    async def ssra_error_handler(request: Request, exc: SSRAError) -> JSONResponse:
        raw_path = str(request.scope.get("path", "/"))
        tp = ensure_w3c_traceparent(request.headers.get("traceparent"))
        problem = exc.to_problem_details(instance=raw_path, trace_id=tp)
        return JSONResponse(
            status_code=exc.status_code,
            content=problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"traceparent": tp, **_CHANNEL_SECURITY_HEADERS},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        raw_path = str(request.scope.get("path", "/"))
        tp = ensure_w3c_traceparent(request.headers.get("traceparent"))
        err = SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            f"Channel gateway validation failed ({len(exc.errors())} error(s))",
            status_code=422,
        )
        return JSONResponse(
            status_code=422,
            content=err.to_problem_details(instance=raw_path, trace_id=tp).model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"traceparent": tp, **_CHANNEL_SECURITY_HEADERS},
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "ssra-channel-gateway"}

    @app.post("/v1/webhooks/inbound")
    async def inbound_webhook(
        request: Request,
        x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    ) -> dict[str, object]:
        raw_bytes = await request.body()
        if (require_signature or x_hub_signature_256 is not None) and not verify_webhook_hmac(
            raw_bytes, x_hub_signature_256, active_secret
        ):
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "Invalid or missing webhook HMAC signature",
                status_code=401,
            )

        body = InboundChannelWebhook.model_validate_json(raw_bytes)
        if body.message_id in seen_message_ids:
            return {"status": "deduplicated_drop", "message_id": body.message_id}

        current_count = sender_counts.get(body.sender_ref, 0)
        if current_count >= max_requests_per_sender:
            raise SSRAError(
                McpErrorCode.RATE_LIMITED,
                f"Per-sender rate limit ({max_requests_per_sender}) exceeded for '{body.sender_ref}'",
                status_code=429,
            )
        sender_counts[body.sender_ref] = current_count + 1
        if len(seen_message_ids) >= MAX_SEEN_MESSAGE_IDS:
            oldest_mid = next(iter(seen_message_ids))
            seen_message_ids.pop(oldest_mid, None)
        seen_message_ids[body.message_id] = None

        max_len = (
            182
            if body.channel == ChannelName.USSD
            else (160 if body.channel == ChannelName.SMS else 4096)
        )
        event: ConversationEvent = make_conversation_event(
            body.text,
            locale=body.locale,
            channel=body.channel,
            thread_id=f"thr_{body.channel.value}_{body.sender_ref}",
            max_len=max_len,
            rich_ui=body.channel == ChannelName.WEB,
        )
        upper_txt = body.text.strip().upper()
        consent_action: str | None = None
        if upper_txt in ("STOP", "UNSUBSCRIBE"):
            opted_out_senders.add(body.sender_ref)
            consent_action = "OPTED_OUT"
        elif upper_txt == "START":
            opted_out_senders.discard(body.sender_ref)
            consent_action = "OPTED_IN"

        return {
            "status": "normalised",
            "cloud_event": event.model_dump(mode="json"),
            "consent_action": consent_action,
            "sender_opted_out": body.sender_ref in opted_out_senders,
            "sms_metrics": compute_sms_segments(body.text)
            if body.channel == ChannelName.SMS
            else None,
        }

    @app.post("/v1/ussd/session")
    async def ussd_session(body: UssdSessionRequest) -> dict[str, object]:
        screen = render_ussd_screen(
            session_id=body.session_id,
            ussd_input=body.ussd_input,
            elapsed_seconds=body.elapsed_seconds,
            locale=body.locale,
        )
        return {
            "session_id": screen.session_id,
            "response_type": screen.response_type,
            "screen_text": screen.screen_text,
            "char_length": len(screen.screen_text),
            "send_sms_followup": screen.send_sms_followup,
        }

    return app


app = create_channel_gateway_app()
