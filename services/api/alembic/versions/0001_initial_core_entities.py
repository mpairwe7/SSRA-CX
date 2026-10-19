"""Initial PostgreSQL 18 + pgvector 0.8+ migration for SSRA Assist's 10 core entities (Section 17).

Revision ID: 0001_initial_core_entities
Revises: None
Create Date: 2026-10-16
"""

from __future__ import annotations

revision: str = "0001_initial_core_entities"
down_revision: str | None = None
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None

UPGRADE_SQL: tuple[str, ...] = (
    "CREATE EXTENSION IF NOT EXISTS vector;",
    "CREATE EXTENSION IF NOT EXISTS pg_trgm;",
    # 1. conversations (Partitioned monthly by started_at, UUIDv7 default)
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id VARCHAR(64) NOT NULL DEFAULT ('conv_' || uuidv7()::text),
        channel VARCHAR(32) NOT NULL,
        locale VARCHAR(16) NOT NULL,
        subject_ref VARCHAR(64),
        auth_level VARCHAR(32) NOT NULL DEFAULT 'ANONYMOUS',
        office_code VARCHAR(32) NOT NULL DEFAULT 'JUBA_HQ',
        started_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
        status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
        csat SMALLINT,
        PRIMARY KEY (id, started_at)
    ) PARTITION BY RANGE (started_at);
    """,
    # 2. messages (Partitioned monthly by created_at)
    """
    CREATE TABLE IF NOT EXISTS messages (
        id VARCHAR(64) NOT NULL DEFAULT ('msg_' || uuidv7()::text),
        conversation_id VARCHAR(64) NOT NULL,
        role VARCHAR(16) NOT NULL,
        content_ref VARCHAR(4096) NOT NULL,
        language VARCHAR(16) NOT NULL,
        safety_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
        PRIMARY KEY (id, created_at)
    ) PARTITION BY RANGE (created_at);
    """,
    # 3. tool_invocations (Partitioned monthly by created_at)
    """
    CREATE TABLE IF NOT EXISTS tool_invocations (
        id VARCHAR(64) NOT NULL DEFAULT ('tinv_' || uuidv7()::text),
        conversation_id VARCHAR(64) NOT NULL,
        server VARCHAR(64) NOT NULL,
        tool VARCHAR(64) NOT NULL,
        args_hash CHAR(64) NOT NULL,
        result_ref VARCHAR(256) NOT NULL,
        tier VARCHAR(8) NOT NULL,
        status VARCHAR(32) NOT NULL,
        latency_ms INTEGER NOT NULL DEFAULT 0,
        trace_id VARCHAR(64) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
        PRIMARY KEY (id, created_at)
    ) PARTITION BY RANGE (created_at);
    """,
    # 4. confirmations
    """
    CREATE TABLE IF NOT EXISTS confirmations (
        id VARCHAR(64) PRIMARY KEY DEFAULT ('cfm_' || uuidv7()::text),
        conversation_id VARCHAR(64) NOT NULL,
        action_digest CHAR(64) NOT NULL,
        issued_at TIMESTAMPTZ NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        used_at TIMESTAMPTZ
    );
    """,
    # 5. handoffs
    """
    CREATE TABLE IF NOT EXISTS handoffs (
        id VARCHAR(64) PRIMARY KEY DEFAULT ('hoff_' || uuidv7()::text),
        conversation_id VARCHAR(64) NOT NULL,
        reason VARCHAR(64) NOT NULL,
        queue VARCHAR(64) NOT NULL,
        assigned_to VARCHAR(64),
        office_code VARCHAR(32) NOT NULL DEFAULT 'JUBA_HQ',
        sla_due TIMESTAMPTZ NOT NULL,
        outcome VARCHAR(32) NOT NULL DEFAULT 'PENDING'
    );
    """,
    # 6. cases
    """
    CREATE TABLE IF NOT EXISTS cases (
        id VARCHAR(64) PRIMARY KEY DEFAULT ('case_' || uuidv7()::text),
        subject_ref VARCHAR(64),
        type VARCHAR(32) NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'OPEN',
        priority VARCHAR(16) NOT NULL DEFAULT 'NORMAL',
        office_code VARCHAR(32) NOT NULL DEFAULT 'JUBA_HQ',
        sla_due TIMESTAMPTZ NOT NULL,
        events JSONB NOT NULL DEFAULT '[]'::jsonb
    );
    """,
    # 7. consents
    """
    CREATE TABLE IF NOT EXISTS consents (
        id VARCHAR(64) PRIMARY KEY DEFAULT ('cns_' || uuidv7()::text),
        subject_ref VARCHAR(64) NOT NULL,
        channel VARCHAR(32) NOT NULL,
        purpose VARCHAR(64) NOT NULL,
        granted_at TIMESTAMPTZ NOT NULL,
        revoked_at TIMESTAMPTZ,
        evidence JSONB NOT NULL DEFAULT '{}'::jsonb
    );
    """,
    # 8. knowledge_snapshots & knowledge_chunks (Hybrid FTS + pgvector 0.8+ HNSW iterative scans)
    """
    CREATE TABLE IF NOT EXISTS knowledge_snapshots (
        version VARCHAR(32) PRIMARY KEY,
        status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
        approved_by VARCHAR(128) NOT NULL,
        published_at TIMESTAMPTZ,
        checksum CHAR(64) NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_chunks (
        id VARCHAR(64) PRIMARY KEY,
        snapshot_version VARCHAR(32) NOT NULL REFERENCES knowledge_snapshots(version),
        doc_title VARCHAR(512) NOT NULL,
        section_anchor VARCHAR(128) NOT NULL,
        language VARCHAR(16) NOT NULL,
        effective_from DATE NOT NULL,
        effective_to DATE,
        content TEXT NOT NULL,
        search_tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
        embedding vector(1024)
    );
    CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_hnsw
        ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
    CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_tsv
        ON knowledge_chunks USING gin (search_tsv);
    """,
    # 9. tax_facts
    """
    CREATE TABLE IF NOT EXISTS tax_facts (
        id VARCHAR(64) PRIMARY KEY DEFAULT ('tf_' || uuidv7()::text),
        key VARCHAR(128) NOT NULL,
        value NUMERIC(20, 4) NOT NULL,
        unit VARCHAR(32) NOT NULL,
        currency VARCHAR(8) NOT NULL,
        applies_to VARCHAR(256) NOT NULL,
        effective_from DATE NOT NULL,
        effective_to DATE,
        legal_ref VARCHAR(512) NOT NULL,
        approved_by VARCHAR(128) NOT NULL,
        version VARCHAR(32) NOT NULL REFERENCES knowledge_snapshots(version),
        UNIQUE (key, version, effective_from)
    );
    """,
    # 10. audit_events (Append-only, hash-chained, partitioned monthly)
    """
    CREATE TABLE IF NOT EXISTS audit_events (
        id VARCHAR(64) NOT NULL DEFAULT ('aud_' || uuidv7()::text),
        actor VARCHAR(128) NOT NULL,
        on_behalf_of VARCHAR(64),
        action VARCHAR(128) NOT NULL,
        resource VARCHAR(256) NOT NULL,
        digest CHAR(64) NOT NULL,
        prev_hash CHAR(64) NOT NULL,
        hash CHAR(64) NOT NULL UNIQUE,
        at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
        PRIMARY KEY (id, at)
    ) PARTITION BY RANGE (at);
    """,
    # 11. outbox_events (Transactional CloudEvents 1.0 outbox to NATS JetStream)
    """
    CREATE TABLE IF NOT EXISTS outbox_events (
        id VARCHAR(64) PRIMARY KEY DEFAULT ('outbox_' || uuidv7()::text),
        source VARCHAR(128) NOT NULL,
        event_type VARCHAR(128) NOT NULL,
        subject VARCHAR(128) NOT NULL,
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        published_to_nats SMALLINT NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
    );
    CREATE INDEX IF NOT EXISTS idx_outbox_events_unpublished
        ON outbox_events (published_to_nats, created_at);
    """,
)
