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
