"""AG-UI Protocol over SSE Streaming Endpoint (Sections 5, 6.1, 9.3, 10.1, ADR-005)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from ssra_core import new_id

from ssra_runtime.schemas import RuntimeTurnResponse


def format_sse_event(event_type: str, data: dict[str, Any], event_id: str | None = None) -> str:
    eid = event_id or new_id("agui")
    payload = json.dumps({"type": event_type, **data}, ensure_ascii=False)
    return f"id: {eid}\nevent: agui\ndata: {payload}\n\n"


async def stream_agui_events(turn: RuntimeTurnResponse) -> AsyncIterator[str]:
    """Yield standard AG-UI SSE lifecycle events from a completed RuntimeTurnResponse."""
    run_id = new_id("run")
    msg_id = new_id("msg")

    yield format_sse_event(
        "RUN_STARTED",
        {
            "threadId": turn.thread_id,
            "runId": run_id,
            "tier": turn.tier.value,
            "locale": turn.locale.value,
        },
    )

    for art in turn.artifacts:
        yield format_sse_event(
            "TOOL_CALL_START",
            {
                "toolCallId": art.id,
                "toolCallName": f"{art.server}.{art.tool}",
                "tier": art.tier.value,
            },
        )
        yield format_sse_event(
            "TOOL_CALL_END",
            {
                "toolCallId": art.id,
                "toolCallName": f"{art.server}.{art.tool}",
                "provenance": art.provenance,
            },
        )

    yield format_sse_event(
        "TEXT_MESSAGE_START",
        {"messageId": msg_id, "role": "assistant"},
    )

    for seg in turn.answer.segments:
        yield format_sse_event(
            "TEXT_MESSAGE_CONTENT",
            {
                "messageId": msg_id,
                "delta": seg.text,
                "citationIds": seg.citation_ids,
            },
        )

    yield format_sse_event(
        "TEXT_MESSAGE_END",
        {"messageId": msg_id},
    )

    if turn.answer.citations:
        yield format_sse_event(
            "CUSTOM",
            {
                "name": "ssra.citations",
                "value": [c.model_dump(mode="json") for c in turn.answer.citations],
            },
        )

    if turn.answer.ui_component is not None:
        yield format_sse_event(
            "CUSTOM",
            {
                "name": "ssra.ui_component",
                "value": turn.answer.ui_component.model_dump(mode="json"),
            },
        )

    yield format_sse_event(
        "RUN_FINISHED",
        {
            "threadId": turn.thread_id,
            "runId": run_id,
            "auditEventHash": turn.audit_event_hash,
            "abstained": turn.answer.abstained,
            "isEstimate": turn.answer.is_estimate,
        },
    )
