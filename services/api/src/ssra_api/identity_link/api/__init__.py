"""API router for identity_link bounded context (Phase 2 OTP, Step-Up, SIM-swap, OCR Pre-Check & Document/Screenshot Analysis)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from ssra_core import McpErrorCode, SSRAError

router = APIRouter(prefix="/v1/identity-link", tags=["identity_link"])


class VerifyOtpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tin: str
    otp_code: str
    step_up: bool = False
    sim_swap_recent: bool = False


class VerifyOtpResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_ref: str
    tin_masked: str
    auth_level: str
    sim_swap_checked: bool


class DocumentPrecheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mime_type: str
    size_bytes: int
    sha256_hex: str


class DocumentPrecheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_id: str
    mime_type: str
    malware_scan_status: str
    ocr_legible: bool
    status: str


class AnalyzeDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str
    text_content: str
    size_bytes: int
    kind: str = "pdf"


class AnalyzeDocumentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    filename: str
    kind: str
    size_bytes: int
    doc_type: str
    confidence: float
    matched_keywords: list[str]
    fields: dict[str, list[str]]
    tax_reconciliation: dict[str, Any]
    screenshot_guidance: dict[str, Any]
    grounding_passage: str
    warnings: list[str]


@router.post(
    "/verify-otp",
    response_model=VerifyOtpResponse,
    responses={503: {"description": "Approved identity and OTP providers are not configured."}},
)
async def verify_otp(body: VerifyOtpRequest) -> VerifyOtpResponse:
    """Fail closed until an approved identity directory, OTP, and SIM-swap adapter is wired."""
    del body
    raise SSRAError(
        McpErrorCode.UPSTREAM_UNAVAILABLE,
        "Identity verification is unavailable until SSRA approves and configures the identity, OTP, and SIM-swap providers (OQ-005).",
        status_code=503,
    )


@router.post(
    "/document-precheck",
    response_model=DocumentPrecheckResponse,
    responses={503: {"description": "Malware scanning and OCR providers are not configured."}},
)
async def document_precheck(body: DocumentPrecheckRequest) -> DocumentPrecheckResponse:
    """Fail closed rather than report a clean scan without a real scanner and OCR provider."""
    del body
    raise SSRAError(
        McpErrorCode.UPSTREAM_UNAVAILABLE,
        "Document precheck is unavailable until approved malware scanning and OCR providers are configured (OQ-017).",
        status_code=503,
    )


@router.post(
    "/documents/analyze",
    response_model=AnalyzeDocumentResponse,
    responses={503: {"description": "Approved OCR and legal guidance sources are not configured."}},
)
async def analyze_document(body: AnalyzeDocumentRequest) -> AnalyzeDocumentResponse:
    """Fail closed until OCR provenance and approved legal guidance are available."""
    del body
    raise SSRAError(
        McpErrorCode.UPSTREAM_UNAVAILABLE,
        "Document analysis is unavailable until OCR provenance, approved legal sources, and numeric validation are configured (OQ-017).",
        status_code=503,
    )
