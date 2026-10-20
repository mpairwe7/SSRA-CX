"""AG-UI Protocol over SSE Streaming Endpoint (Sections 5, 6.1, 9.3, 10.1, ADR-005)."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

from ssra_core import new_id

from ssra_runtime.schemas import RuntimeTurnResponse

_BEARER_OR_JWT_RE = re.compile(
    r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}\b|\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"
)
_INTERNAL_DSN_RE = re.compile(r"(?i)\b(?:postgres(?:ql)?|redis|valkey)://[^\s\"']+")
_UNMASKED_PHONE_RE = re.compile(r"(?<!\d)\+?211[\s-]?\d{9}\b")
_UNMASKED_TIN_RE = re.compile(r"\b\d{9,12}\b")


def scrub_agui_stream_dlp(text: str) -> str:
    """Scrub leaked secrets, JWTs, internal DSNs, and unmasked TINs/phones from outgoing AG-UI SSE chunks."""
    if not text:
        return text
    cleaned = _BEARER_OR_JWT_RE.sub("[REDACTED_SECRET_TOKEN]", text)
    cleaned = _INTERNAL_DSN_RE.sub("[REDACTED_INTERNAL_DSN]", cleaned)
    cleaned = _UNMASKED_PHONE_RE.sub("[REDACTED_PHONE]", cleaned)
    return _UNMASKED_TIN_RE.sub("[REDACTED_TIN]", cleaned)


def format_sse_event(event_type: str, data: dict[str, Any], event_id: str | None = None) -> str:
    eid = event_id or new_id("agui")
    payload = json.dumps({"type": event_type, **data}, ensure_ascii=False)
    return f"id: {eid}\nevent: agui\ndata: {payload}\n\n"


async def stream_agui_events(
    turn: RuntimeTurnResponse,
    *,
    last_event_id: str | None = None,
) -> AsyncIterator[str]:
    """Yield standard AG-UI SSE lifecycle events with resumable `Last-Event-ID` support."""
    run_id = new_id("run")
    msg_id = new_id("msg")
    staged: list[tuple[str, str, dict[str, Any]]] = []

    def _push(event_type: str, data: dict[str, Any]) -> None:
        seq = len(staged) + 1
        staged.append((f"{turn.thread_id}:ev:{seq}", event_type, data))

    _push(
        "RUN_STARTED",
        {
            "threadId": turn.thread_id,
            "runId": run_id,
            "tier": turn.tier.value,
            "locale": turn.locale.value,
        },
    )

    for art in turn.artifacts:
        _push(
            "TOOL_CALL_START",
            {
                "toolCallId": art.id,
                "toolCallName": f"{art.server}.{art.tool}",
                "tier": art.tier.value,
            },
        )
        _push(
            "TOOL_CALL_END",
            {
                "toolCallId": art.id,
                "toolCallName": f"{art.server}.{art.tool}",
                "provenance": art.provenance,
            },
        )

    _push(
        "TEXT_MESSAGE_START",
        {"messageId": msg_id, "role": "assistant"},
    )

    for seg in turn.answer.segments:
        _push(
            "TEXT_MESSAGE_CONTENT",
            {
                "messageId": msg_id,
                "delta": scrub_agui_stream_dlp(seg.text),
                "citationIds": seg.citation_ids,
            },
        )

    _push(
        "TEXT_MESSAGE_END",
        {"messageId": msg_id},
    )

    if turn.answer.citations:
        _push(
            "CUSTOM",
            {
                "name": "ssra.citations",
                "value": [c.model_dump(mode="json") for c in turn.answer.citations],
            },
        )

    if turn.answer.ui_component is not None:
        _push(
            "CUSTOM",
            {
                "name": "ssra.ui_component",
                "value": turn.answer.ui_component.model_dump(mode="json"),
            },
        )

    _push(
        "RUN_FINISHED",
        {
            "threadId": turn.thread_id,
            "runId": run_id,
            "auditEventHash": turn.audit_event_hash,
            "abstained": turn.answer.abstained,
            "isEstimate": turn.answer.is_estimate,
        },
    )

    start_idx = 0
    if last_event_id:
        cleaned_last = last_event_id.strip()
        for idx, (eid, _, _) in enumerate(staged):
            if eid == cleaned_last:
                start_idx = idx + 1
                break

    for eid, ev_type, payload in staged[start_idx:]:
        yield format_sse_event(ev_type, payload, event_id=eid)
