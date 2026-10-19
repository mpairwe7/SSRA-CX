"""SIEM Export (OCSF & CEF) and Inter-Model Output Validation (Sections 8.2 & 12.3).

Implements:
1. `format_audit_event_as_cef` and `format_audit_event_as_ocsf` for exporting gateway,
   MCP server, and runtime security events to SSRA SecOps SIEM with Presidio PII redaction.
2. `validate_inter_model_handoff` ("validate outputs wherever one model's output feeds another"
   — Section 8.2), blocking instruction-injection tokens between `understand` and `compose`.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict
from ssra_core import Intent, McpErrorCode, SSRAError

from ssra_security.audit import AuditEvent
from ssra_security.redaction import redact_pii

SiemSeverity = Literal["SEV-1", "SEV-2", "SEV-3", "SEV-4"]

_INTER_MODEL_INJECTION_RE = re.compile(
    r"(<\|im_start\|>|<\|endoftext\|>|\[INST\]|</untrusted_|ignore\s+previous\s+instructions)",
    flags=re.IGNORECASE,
)


class OcsfSecurityEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    class_uid: int = 3001  # Account / Access Activity
    category_uid: int = 3  # Identity & Access Management / Audit
    severity: SiemSeverity
    time: str
    actor_id: str
    on_behalf_of_masked: str | None
    action: str
    resource: str
    digest: str
    chain_hash: str


def _escape_cef_header(val: str) -> str:
    """Escape CEF header fields per OWASP ASVS 5.0 V16.4.1 to prevent SIEM log/delimiter injection."""
    return (
        val.replace("\x00", "")
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("\\", "\\\\")
        .replace("|", "\\|")
    )


def _escape_cef_extension(val: str) -> str:
    """Escape CEF extension key-value fields (`=`, `\\`, CR/LF) per ArcSight CEF & ASVS V16.4.1."""
    return (
        val.replace("\x00", "")
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("\\", "\\\\")
        .replace("=", "\\=")
    )


def classify_siem_severity(action: str, safety_flags: list[str] | None = None) -> SiemSeverity:
    """Classify SIEM event severity (SEV-1..SEV-4) from audit action and guardrail safety flags."""
    flags = safety_flags or []
    if any("CROSS_SUBJECT" in f or "PII_GUARD_FAILED" in f or "GOAL_HIJACK" in f for f in flags):
        return "SEV-1"
    if any("NUMERIC_PROVENANCE_FAILED" in f or "PROMPT_INJECTION" in f for f in flags):
        return "SEV-2"
    if "kill_switch" in action or "rollback" in action:
        return "SEV-2"
    return "SEV-4"


def format_audit_event_as_ocsf(
    event: AuditEvent, *, safety_flags: list[str] | None = None
) -> OcsfSecurityEvent:
    """Format an AuditEvent into an OCSF v1.3 Account/Access Activity security event with PII redaction."""
    severity = classify_siem_severity(event.action, safety_flags)
    masked_sub = (
        _escape_cef_extension(redact_pii(event.on_behalf_of).redacted_text)
        if event.on_behalf_of
        else None
    )
    return OcsfSecurityEvent(
        severity=severity,
        time=event.at.isoformat(),
        actor_id=_escape_cef_extension(event.actor),
        on_behalf_of_masked=masked_sub,
        action=_escape_cef_header(event.action),
        resource=_escape_cef_extension(event.resource),
        digest=event.digest,
        chain_hash=event.hash,
    )


def format_audit_event_as_cef(event: AuditEvent, *, safety_flags: list[str] | None = None) -> str:
    """Format an AuditEvent as a log-injection-safe Common Event Format (CEF) SIEM record."""
    ocsf = format_audit_event_as_ocsf(event, safety_flags=safety_flags)
    sev_num = {"SEV-1": 10, "SEV-2": 8, "SEV-3": 5, "SEV-4": 3}[ocsf.severity]
    return (
        f"CEF:0|SSRA|SSRAAssist|2026.10.1|{_escape_cef_header(ocsf.action)}|"
        f"{_escape_cef_header(ocsf.action)}|{sev_num}|"
        f"act={_escape_cef_extension(ocsf.actor_id)} "
        f"suser={_escape_cef_extension(ocsf.on_behalf_of_masked or 'anonymous')} "
        f"cs1={_escape_cef_extension(ocsf.resource)} cs2={ocsf.chain_hash}"
    )


def validate_inter_model_handoff(intent: Intent) -> Intent:
    """Section 8.2: Validate outputs wherever one model's output (`understand`) feeds another (`compose`)."""
    sanitised_slots: dict[str, str | int | float | bool] = {}
    for k, v in intent.slots.items():
        if isinstance(v, str):
            if _INTER_MODEL_INJECTION_RE.search(v):
                raise SSRAError(
                    McpErrorCode.VALIDATION_FAILED,
                    f"Inter-model handoff blocked injection token in slot '{k}'",
                    status_code=400,
                )
            sanitised_slots[k] = redact_pii(v).redacted_text[:256]
        else:
            sanitised_slots[k] = v
    return intent.model_copy(update={"slots": sanitised_slots})
