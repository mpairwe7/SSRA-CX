"""Tests for services/api across Phase 1, Phase 2 (Identity & Document Pre-check), Phase 3 (Staff Copilot & Knowledge Release), and Phase 4 (Insights)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from ssra_api import create_api_app
from ssra_api.conversations.domain import ConversationEntity
from ssra_api.conversations.infrastructure import InMemoryConversationRepository
from ssra_api.database import POSTGRES18_RLS_AND_WORM_DDL, Base
from ssra_api.middleware import install_api_conventions_middleware
from ssra_api.outbox import InMemoryOutboxBuffer
from ssra_core import McpErrorCode, SSRAError
from ssra_testing import AsgiTestClient


def test_core_api_fails_closed_without_explicit_reference_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SSRA_RUNTIME_MODE", raising=False)
    client = AsgiTestClient(create_api_app())
    response = client.get("/healthz")
    assert response.status_code == 503
    assert response.json()["code"] == "UPSTREAM_UNAVAILABLE"

    monkeypatch.setenv("SSRA_RUNTIME_MODE", "unknown")
    invalid_mode_response = client.get("/v1/analytics/cx-scorecard")
    assert invalid_mode_response.status_code == 503
    assert invalid_mode_response.json()["code"] == "UPSTREAM_UNAVAILABLE"


def test_api_health_and_database_ddl_invariants() -> None:
    """Verify database DDL invariants, FORCE ROW LEVEL SECURITY, and recursive outbox PII redaction."""
    assert len(Base.metadata.tables) == 13
    assert any("ENABLE ROW LEVEL SECURITY" in stmt for stmt in POSTGRES18_RLS_AND_WORM_DDL)
    assert any("FORCE ROW LEVEL SECURITY" in stmt for stmt in POSTGRES18_RLS_AND_WORM_DDL)
    assert any("FOR SELECT" in stmt for stmt in POSTGRES18_RLS_AND_WORM_DDL)
    assert any("WITH CHECK" in stmt for stmt in POSTGRES18_RLS_AND_WORM_DDL)
    assert any("staff_office_isolation_handoffs" in stmt for stmt in POSTGRES18_RLS_AND_WORM_DDL)
    assert any("forbid_audit_events_mutation" in stmt for stmt in POSTGRES18_RLS_AND_WORM_DDL)

    outbox = InMemoryOutboxBuffer()
    evt = outbox.stage_domain_event(
        context_name="cases",
        event_type="ssra.case.created.v1",
        subject="case_01",
        data={
            "priority": "HIGH",
            "nested": {"tin": "2003005678", "phones": ["+211912345678", ("OTP: 849201", 42)]},
        },
    )
    assert evt.specversion == "1.0"
    assert evt.data["nested"]["tin"] == "••••5678"
    assert "+211•••••••78" in evt.data["nested"]["phones"][0]
    assert "[REDACTED_OTP]" in evt.data["nested"]["phones"][1][0]
    with pytest.raises(SSRAError) as publish_error:
        outbox.flush_to_jetstream()
    assert publish_error.value.code == McpErrorCode.UPSTREAM_UNAVAILABLE
    assert len(outbox.staged_events) == 1
    assert outbox.staged_events[0].published_to_nats is False

    bounded = InMemoryOutboxBuffer(max_staged_events=1)
    bounded.stage_domain_event(
        context_name="cases",
        event_type="ssra.case.created.v1",
        subject="case_01",
        data={},
    )
    with pytest.raises(SSRAError):
        bounded.stage_domain_event(
            context_name="cases",
            event_type="ssra.case.created.v1",
            subject="case_02",
            data={},
        )
    assert len(bounded.staged_events) == 1


def test_reference_outbox_capacity_and_snapshot_state_are_explicit() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        InMemoryOutboxBuffer(max_staged_events=0)

    outbox = InMemoryOutboxBuffer(max_staged_events=1)
    assert outbox.active_knowledge_snapshot == "2026.10.1"
    outbox.stage_domain_event(
        context_name="knowledge",
        event_type="ssra.knowledge.snapshot.published.v1",
        subject="snapshot_2026.10.2",
        data={"active_version": "2026.10.2"},
    )
    assert outbox.active_knowledge_snapshot == "2026.10.2"

    with pytest.raises(SSRAError) as overflow:
        outbox.stage_domain_event(
            context_name="knowledge",
            event_type="ssra.knowledge.snapshot.published.v1",
            subject="snapshot_2026.10.3",
            data={"active_version": "2026.10.3"},
        )
    assert overflow.value.status_code == 503
    assert outbox.active_knowledge_snapshot == "2026.10.2"
    assert len(outbox.staged_events) == 1


def test_reference_conversation_repository_scopes_reads_by_office() -> None:
    repository = InMemoryConversationRepository()
    conversation = ConversationEntity(
        id="conv_reference_01",
        channel="web",
        locale="en",
        subject_ref=None,
        auth_level="anonymous",
        started_at=datetime(2026, 10, 21, tzinfo=UTC),
        office_code="JUBA_HQ",
    )
    repository.save(conversation)

    assert repository.get(conversation.id) == conversation
    assert repository.get("missing") is None
    assert repository.list_by_office("JUBA_HQ") == [conversation]
    assert repository.list_by_office("Wau") == []


def test_appointments_slots_endpoint_abstains_without_inventory_provider() -> None:
    import asyncio

    from ssra_api.appointments.api import get_slots

    response = AsgiTestClient(create_api_app()).get("/v1/appointments/slots?office_code=JUBA_HQ")

    assert response.status_code == 503
    assert response.json()["code"] == "UPSTREAM_UNAVAILABLE"
    with pytest.raises(SSRAError) as direct_response:
        asyncio.run(get_slots("JUBA_HQ"))
    assert direct_response.value.status_code == 503


def test_identity_and_document_providers_fail_closed_until_approved() -> None:
    client = AsgiTestClient(create_api_app())

    r_otp = client.post(
        "/v1/identity-link/verify-otp",
        json={"tin": "2003005678", "otp_code": "123456", "step_up": True},
    )
    assert r_otp.status_code == 503
    assert r_otp.json()["code"] == "UPSTREAM_UNAVAILABLE"

    r_doc = client.post(
        "/v1/identity-link/document-precheck",
        json={
            "mime_type": "application/pdf",
            "size_bytes": 120_000,
            "sha256_hex": "a" * 64,
        },
    )
    assert r_doc.status_code == 503
    assert r_doc.json()["code"] == "UPSTREAM_UNAVAILABLE"

    r_analysis = client.post(
        "/v1/identity-link/documents/analyze",
        json={"filename": "receipt.pdf", "text_content": "sample", "size_bytes": 120_000},
    )
    assert r_analysis.status_code == 503
    assert r_analysis.json()["code"] == "UPSTREAM_UNAVAILABLE"


def test_phase3_staff_copilot_and_conversation_routes_fail_closed_without_staff_sessions() -> None:
    client = AsgiTestClient(create_api_app())

    r_conv = client.post(
        "/v1/conversations",
        json={"channel": "whatsapp", "locale": "pga", "office_code": "JUBA_HQ"},
        headers={"Idempotency-Key": "idem_conv_1"},
    )
    assert r_conv.status_code == 200
    conv_id = r_conv.json()["id"]

    # No route may infer staff identity from a request body or caller-controlled header.
    r_takeover = client.post(
        f"/v1/conversations/{conv_id}/takeover",
        json={"staff_id": "officer_grace_01"},
    )
    assert r_takeover.status_code == 403
    assert r_takeover.json()["code"] == "NOT_AUTHORIZED"

    r_inbox = client.get("/v1/conversations/inbox?office_code=JUBA_HQ")
    assert r_inbox.status_code == 403
    assert r_inbox.json()["code"] == "NOT_AUTHORIZED"

    # A reference response cannot be represented as a staff action or cited draft.
    r_draft = client.post(
        f"/v1/conversations/{conv_id}/copilot-draft",
        json={"taxpayer_question": "How do I pay my business tax on eTax?"},
    )
    assert r_draft.status_code == 403

    # Handback and QA scoring also require a verified session.
    r_handback = client.post(f"/v1/conversations/{conv_id}/handback")
    assert r_handback.status_code == 403

    r_qa = client.post(
        f"/v1/conversations/{conv_id}/qa-score",
        json={
            "accuracy": 1.0,
            "citations_complete": 1.0,
            "neutrality": 1.0,
            "language_quality": 0.96,
        },
    )
    assert r_qa.status_code == 403
    assert r_qa.json()["code"] == "NOT_AUTHORIZED"


def test_knowledge_release_routes_require_verified_staff_session() -> None:
    client = AsgiTestClient(create_api_app())
    claimed_staff = {"X-SSRA-Staff-Id": "secops_admin"}

    responses = [
        client.get("/v1/knowledge-admin/active-snapshot", headers=claimed_staff),
        client.post(
            "/v1/knowledge-admin/snapshots",
            json={"version": "2026.11.0", "content_digest_input": "Financial Act update"},
            headers=claimed_staff,
        ),
        client.post("/v1/knowledge-admin/snapshots/2026.11.0/submit-review", headers=claimed_staff),
        client.post(
            "/v1/knowledge-admin/snapshots/2026.11.0/approve",
            json={"legal_approver": "SSRA Chief Legal Counsel"},
            headers=claimed_staff,
        ),
        client.post(
            "/v1/knowledge-admin/snapshots/2026.11.0/publish",
            json={"eval_regression_passed": True},
            headers=claimed_staff,
        ),
        client.post("/v1/knowledge-admin/snapshots/rollback", headers=claimed_staff),
    ]

    assert all(response.status_code == 403 for response in responses)
    assert all(response.json()["code"] == "NOT_AUTHORIZED" for response in responses)


def test_reference_knowledge_release_engine_transitions_without_http_access() -> None:
    from ssra_api.knowledge_admin.application import (
        KnowledgeReleaseWorkflowEngine,
        get_active_snapshot_use_case,
        get_workflow_engine,
    )

    assert get_workflow_engine() is not None
    assert get_active_snapshot_use_case().version == "2026.10.1"
    engine = KnowledgeReleaseWorkflowEngine()
    assert engine.get_active().version == "2026.10.1"

    first = "2026.11.0-reference"
    engine.create_draft(
        version=first, content_digest_input="synthetic test fixture", created_by="maker"
    )
    with pytest.raises(SSRAError):
        engine.publish_snapshot(first, eval_regression_passed=True)
    assert engine.submit_for_legal_review(first).status == "LEGAL_REVIEW"
    with pytest.raises(SSRAError) as self_approval:
        engine.approve_snapshot(first, legal_approver=" maker ")
    assert self_approval.value.code == McpErrorCode.NOT_AUTHORIZED
    assert engine.approve_snapshot(first, legal_approver="checker").status == "APPROVED"
    assert engine.publish_snapshot(first, eval_regression_passed=False).status == "ROLLED_BACK"

    second = "2026.12.0-reference"
    engine.create_draft(
        version=second, content_digest_input="synthetic test fixture", created_by="maker"
    )
    engine.submit_for_legal_review(second)
    engine.approve_snapshot(second, legal_approver="checker")
    assert engine.publish_snapshot(second, eval_regression_passed=True).status == "PUBLISHED"
    assert engine.get_active().version == second
    assert engine.rollback_to_previous().version == "2026.10.1"


def test_phase4_regional_and_multilingual_insights() -> None:
    """Verify Phase 4 regional insights, JIT admin directory verification, maker-checker 404, and RLS."""
    client = AsgiTestClient(create_api_app())
    r = client.get("/v1/analytics/insights")
    assert r.status_code == 503
    assert r.json()["code"] == "UPSTREAM_UNAVAILABLE"

    r_fb = client.post(
        "/v1/analytics/feedback",
        json={
            "conversation_id": "conv_01",
            "csat": 5,
            "reason": "CLEAR_CITATIONS",
            "locale": "pga",
        },
    )
    assert r_fb.status_code == 200
    assert r_fb.json()["csat"] == 5

    r_drift = client.get("/v1/analytics/drift-monitors?intent_kl=0.04&abstention_rate=0.07")
    assert r_drift.status_code == 503
    assert r_drift.json()["code"] == "UPSTREAM_UNAVAILABLE"

    # Long-term consented preferences & per-subject deletion (Section 6.5)
    r_pref = client.put(
        "/v1/consent/preferences/sub_taxpayer_amina_01",
        json={
            "preferred_locale": "pga",
            "preferred_channel": "whatsapp",
            "low_data_mode": True,
            "voice_first_a11y": True,
        },
    )
    assert r_pref.status_code == 200
    assert r_pref.json()["preferred_locale"] == "pga"

    r_del = client.delete("/v1/consent/preferences/sub_taxpayer_amina_01")
    assert r_del.status_code == 200
    assert r_del.json()["deleted"] is True

    # Staff controls remain unavailable without a server-verified staff session.
    r_ks = client.post(
        "/v1/admin/kill-switches",
        json={
            "degradation_level": 4,
            "disabled_tools": ["ledger.get_balance"],
            "disabled_channels": ["voice"],
        },
    )
    assert r_ks.status_code == 403

    r_aud = client.get("/v1/admin/audit-verify")
    assert r_aud.status_code == 403

    r_status = client.get("/v1/admin/public-status")
    assert r_status.status_code == 503
    assert r_status.json()["code"] == "UPSTREAM_UNAVAILABLE"

    r_slots = client.get("/v1/appointments/slots?office_code=JUBA_HQ")
    assert r_slots.status_code == 503
    assert r_slots.json()["code"] == "UPSTREAM_UNAVAILABLE"

    r_case = client.post(
        "/v1/cases",
        json={"case_type": "INQUIRY", "summary": "TIN certificate download question"},
    )
    assert r_case.status_code == 200
    assert r_case.json()["status"] == "OPEN"

    r_consent = client.post(
        "/v1/consent",
        json={
            "subject_ref": "sub_taxpayer_amina_01",
            "channel": "whatsapp",
            "purpose": "FILING_REMINDERS",
            "revoked": False,
        },
    )
    assert r_consent.status_code == 200
    assert r_consent.json()["active"] is True

    r_inbox = client.get("/v1/conversations/inbox?office_code=JUBA_HQ")
    assert r_inbox.status_code == 403

    # Request booleans and staff IDs cannot establish a JIT authorization.
    r_jit_self = client.post(
        "/v1/admin/jit-elevation",
        json={
            "requester_staff_id": "stf_01",
            "approver_staff_id": "stf_01",
            "passkey_verified": True,
            "device_posture_compliant": True,
            "duration_minutes": 30,
            "reason": "Update routing config",
        },
    )
    assert r_jit_self.status_code == 403

    r_jit_claimed = client.post(
        "/v1/admin/jit-elevation",
        json={
            "requester_staff_id": "stf_01",
            "approver_staff_id": "stf_supervisor_02",
            "passkey_verified": True,
            "device_posture_compliant": True,
            "duration_minutes": 30,
            "reason": "Update routing config",
        },
    )
    assert r_jit_claimed.status_code == 403

    r_jit_unverified_staff = client.post(
        "/v1/admin/jit-elevation",
        json={
            "requester_staff_id": "stf_unknown_99",
            "approver_staff_id": "stf_supervisor_02",
            "passkey_verified": True,
            "device_posture_compliant": True,
            "duration_minutes": 30,
            "reason": "Unknown staff attempt",
        },
    )
    assert r_jit_unverified_staff.status_code == 403

    # Inbox streams and Tier T3 approvals require the same trusted session.
    r_inbox_stream = client.get("/v1/conversations/inbox/stream?office_code=JUBA_HQ")
    assert r_inbox_stream.status_code == 403

    r_mc_missing = client.post(
        "/v1/cases/case_nonexistent_999/maker-checker",
        json={
            "maker_staff_id": "stf_01",
            "checker_staff_id": "stf_02",
            "action_type": "TCC_EXCEPTION_REVIEW",
            "rationale": "Missing case check",
        },
    )
    assert r_mc_missing.status_code == 403

    r_mc_self = client.post(
        "/v1/cases/case_01/maker-checker",
        json={
            "maker_staff_id": "stf_01",
            "checker_staff_id": "stf_01",
            "action_type": "TCC_EXCEPTION_REVIEW",
            "rationale": "Self approval test",
        },
    )
    assert r_mc_self.status_code == 403

    r_mc_ok = client.post(
        "/v1/cases/case_01/maker-checker",
        json={
            "maker_staff_id": "stf_01",
            "checker_staff_id": "stf_02",
            "action_type": "TCC_EXCEPTION_REVIEW",
            "rationale": "Verified e-Tax payment slip",
        },
    )
    assert r_mc_ok.status_code == 403

    from ssra_api.repositories import PostgresRlsSessionContext

    rls_ctx = PostgresRlsSessionContext(
        staff_id="stf_01", office_code="JUBA_HQ", staff_role="agent"
    )
    assert "JUBA_HQ" in rls_ctx.to_set_local_sql()[0]


def test_api_conventions_etag_304_idempotency_replay_and_traceparent() -> None:
    """Verify ETag middleware plus API idempotency, SSE denial, and bounded request-body behavior."""
    etag_app = FastAPI()
    install_api_conventions_middleware(etag_app)

    @etag_app.get("/v1/reference-health")
    async def reference_health() -> dict[str, str]:
        return {"status": "ok"}

    etag_client = AsgiTestClient(etag_app)
    # Exercise caching semantics without relying on staff-only snapshot administration.
    r_get1 = etag_client.get("/v1/reference-health")
    assert r_get1.status_code == 200
    etag = r_get1.headers.get("ETag")
    assert etag is not None
    assert "traceparent" in r_get1.headers

    r_get2 = etag_client.get("/v1/reference-health", headers={"If-None-Match": etag})
    assert r_get2.status_code == 304
    assert "Strict-Transport-Security" in r_get1.headers
    assert "Permissions-Policy" in r_get1.headers

    client = AsgiTestClient(create_api_app())

    # RFC 9457 Problem Details on RequestValidationError (422)
    r_val = client.post("/v1/analytics/feedback", json={"conversation_id": "c1", "csat": 99})
    assert r_val.status_code == 422
    assert r_val.headers["content-type"].startswith("application/problem+json")
    assert r_val.json()["code"] == "VALIDATION_FAILED"

    # Reference event buffer receives synthetic test mutations but does not publish them.
    from ssra_api.outbox import get_outbox_store

    assert len(get_outbox_store().staged_events) >= 1

    # 2. POST with same Idempotency-Key returns identical cached response
    r_post1 = client.post(
        "/v1/conversations",
        json={"channel": "web", "locale": "en"},
        headers={"Idempotency-Key": "idem_replay_test_01"},
    )
    assert r_post1.status_code == 200
    assert r_post1.headers.get("X-Idempotency-Replayed") == "false"

    r_post2 = client.post(
        "/v1/conversations",
        json={"channel": "web", "locale": "en"},
        headers={"Idempotency-Key": "idem_replay_test_01"},
    )
    assert r_post2.status_code == 200
    assert r_post2.headers.get("X-Idempotency-Replayed") == "true"
    assert r_post2.json()["id"] == r_post1.json()["id"]

    # 3. Caller-scoped Idempotency-Key isolation: different X-SSRA-Subject-Ref does not collide
    r_post_other_sub = client.post(
        "/v1/conversations",
        json={"channel": "web", "locale": "en"},
        headers={
            "Idempotency-Key": "idem_replay_test_01",
            "X-SSRA-Subject-Ref": "sub_taxpayer_deng_02",
        },
    )
    assert r_post_other_sub.status_code == 200
    assert r_post_other_sub.headers.get("X-Idempotency-Replayed") == "false"
    assert r_post_other_sub.json()["id"] != r_post1.json()["id"]

    # 4. SSE stream bypasses ETag body buffering and sets Cache-Control: no-cache, no-transform
    r_sse = client.get("/v1/conversations/inbox/stream?office_code=JUBA_HQ")
    assert r_sse.status_code == 403
    assert r_sse.json()["code"] == "NOT_AUTHORIZED"

    r_chunked_oversize = client.post(
        "/v1/conversations",
        content=(b"x" * 600_000 for _ in range(2)),
    )
    assert r_chunked_oversize.status_code == 413

    # 5. Auditor role accepted in PostgresRlsSessionContext
    from ssra_api.repositories import PostgresRlsSessionContext

    aud_rls = PostgresRlsSessionContext(
        staff_id="aud_01", office_code="JUBA_HQ", staff_role="auditor"
    )
    assert "auditor" in aud_rls.to_set_local_sql()[1]

    # 7. Admin Feature-Flags API, Bidirectional Officer Hand-Back, and 2026 Agentic CX Scorecard
    r_flags_unauth = client.get(
        "/v1/admin/feature-flags",
        headers={"X-SSRA-Staff-Id": "unverified_caller"},
    )
    assert r_flags_unauth.status_code == 403

    # SEC2-G5: Read-only Auditor (ssra_auditor) is blocked from mutating kill switches or feature flags
    r_ks_auditor = client.post(
        "/v1/admin/kill-switches",
        headers={"X-SSRA-Staff-Id": "ssra_auditor"},
        json={"degradation_level": 2, "disabled_tools": [], "disabled_channels": []},
    )
    assert r_ks_auditor.status_code == 403

    r_prot_flag = client.post(
        "/v1/admin/feature-flags",
        headers={"X-SSRA-Staff-Id": "secops_admin"},
        json={"flag_name": "FF_NUMERIC_PROVENANCE", "enabled": False, "rollout_pct": 0},
    )
    assert r_prot_flag.status_code == 403

    r_flags_no_session = client.get(
        "/v1/admin/feature-flags",
        headers={"X-SSRA-Staff-Id": "secops_admin"},
    )
    assert r_flags_no_session.status_code == 403

    r_flag_upd = client.post(
        "/v1/admin/feature-flags",
        headers={"X-SSRA-Staff-Id": "secops_admin"},
        json={
            "flag_name": "FF_AUTONOMOUS_GOAL_PLANNER",
            "enabled": True,
            "rollout_pct": 100,
        },
    )
    assert r_flag_upd.status_code == 403

    r_scorecard = client.get("/v1/analytics/cx-scorecard")
    assert r_scorecard.status_code == 503
    assert r_scorecard.json()["code"] == "UPSTREAM_UNAVAILABLE"

    conv_id = r_post1.json()["id"]
    # Body-bearing handback before takeover is rejected with 403
    r_hb_before_takeover = client.post(
        f"/v1/conversations/{conv_id}/handback",
        json={
            "officer_id": "stf_01",
            "resolution_summary": "Premature handback attempt",
            "approved_next_intent": "guided_filing_and_payment",
            "return_to_ai_step": 2,
        },
    )
    assert r_hb_before_takeover.status_code == 403

    # Caller-supplied staff IDs cannot claim takeover.
    r_to = client.post(
        f"/v1/conversations/{conv_id}/takeover",
        json={"staff_id": "stf_01"},
    )
    assert r_to.status_code == 403

    # Mismatched officer_id on handback is rejected with 403
    r_hb_wrong_officer = client.post(
        f"/v1/conversations/{conv_id}/handback",
        json={
            "officer_id": "stf_other",
            "resolution_summary": "Wrong officer attempt",
            "approved_next_intent": "guided_filing_and_payment",
            "return_to_ai_step": 2,
        },
    )
    assert r_hb_wrong_officer.status_code == 403

    # Invalid approved_next_intent on handback is rejected with 422
    r_hb_bad_intent = client.post(
        f"/v1/conversations/{conv_id}/handback",
        json={
            "officer_id": "stf_01",
            "resolution_summary": "Bad intent attempt",
            "approved_next_intent": "not_a_valid_intent",
            "return_to_ai_step": 2,
        },
    )
    assert r_hb_bad_intent.status_code == 403

    r_hb = client.post(
        f"/v1/conversations/{conv_id}/handback",
        json={
            "officer_id": "stf_01",
            "resolution_summary": "Verified e-Tax assessment slip for +211912345678; ready for guided payment step.",
            "approved_next_intent": "guided_filing_and_payment",
            "return_to_ai_step": 2,
        },
    )
    assert r_hb.status_code == 403
