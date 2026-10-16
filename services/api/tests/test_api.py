"""Tests for services/api across Phase 1, Phase 2 (Identity & Document Pre-check), Phase 3 (Staff Copilot & Knowledge Release), and Phase 4 (Insights)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from ssra_api import create_api_app
from ssra_api.database import POSTGRES18_RLS_AND_WORM_DDL, Base
from ssra_api.outbox import TransactionalOutboxStore


def test_api_health_and_database_ddl_invariants() -> None:
    assert len(Base.metadata.tables) == 10
    assert any("ENABLE ROW LEVEL SECURITY" in stmt for stmt in POSTGRES18_RLS_AND_WORM_DDL)
    assert any("forbid_audit_events_mutation" in stmt for stmt in POSTGRES18_RLS_AND_WORM_DDL)

    outbox = TransactionalOutboxStore()
    evt = outbox.stage_domain_event(
        context_name="cases",
        event_type="ssra.case.created.v1",
        subject="case_01",
        data={"priority": "HIGH"},
    )
    assert evt.specversion == "1.0"
    assert outbox.flush_to_jetstream() == 1
    assert outbox.published_events[0].published_to_nats is True


def test_phase2_identity_step_up_sim_swap_and_document_precheck() -> None:
    client = TestClient(create_api_app())

    # T1 OTP binding succeeds
    r_otp = client.post(
        "/v1/identity-link/verify-otp",
        json={"tin": "2003005678", "otp_code": "123456", "step_up": True},
    )
    assert r_otp.status_code == 200
    assert r_otp.json()["tin_masked"] == "••••5678"
    assert r_otp.json()["auth_level"] == "T3_STEP_UP"
    assert r_otp.json()["sim_swap_checked"] is True

    # SIM-swap recency signal blocks step-up (OQ-005 / Section 12.3)
    r_sim_swap = client.post(
        "/v1/identity-link/verify-otp",
        json={
            "tin": "2003005678",
            "otp_code": "123456",
            "step_up": True,
            "sim_swap_recent": True,
        },
    )
    assert r_sim_swap.status_code == 403

    # Document pre-check (malware scan + OCR legibility)
    r_doc = client.post(
        "/v1/identity-link/document-precheck",
        json={
            "mime_type": "application/pdf",
            "size_bytes": 120_000,
            "sha256_hex": "a" * 64,
        },
    )
    assert r_doc.status_code == 200
    assert r_doc.json()["malware_scan_status"] == "CLEAN"
    assert r_doc.json()["ocr_legible"] is True


def test_phase3_staff_copilot_takeover_handback_and_qa_scoring() -> None:
    client = TestClient(create_api_app())

    r_conv = client.post(
        "/v1/conversations",
        json={"channel": "whatsapp", "locale": "pga", "office_code": "JUBA_HQ"},
        headers={"Idempotency-Key": "idem_conv_1"},
    )
    assert r_conv.status_code == 200
    conv_id = r_conv.json()["id"]

    # Staff takeover
    r_takeover = client.post(
        f"/v1/conversations/{conv_id}/takeover",
        json={"staff_id": "officer_grace_01"},
    )
    assert r_takeover.status_code == 200
    assert r_takeover.json()["status"] == "STAFF_TAKEOVER"
    assert r_takeover.json()["assigned_staff_id"] == "officer_grace_01"

    # AI Copilot draft with citations
    r_draft = client.post(
        f"/v1/conversations/{conv_id}/copilot-draft",
        json={"taxpayer_question": "How do I pay my business tax on eTax?"},
    )
    assert r_draft.status_code == 200
    assert "https://etax.nra.gov.ss/" in r_draft.json()["cited_reply_draft"]
    assert len(r_draft.json()["citations"]) >= 1

    # Hand back to AI
    r_handback = client.post(f"/v1/conversations/{conv_id}/handback")
    assert r_handback.status_code == 200
    assert r_handback.json()["status"] == "HANDED_BACK_TO_AI"

    # QA Rubric scoring
    r_qa = client.post(
        f"/v1/conversations/{conv_id}/qa-score",
        json={
            "accuracy": 1.0,
            "citations_complete": 1.0,
            "neutrality": 1.0,
            "language_quality": 0.96,
        },
    )
    assert r_qa.status_code == 200
    assert r_qa.json()["qa_score"] == 0.99


def test_phase3_knowledge_release_6_step_workflow_and_one_step_rollback() -> None:
    client = TestClient(create_api_app())

    # Step 1: Create draft snapshot
    r1 = client.post(
        "/v1/knowledge-admin/snapshots",
        json={"version": "2026.11.0", "content_digest_input": "Financial Act update"},
    )
    assert r1.status_code == 200
    assert r1.json()["status"] == "DRAFT"

    # Step 2: Submit for legal review
    r2 = client.post("/v1/knowledge-admin/snapshots/2026.11.0/submit-review")
    assert r2.status_code == 200
    assert r2.json()["status"] == "LEGAL_REVIEW"

    # Maker-checker check: draft author cannot self-approve their own snapshot
    r_self_approve = client.post(
        "/v1/knowledge-admin/snapshots/2026.11.0/approve",
        json={"legal_approver": "policy_author_default"},
    )
    assert r_self_approve.status_code == 403

    # Step 3: Legal approval by independent counsel
    r3 = client.post(
        "/v1/knowledge-admin/snapshots/2026.11.0/approve",
        json={"legal_approver": "SSRA Chief Legal Counsel"},
    )
    assert r3.status_code == 200
    assert r3.json()["status"] == "APPROVED"

    # Step 4 & 5: Publish with passing eval gate
    r4 = client.post(
        "/v1/knowledge-admin/snapshots/2026.11.0/publish",
        json={"eval_regression_passed": True},
    )
    assert r4.status_code == 200
    assert r4.json()["status"] == "PUBLISHED"

    # Step 6: One-step rollback restores 2026.10.1
    r_rb = client.post("/v1/knowledge-admin/snapshots/rollback")
    assert r_rb.status_code == 200
    assert r_rb.json()["version"] == "2026.10.1"
    assert r_rb.json()["status"] == "PUBLISHED"


def test_phase4_regional_and_multilingual_insights() -> None:
    client = TestClient(create_api_app())
    r = client.get("/v1/analytics/insights")
    assert r.status_code == 200
    insights = r.json()
    assert len(insights) >= 3
    locales = {i["locale"] for i in insights}
    assert {"en", "pga", "ar"}.issubset(locales)

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
    assert r_drift.status_code == 200
    assert r_drift.json()["status"] == "HEALTHY"
    assert r_drift.json()["slo_burn_rate_alert"] is False

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

    # Live kill-switch update & audit chain verification (Section 12.3)
    r_ks = client.post(
        "/v1/admin/kill-switches",
        json={
            "degradation_level": 4,
            "disabled_tools": ["ledger.get_balance"],
            "disabled_channels": ["voice"],
        },
    )
    assert r_ks.status_code == 200
    assert r_ks.json()["degradation_level"] == 4

    r_aud = client.get("/v1/admin/audit-verify")
    assert r_aud.status_code == 200
    assert r_aud.json()["integrity_verified"] is True
    assert r_aud.json()["events_count"] >= 1

    r_status = client.get("/v1/admin/public-status")
    assert r_status.status_code == 200
    assert r_status.json()["overall_status"] == "DEGRADED_SAFE_MODE"
    assert r_status.json()["channels"]["voice"] == "PAUSED"

    r_slots = client.get("/v1/appointments/slots?office_code=JUBA_HQ")
    assert r_slots.status_code == 200
    assert len(r_slots.json()) == 2

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
    assert r_inbox.status_code == 200

    # JIT Admin elevation with maker-checker & device posture verification (Section 12.3)
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

    r_jit_ok = client.post(
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
    assert r_jit_ok.status_code == 200
    assert r_jit_ok.json()["granted"] is True

    # Real-time inbox SSE stream & Tier T3 Maker-Checker approval + Postgres RLS context
    r_inbox_stream = client.get("/v1/conversations/inbox/stream?office_code=JUBA_HQ")
    assert r_inbox_stream.status_code == 200
    assert "INBOX_SNAPSHOT" in r_inbox_stream.text

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
    assert r_mc_ok.status_code == 200
    assert r_mc_ok.json()["status"] == "MAKER_CHECKER_APPROVED"

    from ssra_api.repositories import PostgresRlsSessionContext

    rls_ctx = PostgresRlsSessionContext(
        staff_id="stf_01", office_code="JUBA_HQ", staff_role="agent"
    )
    assert "JUBA_HQ" in rls_ctx.to_set_local_sql()[0]


def test_api_conventions_etag_304_idempotency_replay_and_traceparent() -> None:
    client = TestClient(create_api_app())

    # 1. GET returns ETag and traceparent; If-None-Match returns 304 Not Modified
    r_get1 = client.get("/v1/analytics/summary")
    assert r_get1.status_code == 200
    etag = r_get1.headers.get("ETag")
    assert etag is not None
    assert "traceparent" in r_get1.headers

    r_get2 = client.get("/v1/analytics/summary", headers={"If-None-Match": etag})
    assert r_get2.status_code == 304

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
