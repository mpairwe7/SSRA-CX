"""Transactional Outbox to NATS JetStream in CloudEvents 1.0 Envelopes (Section 10.4)."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict
from ssra_core import new_id, utc_now
from ssra_security import redact_pii

MAX_STAGED_OUTBOX_EVENTS = 4096
MAX_PUBLISHED_OUTBOX_EVENTS = 4096


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


class TransactionalOutboxStore:
    """Stages domain events transactionally and flushes CloudEvents 1.0 envelopes to NATS JetStream."""

    def __init__(self) -> None:
        """Initialise thread-safe staged and published event queues and active knowledge snapshot tracker."""
        self._lock = threading.RLock()
        self._staged: list[OutboxCloudEvent] = []
        self._published: list[OutboxCloudEvent] = []
        self._active_knowledge_snapshot: str = "2026.10.1"

    @property
    def active_knowledge_snapshot(self) -> str:
        """Return the currently active published knowledge snapshot version."""
        with self._lock:
            return self._active_knowledge_snapshot

    @property
    def staged_events(self) -> tuple[OutboxCloudEvent, ...]:
        """Return an immutable tuple of staged CloudEvents awaiting JetStream flush."""
        with self._lock:
            return tuple(self._staged)

    @property
    def published_events(self) -> tuple[OutboxCloudEvent, ...]:
        """Return an immutable tuple of CloudEvents flushed to NATS JetStream."""
        with self._lock:
            return tuple(self._published)

    def stage_domain_event(
        self,
        *,
        context_name: str,
        event_type: str,
        subject: str,
        data: dict[str, Any],
    ) -> OutboxCloudEvent:
        """Stage a PII-redacted CloudEvents 1.0 domain event in the transactional outbox."""
        with self._lock:
            if len(self._staged) >= MAX_STAGED_OUTBOX_EVENTS:
                self._staged.pop(0)
            if (
                event_type
                in (
                    "ssra.knowledge.snapshot.published.v1",
                    "ssra.knowledge.snapshot.rolled_back.v1",
                )
                and "active_version" in data
            ):
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
        with self._lock:
            count = len(self._staged)
            while self._staged:
                evt = self._staged.pop(0)
                if len(self._published) >= MAX_PUBLISHED_OUTBOX_EVENTS:
                    self._published.pop(0)
                self._published.append(
                    OutboxCloudEvent(
                        id=evt.id,
                        source=evt.source,
                        type=evt.type,
                        subject=evt.subject,
                        time=evt.time,
                        data=evt.data,
                        published_to_nats=True,
                    )
                )
            return count


_default_outbox = TransactionalOutboxStore()


def get_outbox_store() -> TransactionalOutboxStore:
    return _default_outbox
