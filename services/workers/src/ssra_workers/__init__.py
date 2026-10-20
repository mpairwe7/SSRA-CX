"""Temporal workflows for 6-step Knowledge Release, Legal Chunking, Case SLA timers, and Goal Continuation (Sections 7, 10.2, 17)."""

from __future__ import annotations

from dataclasses import dataclass

from ssra_workers.campaigns import (
    CampaignDispatchSummary,
    ReminderCandidate,
    run_consent_checked_filing_reminder_campaign,
)
from ssra_workers.continuation import (
    APPROVED_CONTINUATION_TEMPLATES,
    GoalContinuationCandidate,
    GoalContinuationDispatchSummary,
    build_continuation_message,
    run_post_interaction_goal_continuation,
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


def get_worker_health_status() -> dict[str, object]:
    """Health & readiness probe for SSRA Temporal background workers."""
    return {
        "status": "ok",
        "service": "ssra-workers",
        "task_queues": [
            "knowledge_release",
            "case_sla_timers",
            "reminder_campaigns",
            "goal_continuation",
        ],
        "sla_priorities": sorted(SLA_HOURS_BY_PRIORITY),
    }


__all__ = [
    "APPROVED_CONTINUATION_TEMPLATES",
    "SLA_HOURS_BY_PRIORITY",
    "CampaignDispatchSummary",
    "CaseSlaEvaluation",
    "GoalContinuationCandidate",
    "GoalContinuationDispatchSummary",
    "KnowledgeReleaseJob",
    "LegalChunk",
    "ReminderCandidate",
    "build_continuation_message",
    "chunk_legal_document_by_structure",
    "evaluate_case_sla",
    "get_worker_health_status",
    "run_consent_checked_filing_reminder_campaign",
    "run_post_interaction_goal_continuation",
    "verify_knowledge_release_gate",
]
