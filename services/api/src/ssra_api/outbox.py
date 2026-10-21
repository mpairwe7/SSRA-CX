"""Process-local CloudEvents buffer used by reference-mode tests; it is not a transactional outbox."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict
from ssra_core import McpErrorCode, SSRAError, new_id, utc_now
from ssra_security import redact_pii

MAX_STAGED_OUTBOX_EVENTS = 4096


def _redact_outbox_value(val: Any) -> Any:
    """Recursively redact PII in strings, dicts, lists, and tuples before outbox staging."""
    if isinstance(val, str):
        return redact_pii(val).redacted_text
    if isinstance(val, dict):
        return {str(k): _redact_outbox_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_redact_outbox_value(item) for item in val]
    if isinstance(val, tuple):
        return tuple(_redact_outbox_value(item) for item in val)
    return val


def _redact_outbox_data(data: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a domain event payload dictionary by recursively redacting PII."""
    return {str(k): _redact_outbox_value(v) for k, v in data.items()}


class OutboxCloudEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    specversion: str = "1.0"
    id: str
    source: str
    type: str
    subject: str
    time: datetime
    datacontenttype: str = "application/json"
    data: dict[str, Any]
    published_to_nats: bool = False


class InMemoryOutboxBuffer:
    """Hold bounded, PII-redacted events for reference tests without claiming durable delivery."""

    def __init__(self, *, max_staged_events: int = MAX_STAGED_OUTBOX_EVENTS) -> None:
        """Initialise an in-memory event buffer with an explicit capacity."""
        if max_staged_events < 1:
            raise ValueError("max_staged_events must be at least 1")
        self._lock = threading.RLock()
        self._max_staged_events = max_staged_events
        self._staged: list[OutboxCloudEvent] = []
        self._active_knowledge_snapshot: str = "2026.10.1"

    @property
    def active_knowledge_snapshot(self) -> str:
        """Return the currently active published knowledge snapshot version."""
        with self._lock:
            return self._active_knowledge_snapshot

    @property
    def staged_events(self) -> tuple[OutboxCloudEvent, ...]:
        """Return an immutable snapshot of events held only in this process."""
        with self._lock:
            return tuple(self._staged)

    def stage_domain_event(
        self,
        *,
        context_name: str,
        event_type: str,
        subject: str,
        data: dict[str, Any],
    ) -> OutboxCloudEvent:
        """Stage a PII-redacted CloudEvents 1.0 event in the process-local reference buffer."""
        with self._lock:
            if len(self._staged) >= self._max_staged_events:
                raise SSRAError(
                    McpErrorCode.UPSTREAM_UNAVAILABLE,
                    "Reference event buffer is full; no staged event was discarded.",
                    status_code=503,
                )
            is_snapshot_event = (
                event_type
                in (
                    "ssra.knowledge.snapshot.published.v1",
                    "ssra.knowledge.snapshot.rolled_back.v1",
                )
                and "active_version" in data
            )
            if is_snapshot_event:
                self._active_knowledge_snapshot = str(data["active_version"])
            evt = OutboxCloudEvent(
                id=new_id("outbox"),
                source=f"urn:ssra:api:{context_name}",
                type=event_type,
                subject=subject,
                time=utc_now(),
                data=_redact_outbox_data(data),
                published_to_nats=False,
            )
            self._staged.append(evt)
            return evt

    def flush_to_jetstream(self) -> int:
        """Fail closed because no NATS JetStream publisher is configured."""
        raise SSRAError(
            McpErrorCode.UPSTREAM_UNAVAILABLE,
            "NATS JetStream publisher is not configured; no events were published or removed from the buffer.",
            status_code=503,
        )


_default_outbox = InMemoryOutboxBuffer()


def get_outbox_store() -> InMemoryOutboxBuffer:
    """Return the process-local reference event buffer."""
    return _default_outbox
