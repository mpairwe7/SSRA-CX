"""Domain layer for identity_link bounded context (Phase 2 progressive identity, OCR pre-check & Document/Screenshot Analysis)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class SsraDocumentType(StrEnum):
    RECEIPT = "receipt"
    TIN_CARD = "tin_card"
    NATIONAL_ID = "national_id"
    ASSESSMENT = "assessment"
    CUSTOMS_DECLARATION = "customs_declaration"
    FILING_FORM = "filing_form"
    INVOICE = "invoice"
    STATUTORY_ACT = "statutory_act"
    PORTAL_SCREENSHOT = "portal_screenshot"
    GENERIC = "generic"


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


@dataclass(frozen=True)
class DocumentAnalysisResult:
    document_id: str
    filename: str
    kind: str
    size_bytes: int
    doc_type: SsraDocumentType
    confidence: float
    matched_keywords: list[str]
    fields: dict[str, list[str]]
    tax_reconciliation: dict[str, Any]
    screenshot_guidance: dict[str, Any]
    grounding_passage: str
    warnings: list[str] = field(default_factory=list)
