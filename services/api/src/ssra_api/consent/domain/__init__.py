"""Domain layer for consent & long-term subject preferences bounded context (Section 6.5 & 17)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ConsentRecord:
    subject_ref: str
    channel: str
    purpose: str
    granted_at: datetime
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class SubjectPreferenceEntity:
    subject_ref: str
    preferred_locale: str
    preferred_channel: str
    low_data_mode: bool
    voice_first_a11y: bool
    updated_at: datetime
