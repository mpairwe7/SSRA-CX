"""API router for identity_link bounded context (Phase 2 OTP, Step-Up, SIM-swap, OCR Pre-Check & Document/Screenshot Analysis)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from ssra_api.identity_link.application import (
    analyze_uploaded_document_use_case,
    bind_tin_with_otp_use_case,
    precheck_uploaded_document_use_case,
)

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


@router.post("/verify-otp", response_model=VerifyOtpResponse)
async def verify_otp(body: VerifyOtpRequest) -> VerifyOtpResponse:
    """Verify TIN, 6-digit OTP, and SIM-swap signal to bind an opaque `subject_ref`."""
    subject_ref = "sub_taxpayer_deng_02" if body.tin.endswith("5678") else "sub_taxpayer_amina_01"
    binding = bind_tin_with_otp_use_case(
        tin=body.tin,
        subject_ref=subject_ref,
        otp_code=body.otp_code,
        step_up=body.step_up,
        sim_swap_recent=body.sim_swap_recent,
    )
    return VerifyOtpResponse(
        subject_ref=binding.subject_ref,
        tin_masked=binding.tin_masked,
        auth_level=binding.auth_level,
        sim_swap_checked=binding.sim_swap_checked,
    )


@router.post("/document-precheck", response_model=DocumentPrecheckResponse)
async def document_precheck(body: DocumentPrecheckRequest) -> DocumentPrecheckResponse:
    res = precheck_uploaded_document_use_case(
        mime_type=body.mime_type,
        size_bytes=body.size_bytes,
        sha256_hex=body.sha256_hex,
    )
    return DocumentPrecheckResponse(
        upload_id=res.upload_id,
        mime_type=res.mime_type,
        malware_scan_status=res.malware_scan_status,
        ocr_legible=res.ocr_legible,
        status=res.status,
    )


@router.post("/documents/analyze", response_model=AnalyzeDocumentResponse)
async def analyze_document(body: AnalyzeDocumentRequest) -> AnalyzeDocumentResponse:
    res = analyze_uploaded_document_use_case(
        filename=body.filename,
        text_content=body.text_content,
        size_bytes=body.size_bytes,
        kind=body.kind,
    )
    return AnalyzeDocumentResponse(
        document_id=res.document_id,
        filename=res.filename,
        kind=res.kind,
        size_bytes=res.size_bytes,
        doc_type=res.doc_type.value,
        confidence=res.confidence,
        matched_keywords=res.matched_keywords,
        fields=res.fields,
        tax_reconciliation=res.tax_reconciliation,
        screenshot_guidance=res.screenshot_guidance,
        grounding_passage=res.grounding_passage,
        warnings=res.warnings,
    )
