"""Domain layer for cases bounded context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CaseEntity:
    id: str
    subject_ref: str | None
    case_type: str
    status: str
    priority: str
    created_at: datetime
