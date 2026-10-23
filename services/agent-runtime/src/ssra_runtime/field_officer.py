"""Phase 4 Field-Officer Assist Mode (`services/agent-runtime/src/ssra_runtime/field_officer.py` — Section 3 & 12.3).

Enables authenticated SSRA domestic-tax and border customs officers (`AuthLevel.STAFF_PASSKEY`)
to run cited tariff lookups, verify TCC/receipt authenticity, and generate on-the-spot
taxpayer compliance checklists while enforcing strict staff RBAC and audit logging.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from ssra_core import AuthLevel, LocaleCode, McpErrorCode, SSRAError
from ssra_security import HashChainedAuditLedger

from ssra_runtime.tools import GovernedMcpGatewayClient


class FieldOfficerAssistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    officer_id: str = Field(min_length=3)
    office_code: str = "NIMULE_CUSTOMS"
    auth_level: AuthLevel = AuthLevel.STAFF_PASSKEY
    task_type: str  # TARIFF_CHECK | VERIFY_CHANNEL | PAYE_CHECKLIST
    hs_code: str | None = None
    cif_value_usd: str | None = None
    candidate_channel: str | None = None
    locale: LocaleCode = LocaleCode.EN


class FieldOfficerAssistResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    officer_id: str
    office_code: str
    task_type: str
    cited_guidance: str
    legal_ref: str
    official_portal: str = "https://etax.nra.gov.ss/"
    audit_event_hash: str


_ALLOWED_FIELD_OFFICER_TASKS = frozenset(
    {"TARIFF_CHECK", "VERIFY_CHANNEL", "PAYE_CHECKLIST", "COMPLIANCE_CHECKLIST"}
)


def execute_field_officer_assist(
    req: FieldOfficerAssistRequest,
    *,
    gateway: GovernedMcpGatewayClient,
    audit_ledger: HashChainedAuditLedger,
) -> FieldOfficerAssistResponse:
    if req.auth_level != AuthLevel.STAFF_PASSKEY:
        raise SSRAError(
            McpErrorCode.NOT_AUTHORIZED,
            "Field-Officer Assist requires STAFF_PASSKEY authentication (WebAuthn passkey)",
            status_code=403,
        )
    if req.task_type not in _ALLOWED_FIELD_OFFICER_TASKS:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            f"Unsupported Field-Officer task_type '{req.task_type}'; must be one of {sorted(_ALLOWED_FIELD_OFFICER_TASKS)}",
            status_code=400,
        )

    if req.task_type == "TARIFF_CHECK":
        hs = req.hs_code or "8703.23"
        cif = req.cif_value_usd or "10000"
        tariff_art = gateway.invoke_tool(
            server_name="customs",
            tool_name="lookup_tariff",
            arguments={"hs_code": hs},
            auth_level=req.auth_level,
            subject_ref=req.officer_id,
        )
        art = gateway.invoke_tool(
            server_name="customs",
            tool_name="estimate_duties",
            arguments={"hs_code": hs, "cif_value_usd": cif},
            auth_level=req.auth_level,
            subject_ref=req.officer_id,
        )
        sc = art.structured_content
        excise_pct = tariff_art.structured_content.get("excise_rate_percent", "0")
        guidance = (
            f"HS {sc['hs_code']} (CIF {sc['cif_value_usd']} USD @ official BoSS rate "
            f"{sc['boss_official_fx_rate_ssp_per_usd']} SSP/USD = {sc['customs_value_ssp']} SSP): "
            f"Duty rate {sc['duty_rate_percent']}%, excise rate {excise_pct}%, estimated duty {sc['estimated_duty_ssp']} SSP. "
            f"Collect strictly via e-Tax bank remittance (March 2026 cash-free directive)."
        )
        legal_ref = "Customs Service Act 2013 & Financial Act 2024/2025 Tariff Schedule"
    elif req.task_type == "VERIFY_CHANNEL":
        cand = req.candidate_channel or "https://etax.nra.gov.ss/"
        art = gateway.invoke_tool(
            server_name="official-channels",
            tool_name="verify_payment_account",
            arguments={"account_or_portal": cand},
            auth_level=req.auth_level,
            subject_ref=req.officer_id,
        )
        sc = art.structured_content
        guidance = f"{sc['status']}: {sc['guidance']}"
        legal_ref = "SSRA March 2026 Cash-Free Bank Collection Directive"
    else:
        guidance = (
            "Field Compliance Checklist: (1) Verify active TIN certificate from https://etax.nra.gov.ss/; "
            "(2) Verify valid electronic TCC on e-Tax (manual paper TCCs are invalid); "
            "(3) Instruct taxpayer to remit all taxes into designated TSA banks via e-Tax."
        )
        legal_ref = "SSRA Act 2016 (as amended 2023) & Taxation Act 2009"

    aud = audit_ledger.append(
        actor=req.officer_id,
        action=f"field_officer.assist.{req.task_type.lower()}",
        resource=f"office://{req.office_code}",
        payload={"task_type": req.task_type, "hs_code": req.hs_code},
    )
    return FieldOfficerAssistResponse(
        officer_id=req.officer_id,
        office_code=req.office_code,
        task_type=req.task_type,
        cited_guidance=guidance,
        legal_ref=legal_ref,
        audit_event_hash=aud.hash,
    )
