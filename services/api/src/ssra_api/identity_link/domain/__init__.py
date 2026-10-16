"""Domain layer for identity_link bounded context (Phase 2 progressive identity & OCR pre-check)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class IdentityBinding:
    subject_ref: str
    tin_masked: str
    auth_level: str
    sim_swap_checked: bool
    verified_at: datetime


@dataclass(frozen=True)
class DocumentPrecheckResult:
    upload_id: str
    mime_type: str
    malware_scan_status: str
    ocr_legible: bool
    status: str
