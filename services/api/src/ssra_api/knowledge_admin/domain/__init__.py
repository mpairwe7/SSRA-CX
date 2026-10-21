"""Reference knowledge snapshot state model with maker-checker transition rules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeSnapshotEntity:
    version: str
    status: str  # DRAFT | LEGAL_REVIEW | APPROVED | PUBLISHED | ROLLED_BACK
    approved_by: str
    checksum: str
    created_by: str = "policy_author_default"
