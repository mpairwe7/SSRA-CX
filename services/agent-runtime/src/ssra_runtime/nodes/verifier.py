"""Stage 9: Post-Tool Outcome Verification Loop (October 2026 Agentic CX).

Verifies after specialist subgraph & MCP tool execution that:
1. Every executed `ToolArtifact` carries deterministic provenance (`record_id`, `as_of`, or `snapshot_version`).
2. Multi-step plan post-conditions hold and any domain blockers (e.g., overdue balance blocking TCC issuance,
   overdue filing status, or secondary step failures) are explicitly surfaced for grounded composition.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, Field
from ssra_core import Plan

from ssra_runtime.schemas import ToolArtifact


class OutcomeVerificationResult(BaseModel):
    """Structured result of Stage 9 post-tool outcome verification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verified: bool
    planned_step_count: int
    completed_artifact_count: int
    provenance_complete: bool
    blocker_codes: list[str] = Field(default_factory=list)
    remediation_notes: list[str] = Field(default_factory=list)


def _parse_decimal_safe(val: object) -> Decimal:
    """Parse a string/number into a `Decimal` safely, returning `Decimal('0')` on malformed values."""
    try:
        return Decimal(str(val).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return Decimal("0")


def verify_plan_outcomes(
    plan: Plan | None,
    artifacts: list[ToolArtifact],
    *,
    failed_steps: list[str] | None = None,
) -> OutcomeVerificationResult:
    """Verify tool artifact provenance and cross-step statutory post-conditions."""
    planned_count = len(plan.steps) if plan is not None else 1
    blockers: list[str] = [f"STEP_FAILED:{s}" for s in (failed_steps or [])]
    if not artifacts:
        return OutcomeVerificationResult(
            verified=(len(blockers) == 0),
            planned_step_count=planned_count,
            completed_artifact_count=0,
            provenance_complete=True,
            blocker_codes=blockers,
            remediation_notes=[],
        )

    provenance_ok = True
    notes: list[str] = []

    has_tcc_step = any(a.tool == "get_tcc_status" for a in artifacts) or (
        plan is not None and "tcc.get_tcc_status" in plan.steps
    )

    for art in artifacts:
        sc = art.structured_content
        has_prov = bool(
            sc.get("record_id")
            or sc.get("as_of")
            or sc.get("snapshot_version")
            or art.provenance.get("snapshot_version")
            or art.provenance.get("source_id")
        )
        if not has_prov:
            provenance_ok = False
            blockers.append(f"MISSING_PROVENANCE:{art.server}.{art.tool}")

        if art.tool == "get_balance":
            outstanding = _parse_decimal_safe(sc.get("total_outstanding_ssp", "0"))
            if outstanding > Decimal("0") and has_tcc_step:
                blockers.append("OVERDUE_BALANCE_REQUIRES_SETTLEMENT")
                notes.append(
                    "TCC issuance on https://etax.nra.gov.ss/ requires settling or reconciling "
                    "outstanding e-Tax balances via designated commercial banks."
                )

        if art.tool == "get_filing_status":
            f_status = str(sc.get("filing_status", "")).upper()
            if f_status in ("OVERDUE", "DELINQUENT", "UNFILED"):
                blockers.append("FILING_STATUS_NOT_CURRENT")
                notes.append(
                    "Pending tax returns must be filed electronically on https://etax.nra.gov.ss/."
                )

        if art.tool == "get_declaration_status":
            d_status = str(sc.get("status", "")).upper()
            duty_ssp = _parse_decimal_safe(sc.get("assessed_duty_ssp", "0"))
            if ("PENDING_PAYMENT" in d_status or "AWAITING" in d_status) and duty_ssp > Decimal(
                "0"
            ):
                blockers.append("CUSTOMS_DUTY_PENDING_SETTLEMENT")
                notes.append(
                    "Customs declaration release requires settling assessed duties via "
                    "https://etax.nra.gov.ss/ into designated commercial banks."
                )

    return OutcomeVerificationResult(
        verified=provenance_ok and not failed_steps,
        planned_step_count=planned_count,
        completed_artifact_count=len(artifacts),
        provenance_complete=provenance_ok,
        blocker_codes=list(dict.fromkeys(blockers)),
        remediation_notes=list(dict.fromkeys(notes)),
    )
