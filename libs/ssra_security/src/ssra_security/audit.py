"""Append-only, hash-chained AuditEvent log (Sections 12.3 & 17)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict
from ssra_core import new_id, utc_now

GENESIS_HASH = "0" * 64


def _sanitise_audit_field(raw: str) -> str:
    """Escape pipe delimiters and strip CR/LF/NUL control characters to prevent hash-chain delimiter collisions."""
    return (
        raw.replace("\x00", "")
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("\\", "\\\\")
        .replace("|", "\\|")
    )


def compute_canonical_digest(payload: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hex digest of any JSON-serialisable dict."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(canonical).hexdigest()


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    actor: str
    on_behalf_of: str | None
    action: str
    resource: str
    digest: str
    prev_hash: str
    hash: str
    at: datetime


def compute_audit_event_hash(
    *,
    prev_hash: str,
    event_id: str,
    actor: str,
    on_behalf_of: str | None,
    action: str,
    resource: str,
    digest: str,
    at_iso: str,
) -> str:
    """Compute the SHA-256 hash chain link over canonicalized, delimiter-escaped audit event fields."""
    material = "|".join(
        [
            _sanitise_audit_field(prev_hash),
            _sanitise_audit_field(event_id),
            _sanitise_audit_field(actor),
            _sanitise_audit_field(on_behalf_of or ""),
            _sanitise_audit_field(action),
            _sanitise_audit_field(resource),
            _sanitise_audit_field(digest),
            _sanitise_audit_field(at_iso),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class HashChainedAuditLedger:
    """Append-only, hash-chained audit ledger with cryptographic integrity verification."""

    def __init__(self) -> None:
        """Initialise an empty append-only hash-chained audit ledger."""
        self._events: list[AuditEvent] = []

    @property
    def events(self) -> tuple[AuditEvent, ...]:
        """Return an immutable tuple of recorded audit events."""
        return tuple(self._events)

    def replace_event_for_testing(self, index: int, event: AuditEvent) -> None:
        """Replace an event at index strictly for tamper-detection unit tests."""
        self._events[index] = event

    def restore_events(self, events: list[AuditEvent]) -> None:
        """Restore a list of audit events during DR restore drills."""
        self._events = list(events)

    def append(
        self,
        *,
        actor: str,
        action: str,
        resource: str,
        payload: dict[str, Any],
        on_behalf_of: str | None = None,
        at: datetime | None = None,
    ) -> AuditEvent:
        """Append a new cryptographically hash-chained AuditEvent to the ledger."""
        prev_hash = self._events[-1].hash if self._events else GENESIS_HASH
        event_id = new_id("aud")
        timestamp = at or utc_now()
        digest = compute_canonical_digest(payload)
        safe_actor = _sanitise_audit_field(actor)
        safe_obo = _sanitise_audit_field(on_behalf_of) if on_behalf_of is not None else None
        safe_action = _sanitise_audit_field(action)
        safe_resource = _sanitise_audit_field(resource)
        event_hash = compute_audit_event_hash(
            prev_hash=prev_hash,
            event_id=event_id,
            actor=safe_actor,
            on_behalf_of=safe_obo,
            action=safe_action,
            resource=safe_resource,
            digest=digest,
            at_iso=timestamp.isoformat(),
        )
        event = AuditEvent(
            id=event_id,
            actor=safe_actor,
            on_behalf_of=safe_obo,
            action=safe_action,
            resource=safe_resource,
            digest=digest,
            prev_hash=prev_hash,
            hash=event_hash,
            at=timestamp,
        )
        self._events.append(event)
        return event

    def verify_integrity(self) -> bool:
        """Verify the unbroken SHA-256 hash chain from GENESIS_HASH through the latest event."""
        expected_prev = GENESIS_HASH
        for ev in self._events:
            if ev.prev_hash != expected_prev:
                return False
            recomputed = compute_audit_event_hash(
                prev_hash=ev.prev_hash,
                event_id=ev.id,
                actor=ev.actor,
                on_behalf_of=ev.on_behalf_of,
                action=ev.action,
                resource=ev.resource,
                digest=ev.digest,
                at_iso=ev.at.isoformat(),
            )
            if ev.hash != recomputed:
                return False
            expected_prev = ev.hash
        return True
