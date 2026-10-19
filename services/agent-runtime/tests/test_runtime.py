"""Unit and trajectory tests for services/agent-runtime (Section 6 & 14)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from ssra_core import (
    Answer,
    AnswerSegment,
    AuthLevel,
    ChannelName,
    Citation,
    IntentName,
    LocaleCode,
    NumericClaim,
    NumericUnit,
    RiskTier,
)
from ssra_runtime import SSRAConversationRuntime, create_runtime_app
from ssra_runtime.gateway_server import create_agentgateway_app
from ssra_runtime.graphs import build_minimal_complaint_ticket, get_guided_journey_steps
from ssra_runtime.guardrails import validate_numeric_provenance
from ssra_testing import make_conversation_event


def test_t0_paye_calculator_and_agui_sse_stream() -> None:
    client = TestClient(create_runtime_app())
    r = client.post(
        "/v1/turns",
        json={
            "message": "How much is PAYE on 250,000 SSP per month?",
            "locale": "en",
            "channel": "web",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["tier"] == "T0"
    assert data["answer"]["is_estimate"] is True
    assert data["answer"]["ui_component"]["name"] == "CalculatorForm"
    assert len(data["audit_event_hash"]) == 64

    # Verify AG-UI SSE stream emits RUN_STARTED, TOOL_CALL_START, TEXT_MESSAGE_CONTENT, CUSTOM, RUN_FINISHED
    stream_res = client.post(
        "/v1/agui/stream",
        json={
            "message": "How much is PAYE on 250,000 SSP per month?",
            "thread_id": "thr_sse_resume_01",
            "locale": "en",
            "channel": "web",
        },
    )
    assert stream_res.status_code == 200
    body_text = stream_res.text
    for expected_event in (
        "RUN_STARTED",
        "TOOL_CALL_START",
        "TEXT_MESSAGE_CONTENT",
        "ssra.ui_component",
        "RUN_FINISHED",
    ):
        assert expected_event in body_text

    # Resumable AG-UI SSE via Last-Event-ID skips already delivered events
    resumed_res = client.post(
        "/v1/agui/stream",
        headers={"Last-Event-ID": "thr_sse_resume_01:ev:2"},
        json={
            "message": "How much is PAYE on 250,000 SSP per month?",
            "thread_id": "thr_sse_resume_01",
            "locale": "en",
            "channel": "web",
        },
    )
    assert resumed_res.status_code == 200
    assert "id: thr_sse_resume_01:ev:1\n" not in resumed_res.text
    assert "RUN_FINISHED" in resumed_res.text

    # RFC 9457 Problem Details on invalid runtime request payload
    r_bad = client.post("/v1/turns", json={"unknown_field": 1})
    assert r_bad.status_code == 422
    assert r_bad.headers["content-type"].startswith("application/problem+json")


def test_t4_waiver_routes_deterministically_to_human_handoff_with_zero_tools() -> None:
    runtime = SSRAConversationRuntime()
    event = make_conversation_event("Please waive my late filing penalty for last month")
    turn = runtime.run_turn(event)

    assert turn.tier == RiskTier.T4
    assert turn.policy_decision == "HANDOFF"
    assert turn.artifacts == []  # T4 never invokes a tool
    assert turn.handoff_ticket is not None
    assert turn.handoff_ticket.reason == "T4_POLICY"


def test_t1_balance_requires_step_up_when_anonymous_and_succeeds_when_bound() -> None:
    runtime = SSRAConversationRuntime()
    evt = make_conversation_event("Check my tax balance", channel=ChannelName.WHATSAPP)

    # 1. Anonymous user gets STEP_UP
    anon_turn = runtime.run_turn(evt, auth_level=AuthLevel.ANONYMOUS, subject_ref=None)
    assert anon_turn.tier == RiskTier.T1
    assert anon_turn.policy_decision == "STEP_UP"
    assert anon_turn.artifacts == []

    # 2. Verified T1_TIN_BOUND user gets their own masked balance
    authed_turn = runtime.run_turn(
        evt,
        auth_level=AuthLevel.T1_TIN_BOUND,
        subject_ref="sub_taxpayer_deng_02",
    )
    assert authed_turn.policy_decision == "ALLOW"
    assert "••••5678" in authed_turn.answer.segments[0].text
    assert "1450000" in authed_turn.answer.segments[0].text


def test_t2_write_triggers_confirmation_interrupt_and_executes_after_token() -> None:
    runtime = SSRAConversationRuntime()
    evt = make_conversation_event("Book an appointment at Juba HQ")

    # Turn 1: Interrupts with ConfirmActionSheet
    turn1 = runtime.run_turn(
        evt,
        auth_level=AuthLevel.T1_TIN_BOUND,
        subject_ref="sub_taxpayer_amina_01",
    )
    assert turn1.tier == RiskTier.T2
    assert turn1.pending_confirmation is not None
    assert turn1.answer.ui_component is not None
    assert turn1.answer.ui_component.name.value == "ConfirmActionSheet"

    # Turn 2: Resume with single-use confirmation_token & idempotency_key
    turn2 = runtime.run_turn(
        evt,
        auth_level=AuthLevel.T1_TIN_BOUND,
        subject_ref="sub_taxpayer_amina_01",
        confirmation_token=turn1.pending_confirmation.token,
        idempotency_key=turn1.pending_confirmation.idempotency_key,
    )
    assert turn2.pending_confirmation is None
    assert any(a.tool == "book_appointment" for a in turn2.artifacts)
    assert "CONFIRMED" in turn2.answer.segments[0].text

    # Deterministic HELP keyword, T1 filing_status & tcc_status, T2 create_case, and preference hydration
    help_turn = runtime.run_turn(make_conversation_event("HELP", channel=ChannelName.SMS))
    assert "SSRA Assist Help" in help_turn.answer.segments[0].text

    runtime.preference_store.upsert_preferences(
        subject_ref="sub_taxpayer_amina_01",
        low_data_mode=True,
    )
    filing_turn = runtime.run_turn(
        make_conversation_event("Check my filing status", thread_id="thr_filing_01"),
        auth_level=AuthLevel.T1_TIN_BOUND,
        subject_ref="sub_taxpayer_amina_01",
    )
    assert any(a.tool == "get_filing_status" for a in filing_turn.artifacts)
    assert filing_turn.answer.ui_component is None  # suppressed by hydrated low_data_mode

    runtime.preference_store.delete_subject_preferences("sub_taxpayer_amina_01")
    filing_rich = runtime.run_turn(
        make_conversation_event("Check my filing status", thread_id="thr_filing_02"),
        auth_level=AuthLevel.T1_TIN_BOUND,
        subject_ref="sub_taxpayer_amina_01",
    )
    assert filing_rich.answer.ui_component is not None
    assert filing_rich.answer.ui_component.name.value == "FilingStatusTimeline"

    tcc_turn = runtime.run_turn(
        make_conversation_event("Check my TCC status", thread_id="thr_tcc_01"),
        auth_level=AuthLevel.T1_TIN_BOUND,
        subject_ref="sub_taxpayer_amina_01",
    )
    assert any(a.tool == "get_tcc_status" for a in tcc_turn.artifacts)
    assert "VALID" in tcc_turn.answer.segments[0].text

    case_evt = make_conversation_event(
        "Please open a support case for my eTax receipt", thread_id="thr_case_01"
    )
    case_t1 = runtime.run_turn(
        case_evt,
        auth_level=AuthLevel.T1_TIN_BOUND,
        subject_ref="sub_taxpayer_amina_01",
    )
    assert case_t1.pending_confirmation is not None
    case_t2 = runtime.run_turn(
        case_evt,
        auth_level=AuthLevel.T1_TIN_BOUND,
        subject_ref="sub_taxpayer_amina_01",
        confirmation_token=case_t1.pending_confirmation.token,
        idempotency_key=case_t1.pending_confirmation.idempotency_key,
    )
    assert any(a.tool == "create_case" for a in case_t2.artifacts)
    assert "OPEN" in case_t2.answer.segments[0].text


def test_numeric_provenance_blocks_untraced_numbers() -> None:
    bad_answer = Answer(
        segments=[
            AnswerSegment(
                text="Your PAYE tax rate is 17.5% and the penalty is 99999 SSP.",
                citation_ids=["cit_1"],
            )
        ],
        citations=[
            Citation(
                id="cit_1",
                snapshot_version="2026.10.1",
                doc_title="Taxation Act 2009",
                section_anchor="Sec-1",
                effective_from="2024-07-01",
            )
        ],
        numbers=[
            NumericClaim(
                value="10", unit=NumericUnit.PERCENT, source_ref="paye.bracket.2.rate_percent"
            )
        ],
        is_estimate=False,
        abstained=False,
    )
    res = validate_numeric_provenance(
        bad_answer,
        tool_artifacts=[{"rate_percent": "10"}],
    )
    assert res.passed is False
    assert "17.5" in res.unverified_numbers
    assert "99999" in res.unverified_numbers


def test_phase1_guided_journeys_and_minimal_data_complaint_intake() -> None:
    tin_steps = get_guided_journey_steps(IntentName.GUIDED_TIN_REGISTRATION)
    assert len(tin_steps) == 3
    assert tin_steps[0].official_portal == "https://etax.nra.gov.ss/"

    tcc_steps = get_guided_journey_steps(IntentName.GUIDED_TCC)
    assert len(tcc_steps) == 2

    complaint = build_minimal_complaint_ticket(
        "My TIN is 1002001234 and phone +211912345678, eTax login page was slow."
    )
    assert "100200" not in complaint.redacted_summary
    assert "••••1234" in complaint.redacted_summary
    assert "+211•••••••78" in complaint.redacted_summary


def test_agentgateway_stateless_mcp_routing_spend_cap_and_a2a_stub() -> None:
    gw_client = TestClient(create_agentgateway_app(daily_usd_cap=10.0))

    # 1. tools/list cached by server name
    r_list = gw_client.post(
        "/mcp",
        headers={"Mcp-Method": "tools/list", "Mcp-Name": "tax-facts"},
        json={},
    )
    assert r_list.status_code == 200
    assert r_list.json()["_meta"]["protocolVersion"] == "2026-07-28"

    # 2. tools/call routed by Mcp-Method and Mcp-Name
    r_call = gw_client.post(
        "/mcp",
        headers={"Mcp-Method": "tools/call", "Mcp-Name": "tax-facts"},
        json={"params": {"name": "get_tax_fact", "arguments": {"key": "paye.filing.deadline_day"}}},
    )
    assert r_call.status_code == 200
    assert r_call.json()["structured_content"]["fact"]["value"] == "15"

    # 3. A2A v1.0 stub is blocked in MVP (ADR-014)
    r_a2a = gw_client.post("/a2a/v1", json={})
    assert r_a2a.status_code == 403

    # 4. Daily spend cap enforcement
    r_spend = gw_client.post("/v1/spend/record", json={"cost_usd": 12.5})
    assert r_spend.status_code == 429


def test_subject_preference_memory_store_forbids_free_text_and_supports_erasure() -> None:
    from ssra_core import LocaleCode
    from ssra_runtime.memory import SubjectPreferenceMemoryStore

    store = SubjectPreferenceMemoryStore()
    pref = store.upsert_preferences(
        subject_ref="sub_01",
        preferred_locale=LocaleCode.AR,
        preferred_channel=ChannelName.WHATSAPP,
        low_data_mode=True,
    )
    assert pref.preferred_locale == LocaleCode.AR
    assert store.get_preferences("sub_01") is not None
    assert store.delete_subject_preferences("sub_01") is True
    assert store.get_preferences("sub_01") is None


def test_conversation_replay_forensic_reconstruction_endpoint() -> None:
    client = TestClient(create_runtime_app())
    r_turn = client.post(
        "/v1/turns",
        json={
            "message": "How much is PAYE on 250,000 SSP per month?",
            "thread_id": "thr_replay_99",
            "locale": "en",
            "channel": "web",
        },
    )
    assert r_turn.status_code == 200

    r_replay = client.get("/v1/turns/thr_replay_99/replay")
    assert r_replay.status_code == 200
    records = r_replay.json()
    assert len(records) == 1
    rec = records[0]
    assert rec["thread_id"] == "thr_replay_99"
    assert rec["prompt_version"] == "2026.10.1"
    assert rec["knowledge_snapshot_version"] == "2026.10.1"
    assert rec["tool_calls"][0]["tool"] == "calculate_paye_estimate"
    assert len(rec["audit_event_hash"]) == 64


def test_pgvector_hybrid_rrf_and_embedding_reranker_bakeoff() -> None:
    from ssra_runtime.retrieval import (
        PGVECTOR_ITERATIVE_SCAN_SQL,
        build_pgvector_hybrid_rrf_sql,
        evaluate_embedding_reranker_bakeoff,
        reciprocal_rank_fusion,
    )

    assert "relaxed_order" in PGVECTOR_ITERATIVE_SCAN_SQL
    sql = build_pgvector_hybrid_rrf_sql()
    assert "ts_rank_cd" in sql and "embedding <=>" in sql

    fused = reciprocal_rank_fusion(["chk_1", "chk_2"], ["chk_2", "chk_3"], top_k=2)
    assert fused[0][0] == "chk_2"  # Appears in both lexical and dense top ranks

    bakeoff = evaluate_embedding_reranker_bakeoff(
        {
            "Qwen3-Embedding + Qwen3-Reranker": [
                {
                    "locale": "en",
                    "expected_chunk_id": "chk_1",
                    "retrieved_chunk_ids": ["chk_1", "chk_2"],
                },
                {
                    "locale": "ar",
                    "expected_chunk_id": "chk_ar_1",
                    "retrieved_chunk_ids": ["chk_ar_1", "chk_2"],
                },
                {
                    "locale": "pga",
                    "expected_chunk_id": "chk_pga_1",
                    "retrieved_chunk_ids": ["chk_pga_1", "chk_3"],
                },
            ]
        },
        k=3,
    )
    assert bakeoff[0].mean_recall_at_k == 1.0
    assert bakeoff[0].meets_parity_gate is True


def test_official_manuals_faqs_and_financial_act_2024_2025_end_to_end() -> None:
    from datetime import date

    from ssra_mcp_knowledge.adapters import KnowledgeCorpusAdapter

    rt = SSRAConversationRuntime()
    cases = [
        (
            LocaleCode.EN,
            "What is the Business Profit Tax rate and advance BPT on imported goods?",
            "Chapter-XII-Sec-66-69-Business-Profit-Tax",
        ),
        (
            LocaleCode.EN,
            "What are the excise tax rates on beer, cigarettes, and passenger cars?",
            "Chapter-XV-Excise-Tax-Schedule",
        ),
        (
            LocaleCode.EN,
            "What is the penalty for late filing and can I apply for a filing extension or installment?",
            "Reg-1.21-1.22-1.36-1.40-Penalties-Extensions-And-Installments",
        ),
        (
            LocaleCode.EN,
            "What are the depreciation rates on tangible property and quarterly advance tax dates?",
            "Chapter-XII-Sec-74-84-Depreciation-And-Quarterly-Advance-Tax",
        ),
        (
            LocaleCode.EN,
            "How do I generate and verify a B2B e-invoice on eTax?",
            "Slides-1-18-B2B-EInvoice-Generation-And-Validation",
        ),
        (
            LocaleCode.EN,
            "How do I submit a customs declaration on eCustoms and what are the declaration stages?",
            "Slides-1-18-eCustoms-Declaration-And-8-Stages",
        ),
        (
            LocaleCode.EN,
            "Does my TIN expire and is tax information confidential?",
            "Sec-4-FAQs-TIN-Validity-Confidentiality-And-Cancellation",
        ),
        (
            LocaleCode.EN,
            "What is the 8% NSIF pension deduction and who is exempt from Personal Income Tax?",
            "Chapter-XI-PIT-Exemptions-And-8-Percent-NSIF-Deduction",
        ),
        (
            LocaleCode.AR,
            "ما هي نسبة ضريبة أرباح الأعمال (BPT) في القانون المالي؟",
            "Chapter-XII-Sec-66-69-Business-Profit-Tax",
        ),
        (
            LocaleCode.PGA,
            "Dariba ta arbah al-a'mal (BPT) kam fi Qanun al-Mali?",
            "Chapter-XII-Sec-66-69-Business-Profit-Tax",
        ),
    ]
    for _idx, (loc, query, expected_anchor) in enumerate(cases):
        ev = make_conversation_event(
            query,
            locale=loc,
        )
        resp = rt.run_turn(ev)
        assert resp.answer.abstained is False, (
            f"Unexpected abstention on '{query}': {resp.safety_flags}"
        )
        assert resp.safety_flags == []
        assert resp.citations[0].section_anchor == expected_anchor
        assert "[REDACTED_UNALLOWLISTED_URL]" not in resp.answer.segments[0].text

    # Verify MemStrata (arXiv:2606.26511) temporal supersession filtering
    adapter = KnowledgeCorpusAdapter()
    superseded_chunk = {
        "id": "chk_superseded_2023",
        "doc_id": "doc_financial_act_2023_2024",
        "effective_from": "2023-07-01",
    }
    assert adapter.is_temporally_valid(superseded_chunk, date(2024, 6, 1)) is True
    assert adapter.is_temporally_valid(superseded_chunk, date(2026, 10, 16)) is False
