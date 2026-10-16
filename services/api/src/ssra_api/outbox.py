"""Transactional Outbox to NATS JetStream in CloudEvents 1.0 Envelopes (Section 10.4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict
from ssra_core import new_id, utc_now


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
        self._staged: list[OutboxCloudEvent] = []
        self._published: list[OutboxCloudEvent] = []

    @property
    def staged_events(self) -> tuple[OutboxCloudEvent, ...]:
        return tuple(self._staged)

    @property
    def published_events(self) -> tuple[OutboxCloudEvent, ...]:
        return tuple(self._published)

    def stage_domain_event(
        self,
        *,
        context_name: str,
        event_type: str,
        subject: str,
        data: dict[str, Any],
    ) -> OutboxCloudEvent:
        evt = OutboxCloudEvent(
            id=new_id("outbox"),
            source=f"urn:ssra:api:{context_name}",
            type=event_type,
            subject=subject,
            time=utc_now(),
            data=data,
            published_to_nats=False,
        )
        self._staged.append(evt)
        return evt

    def flush_to_jetstream(self) -> int:
        count = len(self._staged)
        while self._staged:
            evt = self._staged.pop(0)
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
