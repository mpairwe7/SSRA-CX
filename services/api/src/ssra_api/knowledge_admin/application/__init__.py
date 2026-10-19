"""Application layer for knowledge_admin bounded context (6-Step Knowledge Release Workflow — Section 7)."""

from __future__ import annotations

import hashlib
from dataclasses import replace

from ssra_core import McpErrorCode, SSRAError

from ssra_api.knowledge_admin.domain import KnowledgeSnapshotEntity
from ssra_api.outbox import get_outbox_store


class KnowledgeReleaseWorkflowEngine:
    """Implements Draft -> Legal Review -> Approval -> Publish (with Eval Gate) -> 1-Step Rollback."""

    def __init__(self) -> None:
        self._snapshots: dict[str, KnowledgeSnapshotEntity] = {
            "2026.10.1": KnowledgeSnapshotEntity(
                version="2026.10.1",
                status="PUBLISHED",
                approved_by="SSRA Legal Directorate",
                checksum="7760efe3102ce836d6a6c73c7399d837d752fd1d791be07a1780f1241ef09f34",
            )
        }
        self._active_version: str = "2026.10.1"
        self._previous_published_version: str = "2026.10.1"

    def get_active(self) -> KnowledgeSnapshotEntity:
        return self._snapshots[self._active_version]

    def create_draft(
        self,
        *,
        version: str,
        content_digest_input: str,
        created_by: str = "policy_author_default",
    ) -> KnowledgeSnapshotEntity:
        checksum = hashlib.sha256(content_digest_input.encode("utf-8")).hexdigest()
        snap = KnowledgeSnapshotEntity(
            version=version,
            status="DRAFT",
            approved_by="PENDING_LEGAL_REVIEW",
            checksum=checksum,
            created_by=created_by,
        )
        self._snapshots[version] = snap
        return snap

    def submit_for_legal_review(self, version: str) -> KnowledgeSnapshotEntity:
        snap = self._get_or_404(version)
        if snap.status != "DRAFT":
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                f"Snapshot {version} must be in DRAFT state to submit for legal review",
                status_code=400,
            )
        updated = replace(snap, status="LEGAL_REVIEW")
        self._snapshots[version] = updated
        return updated

    def approve_snapshot(self, version: str, *, legal_approver: str) -> KnowledgeSnapshotEntity:
        """Approve a LEGAL_REVIEW snapshot by an independent legal approver (maker-checker)."""
        snap = self._get_or_404(version)
        if snap.status != "LEGAL_REVIEW":
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                f"Snapshot {version} must be in LEGAL_REVIEW state before approval",
                status_code=400,
            )
        if legal_approver.strip() == snap.created_by.strip():
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "Maker-checker violation: legal_approver must differ from draft author (created_by)",
                status_code=403,
            )
        updated = replace(snap, status="APPROVED", approved_by=legal_approver)
        self._snapshots[version] = updated
        get_outbox_store().stage_domain_event(
            context_name="knowledge_admin",
            event_type="ssra.knowledge.snapshot.approved.v1",
            subject=version,
            data={"version": version, "approved_by": legal_approver, "checksum": snap.checksum},
        )
        return updated

    def publish_snapshot(
        self, version: str, *, eval_regression_passed: bool
    ) -> KnowledgeSnapshotEntity:
        """Publish an APPROVED snapshot after verifying the evaluation regression gate."""
        snap = self._get_or_404(version)
        if snap.status != "APPROVED":
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                f"Snapshot {version} must be APPROVED by SSRA Legal before publish",
                status_code=400,
            )
        if not eval_regression_passed:
            # Step 6 automatic rollback on eval gate failure (Section 7)
            rolled = replace(snap, status="ROLLED_BACK")
            self._snapshots[version] = rolled
            get_outbox_store().stage_domain_event(
                context_name="knowledge_admin",
                event_type="ssra.knowledge.snapshot.eval_failed_rollback.v1",
                subject=version,
                data={"version": version, "active_version": self._active_version},
            )
            return rolled

        self._previous_published_version = self._active_version
        published = replace(snap, status="PUBLISHED")
        self._snapshots[version] = published
        self._active_version = version
        get_outbox_store().stage_domain_event(
            context_name="knowledge_admin",
            event_type="ssra.knowledge.snapshot.published.v1",
            subject=version,
            data={"version": version, "active_version": version, "checksum": published.checksum},
        )
        return published

    def rollback_to_previous(self) -> KnowledgeSnapshotEntity:
        """Perform a 1-step rollback to the previous published knowledge snapshot."""
        current = self._snapshots[self._active_version]
        self._snapshots[self._active_version] = replace(current, status="ROLLED_BACK")
        self._active_version = self._previous_published_version
        get_outbox_store().stage_domain_event(
            context_name="knowledge_admin",
            event_type="ssra.knowledge.snapshot.rolled_back.v1",
            subject=self._active_version,
            data={
                "rolled_back_version": current.version,
                "active_version": self._active_version,
            },
        )
        return self._snapshots[self._active_version]

    def _get_or_404(self, version: str) -> KnowledgeSnapshotEntity:
        snap = self._snapshots.get(version)
        if snap is None:
            raise SSRAError(
                McpErrorCode.NOT_FOUND, f"Snapshot '{version}' not found", status_code=404
            )
        return snap


_engine = KnowledgeReleaseWorkflowEngine()


def get_workflow_engine() -> KnowledgeReleaseWorkflowEngine:
    return _engine


def get_active_snapshot_use_case() -> KnowledgeSnapshotEntity:
    return _engine.get_active()
