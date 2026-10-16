"""Temporal workflows for 6-step Knowledge Release, Legal Chunking, and Case SLA timers (Sections 7, 10.2, 17)."""

from __future__ import annotations

from dataclasses import dataclass

from ssra_workers.campaigns import (
    CampaignDispatchSummary,
    ReminderCandidate,
    run_consent_checked_filing_reminder_campaign,
)
from ssra_workers.ingestion import LegalChunk, chunk_legal_document_by_structure
from ssra_workers.sla import SLA_HOURS_BY_PRIORITY, CaseSlaEvaluation, evaluate_case_sla


@dataclass(frozen=True)
class KnowledgeReleaseJob:
    snapshot_version: str
    approved_by: str
    eval_gate_passed: bool


def verify_knowledge_release_gate(job: KnowledgeReleaseJob) -> str:
    """Enforce Section 7 Step 5-6: Roll back in one step if the eval gate fails."""
    if not job.eval_gate_passed:
        return f"ROLLED_BACK:{job.snapshot_version}"
    return f"PUBLISHED:{job.snapshot_version}"


__all__ = [
    "SLA_HOURS_BY_PRIORITY",
    "CampaignDispatchSummary",
    "CaseSlaEvaluation",
    "KnowledgeReleaseJob",
    "LegalChunk",
    "ReminderCandidate",
    "chunk_legal_document_by_structure",
    "evaluate_case_sla",
    "run_consent_checked_filing_reminder_campaign",
    "verify_knowledge_release_gate",
]
