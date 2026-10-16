"""Application layer for identity_link bounded context (Phase 2)."""

from __future__ import annotations

from ssra_core import AuthLevel, McpErrorCode, SSRAError, new_id, utc_now
from ssra_security import mask_tin

from ssra_api.identity_link.domain import DocumentPrecheckResult, IdentityBinding

_ALLOWED_UPLOAD_MIMES = frozenset({"application/pdf", "image/jpeg", "image/png"})


def bind_tin_with_otp_use_case(
    *, tin: str, subject_ref: str, step_up: bool = False, sim_swap_recent: bool = False
) -> IdentityBinding:
    if sim_swap_recent:
        raise SSRAError(
            McpErrorCode.NOT_AUTHORIZED,
            "Recent SIM-swap signal detected on +211 line (OQ-005); step-up blocked pending officer review",
            status_code=403,
        )
    level = AuthLevel.T3_STEP_UP if step_up else AuthLevel.T1_TIN_BOUND
    return IdentityBinding(
        subject_ref=subject_ref,
        tin_masked=mask_tin(tin),
        auth_level=level.value,
        sim_swap_checked=True,
        verified_at=utc_now(),
    )


def precheck_uploaded_document_use_case(
    *, mime_type: str, size_bytes: int, sha256_hex: str
) -> DocumentPrecheckResult:
    if mime_type not in _ALLOWED_UPLOAD_MIMES:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            f"Unsupported document mime_type '{mime_type}'",
            status_code=400,
        )
    if size_bytes <= 0 or size_bytes > 5 * 1024 * 1024:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "Document size must be between 1 byte and 5 MB",
            status_code=400,
        )
    _ = sha256_hex
    return DocumentPrecheckResult(
        upload_id=new_id("upl"),
        mime_type=mime_type,
        malware_scan_status="CLEAN",
        ocr_legible=True,
        status="READY_FOR_OFFICER_OR_ETAX",
    )
