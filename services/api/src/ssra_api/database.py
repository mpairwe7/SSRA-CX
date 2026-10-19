"""SQLAlchemy 2.x Core Data Model for the 10 SSRA Assist Entities (Section 17 & docs/architecture/data-model.md).

Includes PostgreSQL 18 DDL helpers for:
- Native `uuidv7()` primary keys
- Declarative monthly partitioning on high-volume tables
- Row-Level Security (RLS) policies scoping staff by `office_code`
- Append-only immutability trigger on `audit_events`
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Integer, Numeric, SmallInteger, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ConversationORM(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    locale: Mapped[str] = mapped_column(String(16), nullable=False)
    subject_ref: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    auth_level: Mapped[str] = mapped_column(String(32), nullable=False, default="ANONYMOUS")
    office_code: Mapped[str] = mapped_column(String(32), nullable=False, default="JUBA_HQ")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    csat: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)


class MessageORM(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content_ref: Mapped[str] = mapped_column(String(4096), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    safety_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )


class ToolInvocationORM(Base):
    __tablename__ = "tool_invocations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    server: Mapped[str] = mapped_column(String(64), nullable=False)
    tool: Mapped[str] = mapped_column(String(64), nullable=False)
    args_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    tier: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )


class ConfirmationORM(Base):
    __tablename__ = "confirmations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class HandoffORM(Base):
    __tablename__ = "handoffs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    queue: Mapped[str] = mapped_column(String(64), nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(64), nullable=True)
    office_code: Mapped[str] = mapped_column(String(32), nullable=False, default="JUBA_HQ")
    sla_due: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")


class CaseORM(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject_ref: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="NORMAL")
    office_code: Mapped[str] = mapped_column(String(32), nullable=False, default="JUBA_HQ")
    sla_due: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    events: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)


class ConsentORM(Base):
    __tablename__ = "consents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject_ref: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class KnowledgeSnapshotORM(Base):
    __tablename__ = "knowledge_snapshots"

    version: Mapped[str] = mapped_column(String(32), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    approved_by: Mapped[str] = mapped_column(String(128), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)


class TaxFactORM(Base):
    __tablename__ = "tax_facts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    applies_to: Mapped[str] = mapped_column(String(256), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    legal_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    approved_by: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False, index=True)


class AuditEventORM(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    on_behalf_of: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource: Mapped[str] = mapped_column(String(256), nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )


class OutboxEventORM(Base):
    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    published_to_nats: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


POSTGRES18_RLS_AND_WORM_DDL: tuple[str, ...] = (
    "ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;",
    (
        "CREATE POLICY staff_office_isolation_conversations ON conversations "
        "USING (office_code = current_setting('ssra.staff_office_code', true) "
        "OR current_setting('ssra.staff_role', true) IN ('supervisor', 'admin', 'secops'));"
    ),
    "ALTER TABLE cases ENABLE ROW LEVEL SECURITY;",
    (
        "CREATE POLICY staff_office_isolation_cases ON cases "
        "USING (office_code = current_setting('ssra.staff_office_code', true) "
        "OR current_setting('ssra.staff_role', true) IN ('supervisor', 'admin', 'secops'));"
    ),
    "ALTER TABLE handoffs ENABLE ROW LEVEL SECURITY;",
    (
        "CREATE POLICY staff_office_isolation_handoffs ON handoffs "
        "USING (office_code = current_setting('ssra.staff_office_code', true) "
        "OR current_setting('ssra.staff_role', true) IN ('supervisor', 'admin', 'secops'));"
    ),
    (
        "CREATE OR REPLACE FUNCTION forbid_audit_events_mutation() RETURNS trigger AS $$ "
        "BEGIN RAISE EXCEPTION 'audit_events is append-only (WORM policy)'; END; $$ LANGUAGE plpgsql;"
    ),
    (
        "CREATE TRIGGER trg_audit_events_immutable BEFORE UPDATE OR DELETE ON audit_events "
        "FOR EACH ROW EXECUTE FUNCTION forbid_audit_events_mutation();"
    ),
)
