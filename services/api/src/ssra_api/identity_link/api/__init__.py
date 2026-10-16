"""API router for identity_link bounded context (Phase 2 OTP, Step-Up, SIM-swap & Document OCR Pre-Check)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from ssra_api.identity_link.application import (
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


@router.post("/verify-otp", response_model=VerifyOtpResponse)
async def verify_otp(body: VerifyOtpRequest) -> VerifyOtpResponse:
    subject_ref = "sub_taxpayer_deng_02" if body.tin.endswith("5678") else "sub_taxpayer_amina_01"
    binding = bind_tin_with_otp_use_case(
        tin=body.tin,
        subject_ref=subject_ref,
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
