"""Tests for services/workers (Docling-style legal structure chunker, Knowledge Release gate, and Africa/Juba SLA timers)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ssra_workers import (
    KnowledgeReleaseJob,
    ReminderCandidate,
    chunk_legal_document_by_structure,
    evaluate_case_sla,
    run_consent_checked_filing_reminder_campaign,
    verify_knowledge_release_gate,
)


def test_legal_structure_chunking_preserves_part_and_section_anchors() -> None:
    """Verify legal document chunking preserves PART and SECTION anchors and SHA-256 checksums."""
    sample_act = """
    PART IV: PERSONAL INCOME TAX (PAYE)
    Section 18: Monthly Withholding and Remittance
    Every employer shall withhold PAYE and remit via e-Tax by day 15 of the following month.
    Section 19: Electronic Tax Certificates
    Taxpayers may download their TIN certificate on etax.nra.gov.ss.
    """
    chunks = chunk_legal_document_by_structure(doc_id="doc_tax_act", raw_text=sample_act)
    anchors = [c.section_anchor for c in chunks]
    assert "Part-IV-Sec-18" in anchors
    assert "Part-IV-Sec-19" in anchors
    assert all(len(c.checksum_sha256) == 64 for c in chunks)


def test_knowledge_release_gate_and_sla_escalation() -> None:
    """Verify knowledge release gate rollback, SLA breach escalation, and goal continuation."""
    failed_job = KnowledgeReleaseJob(
        snapshot_version="2026.11.0",
        approved_by="SSRA Legal",
        eval_gate_passed=False,
    )
    assert verify_knowledge_release_gate(failed_job) == "ROLLED_BACK:2026.11.0"

    t0 = datetime(2026, 10, 16, 6, 0, tzinfo=UTC)
    t_late = t0 + timedelta(hours=5)
    sla = evaluate_case_sla(
        case_id="case_01",
        priority="HIGH",
        created_at_utc=t0,
        now_utc=t_late,
    )
    assert sla.is_breached is True
    assert sla.escalate_to_supervisor is True

    # Consent-checked campaign skips anyone without active opt-in or with STOP revocation
    summary = run_consent_checked_filing_reminder_campaign(
        tax_period_year=2026,
        tax_period_month=10,
        candidates=[
            ReminderCandidate(
                subject_ref="sub_opted_in",
                channel="whatsapp",
                locale="en",
                opt_in_granted=True,
                stop_revoked=False,
            ),
            ReminderCandidate(
                subject_ref="sub_stopped",
                channel="whatsapp",
                locale="en",
                opt_in_granted=True,
                stop_revoked=True,
            ),
            ReminderCandidate(
                subject_ref="sub_no_consent",
                channel="sms",
                locale="pga",
                opt_in_granted=False,
                stop_revoked=False,
            ),
        ],
    )
    assert summary.dispatched_subjects == ("sub_opted_in",)
    assert set(summary.skipped_no_consent_subjects) == {"sub_stopped", "sub_no_consent"}

    from ssra_voice.__main__ import main as voice_main
    from ssra_workers import (
        GoalContinuationCandidate,
        build_continuation_candidates_from_outbox_events,
        get_worker_health_status,
        run_post_interaction_goal_continuation,
    )
    from ssra_workers.__main__ import main as workers_main

    assert get_worker_health_status()["status"] == "ok"
    assert workers_main() == 0
    assert voice_main() == 0

    from ssra_core import ChannelName, IntentName, LocaleCode

    cont_summary = run_post_interaction_goal_continuation(
        [
            GoalContinuationCandidate(
                goal_id="goal_tcc_01",
                subject_ref="sub_opted_in",
                goal_type=IntentName.GUIDED_TCC,
                current_step_index=2,
                total_steps=2,
                pending_dependency="ETAX_TCC_APPROVAL",
                dependency_resolved=True,
                opt_in_consent_active=True,
                channel=ChannelName.WHATSAPP,
                locale=LocaleCode.PGA,
                within_whatsapp_24h_window=False,
                template_id="TMPL_SSRA_TCC_READY_2026",
            ),
            GoalContinuationCandidate(
                goal_id="goal_tcc_02",
                subject_ref="sub_no_consent",
                goal_type=IntentName.GUIDED_TCC,
                current_step_index=2,
                total_steps=2,
                pending_dependency="ETAX_TCC_APPROVAL",
                dependency_resolved=True,
                opt_in_consent_active=False,
            ),
            GoalContinuationCandidate(
                goal_id="goal_tcc_03",
                subject_ref="sub_unresolved",
                goal_type=IntentName.GUIDED_TCC,
                current_step_index=2,
                total_steps=2,
                pending_dependency="ETAX_TCC_APPROVAL",
                dependency_resolved=False,
                opt_in_consent_active=True,
            ),
            GoalContinuationCandidate(
                goal_id="goal_tcc_04",
                subject_ref="sub_bad_tmpl",
                goal_type=IntentName.GUIDED_TCC,
                current_step_index=2,
                total_steps=2,
                pending_dependency="ETAX_TCC_APPROVAL",
                dependency_resolved=True,
                opt_in_consent_active=True,
                channel=ChannelName.WHATSAPP,
                locale=LocaleCode.AR,
                within_whatsapp_24h_window=False,
                template_id="UNAPPROVED_TEMPLATE",
            ),
            GoalContinuationCandidate(
                goal_id="goal_tcc_05",
                subject_ref="sub_ar_ok",
                goal_type=IntentName.GUIDED_TCC,
                current_step_index=2,
                total_steps=2,
                pending_dependency="ETAX_TCC_APPROVAL",
                dependency_resolved=True,
                opt_in_consent_active=True,
                channel=ChannelName.SMS,
                locale=LocaleCode.AR,
                template_id="TMPL_SSRA_TCC_READY_2026",
            ),
            GoalContinuationCandidate(
                goal_id="goal_tcc_06",
                subject_ref="sub_en_ok",
                goal_type=IntentName.GUIDED_TCC,
                current_step_index=2,
                total_steps=2,
                pending_dependency="ETAX_TCC_APPROVAL",
                dependency_resolved=True,
                opt_in_consent_active=True,
                channel=ChannelName.SMS,
                locale=LocaleCode.EN,
                template_id="TMPL_SSRA_TCC_READY_2026",
            ),
            GoalContinuationCandidate(
                goal_id="goal_tcc_06_din",
                subject_ref="sub_din_ok",
                goal_type=IntentName.GUIDED_TCC,
                current_step_index=2,
                total_steps=2,
                pending_dependency="ETAX_TCC_APPROVAL",
                dependency_resolved=True,
                opt_in_consent_active=True,
                channel=ChannelName.WHATSAPP,
                locale=LocaleCode.DIN,
                within_whatsapp_24h_window=False,
                template_id="TMPL_SSRA_GOAL_CONTINUATION_2026",
            ),
            GoalContinuationCandidate(
                goal_id="goal_tcc_07",
                subject_ref="sub_sms_bad_tmpl",
                goal_type=IntentName.GUIDED_TCC,
                current_step_index=2,
                total_steps=2,
                pending_dependency="ETAX_TCC_APPROVAL",
                dependency_resolved=True,
                opt_in_consent_active=True,
                channel=ChannelName.SMS,
                locale=LocaleCode.EN,
                template_id="UNAPPROVED_SMS_TEMPLATE",
            ),
        ]
    )
    assert cont_summary.resumed_count == 4
    assert cont_summary.skipped_no_consent == 1
    assert cont_summary.skipped_unresolved_dependency == 1
    assert cont_summary.skipped_unapproved_template_or_flag == 2
    assert "https://etax.nra.gov.ss/" in cont_summary.dispatched_messages[0]["message"]
    assert "Wël de SSRA:" in cont_summary.dispatched_messages[3]["message"]

    from ssra_core import get_default_feature_flag_engine

    engine = get_default_feature_flag_engine()
    engine.set_flag_override(
        "FF_TEMPORAL_POST_INTERACTION_CONTINUATION", enabled=False, rollout_pct=0
    )
    try:
        disabled_cont = run_post_interaction_goal_continuation(
            [
                GoalContinuationCandidate(
                    goal_id="goal_tcc_08",
                    subject_ref="sub_opted_in",
                    goal_type=IntentName.GUIDED_TCC,
                    current_step_index=2,
                    total_steps=2,
                    pending_dependency="ETAX_TCC_APPROVAL",
                    dependency_resolved=True,
                    opt_in_consent_active=True,
                )
            ]
        )
        assert disabled_cont.skipped_unapproved_template_or_flag == 1
    finally:
        engine.reset_flag_override("FF_TEMPORAL_POST_INTERACTION_CONTINUATION")

    outbox_cands = build_continuation_candidates_from_outbox_events(
        outbox_events=[
            {"type": "ssra.cases.maker_checker_approved.v1", "subject": "sub_opted_in"},
            {"type": "ssra.conversation.handback.v1", "subject": "sub_opted_in"},
            {"type": "ssra.unrelated.event.v1", "subject": "sub_opted_in"},
        ],
        opted_in_subjects={"sub_opted_in"},
    )
    assert len(outbox_cands) == 2
    assert run_post_interaction_goal_continuation(outbox_cands).resumed_count == 2
