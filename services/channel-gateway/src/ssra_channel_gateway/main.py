"""WhatsApp, SMS (GSM-7 vs UCS-2 segmentation), and USSD Channel Gateway (Section 5, 11)."""

from __future__ import annotations

import hashlib
import hmac
import math

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from ssra_core import (
    ChannelName,
    ConversationEvent,
    LocaleCode,
    McpErrorCode,
    SSRAError,
)
from ssra_testing import make_conversation_event

from ssra_channel_gateway.ussd import render_ussd_screen


def compute_sms_segments(text: str) -> dict[str, int | str]:
    """Compute SMS encoding (GSM-7 vs UCS-2) and segment count (Section 11: Arabic uses UCS-2 at 70 chars/segment)."""
    is_ascii_gsm7 = all(ord(ch) < 128 for ch in text)
    if is_ascii_gsm7:
        encoding = "GSM-7"
        single_limit = 160
        concat_limit = 153
    else:
        encoding = "UCS-2"
        single_limit = 70
        concat_limit = 67

    length = len(text)
    if length == 0:
        segments = 0
    elif length <= single_limit:
        segments = 1
    else:
        segments = math.ceil(length / concat_limit)

    return {
        "encoding": encoding,
        "char_count": length,
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


def create_channel_gateway_app(
    webhook_secret: str | None = None,
    *,
    max_requests_per_sender: int = 25,
) -> FastAPI:
    active_secret = webhook_secret or "ssra-dev-webhook-key"
    app = FastAPI(title="SSRA Assist Channel Gateway", version="0.1.0")
    seen_message_ids: set[str] = set()
    sender_counts: dict[str, int] = {}

    @app.exception_handler(SSRAError)
    async def ssra_error_handler(request: Request, exc: SSRAError) -> JSONResponse:
        raw_path = str(request.scope.get("path", "/"))
        problem = exc.to_problem_details(instance=raw_path)
        return JSONResponse(
            status_code=exc.status_code,
            content=problem.model_dump(mode="json"),
            media_type="application/problem+json",
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
        if x_hub_signature_256 is not None and not verify_webhook_hmac(
            raw_bytes, x_hub_signature_256, active_secret
        ):
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "Invalid webhook HMAC signature",
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
        seen_message_ids.add(body.message_id)

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
        return {
            "status": "normalised",
            "cloud_event": event.model_dump(mode="json"),
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
