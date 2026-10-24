"""Multi-turn trajectory, channel-limit (SMS/USSD), Tier C national language, and OTel/OpenBao evaluation suite (Sections 7, 11, 12.3, 14.1)."""

from __future__ import annotations

import pytest
from ssra_core import (
    AuthLevel,
    ChannelName,
    IntentName,
    LocaleCode,
    RiskTier,
    SSRAError,
    build_genai_span_attributes,
)
from ssra_runtime import SSRAConversationRuntime
from ssra_security import OpenBaoTransitEncryptor
from ssra_testing import make_conversation_event


def test_multi_turn_journey_trajectory_t0_to_t1_to_t2_confirm() -> None:
    runtime = SSRAConversationRuntime()
    thread_id = "thr_trajectory_001"

    # Turn 1 (T0): PAYE calculator
    t1 = runtime.run_turn(
        make_conversation_event(
            "Calculate PAYE on 300,000 SSP",
            thread_id=thread_id,
        )
    )
    assert t1.tier == RiskTier.T0
    assert [f"{a.server}.{a.tool}" for a in t1.artifacts] == ["tax-facts.calculate_paye_estimate"]

    # Turn 2 (T1 while ANONYMOUS): Must trigger STEP_UP with 0 tools invoked
    t2 = runtime.run_turn(
        make_conversation_event("Check my tax balance", thread_id=thread_id),
        auth_level=AuthLevel.ANONYMOUS,
    )
    assert t2.tier == RiskTier.T1
    assert t2.policy_decision == "STEP_UP"
    assert t2.artifacts == []

    # Turn 3 (T1 after OTP+TIN binding): Invokes ledger.get_balance
    t3 = runtime.run_turn(
        make_conversation_event("Check my tax balance", thread_id=thread_id),
        auth_level=AuthLevel.T1_TIN_BOUND,
        subject_ref="sub_taxpayer_deng_02",
    )
    assert t3.policy_decision == "ALLOW"
    assert [f"{a.server}.{a.tool}" for a in t3.artifacts] == ["ledger.get_balance"]
    assert "••••5678" in t3.answer.segments[0].text

    # Turn 4 (T2 write without confirmation token): Interrupts with ConfirmActionSheet
    t4 = runtime.run_turn(
        make_conversation_event("Book an appointment at Juba HQ", thread_id=thread_id),
        auth_level=AuthLevel.T1_TIN_BOUND,
        subject_ref="sub_taxpayer_deng_02",
    )
    assert t4.tier == RiskTier.T2
    assert t4.pending_confirmation is not None
    assert t4.artifacts == []

    # Turn 5 (T2 resume with single-use confirmation token): Executes appointments.book_appointment
    t5 = runtime.run_turn(
        make_conversation_event("Book an appointment at Juba HQ", thread_id=thread_id),
        auth_level=AuthLevel.T1_TIN_BOUND,
        subject_ref="sub_taxpayer_deng_02",
        confirmation_token=t4.pending_confirmation.token,
        idempotency_key=t4.pending_confirmation.idempotency_key,
    )
    assert [f"{a.server}.{a.tool}" for a in t5.artifacts] == ["appointments.book_appointment"]
    assert runtime.audit_ledger.verify_integrity() is True


def test_channel_length_limits_for_sms_and_ussd() -> None:
    runtime = SSRAConversationRuntime()

    # SMS channel enforces max_len=160
    sms_evt = make_conversation_event(
        "How do I register for a TIN?",
        channel=ChannelName.SMS,
        max_len=160,
        rich_ui=False,
    )
    sms_turn = runtime.run_turn(sms_evt)
    assert len(sms_turn.answer.segments[0].text) <= 160
    assert sms_turn.answer.ui_component is None

    # USSD channel enforces max_len=182 and deterministic synchronous path
    ussd_evt = make_conversation_event(
        "*755#",
        channel=ChannelName.USSD,
        max_len=182,
        rich_ui=False,
    )
    ussd_turn = runtime.run_turn(ussd_evt)
    assert len(ussd_turn.answer.segments[0].text) <= 182
    assert ussd_turn.artifacts == []


def test_tier_c_national_languages_curated_retrieval() -> None:
    """Section 7: Dinka (din), Nuer (nus), Bari (bfa), Zande (zne), and Shilluk (shk) curated answers."""
    runtime = SSRAConversationRuntime()
    for loc in (LocaleCode.DIN, LocaleCode.NUS, LocaleCode.BFA, LocaleCode.ZNE, LocaleCode.SHK):
        evt = make_conversation_event("TIN registration e-Tax", locale=loc)
        turn = runtime.run_turn(evt)
        assert not turn.answer.abstained
        assert turn.answer.citations[0].section_anchor == "Part-I-Sec-1-TIN-Registration"
        assert "https://etax.nra.gov.ss/" in turn.answer.segments[0].text


def test_openbao_transit_encryption_and_otel_genai_attributes() -> None:
    enc = OpenBaoTransitEncryptor()
    ct = enc.encrypt_field("2003005678", context="tin-binding")
    assert ct.startswith("vault:v1:")
    assert "2003005678" not in ct
    assert enc.decrypt_field(ct, context="tin-binding") == "2003005678"

    # Wrong AAD context is rejected
    with pytest.raises(SSRAError):
        enc.decrypt_field(ct, context="wrong-context")

    span_attrs = build_genai_span_attributes(
        model="ssra-sovereign/qwen2.5-14b-instruct",
        input_tokens=420,
        output_tokens=180,
        channel=ChannelName.WHATSAPP,
        locale=LocaleCode.PGA,
        intent=IntentName.CALCULATE_PAYE,
        tier=RiskTier.T0,
    ).to_otel_dict()
    assert span_attrs["gen_ai.system"] == "ssra.sovereign.vllm"
    assert span_attrs["ssra.channel"] == "whatsapp"
    assert span_attrs["ssra.cost.estimated_usd"] > 0.005


def test_multiturn_anaphoric_slot_carryover_and_guided_journey_progression() -> None:
    """ADR-028 Phase 1: Verify multi-turn slot carry-over (PAYE, WHT, Customs HS code) and guided journey progression."""
    runtime = SSRAConversationRuntime()
    thread_id = "thr_adr028_multiturn_01"

    # 1. PAYE Turn 1 -> Anaphoric Turn 2 ('Please, what if it is 800,000 SSP?')
    t1 = runtime.run_turn(
        make_conversation_event("Calculate PAYE on 300,000 SSP", thread_id=thread_id)
    )
    assert t1.intent is not None and t1.intent.intent == IntentName.CALCULATE_PAYE
    t2 = runtime.run_turn(
        make_conversation_event("Please, what if it is 800,000 SSP?", thread_id=thread_id)
    )
    assert t2.intent is not None and t2.intent.intent == IntentName.CALCULATE_PAYE
    assert "800000" in t2.answer.segments[0].text

    # 2. Withholding Tax Turn 3 -> Category follow-up Turn 4 ('What if it is for technical fees?')
    t3 = runtime.run_turn(
        make_conversation_event(
            "Calculate withholding tax on 2,000,000 SSP for rent",
            thread_id=thread_id,
        )
    )
    assert t3.intent is not None and t3.intent.intent == IntentName.CALCULATE_WITHHOLDING
    t4 = runtime.run_turn(
        make_conversation_event("What if it is for technical fees?", thread_id=thread_id)
    )
    assert t4.intent is not None and t4.intent.intent == IntentName.CALCULATE_WITHHOLDING
    assert "2000000" in t4.answer.segments[0].text
    assert "technical_fees" in t4.answer.segments[0].text

    # 3. Customs HS code Turn 5 -> CIF follow-up Turn 6 without repeating HS code
    t5 = runtime.run_turn(
        make_conversation_event("What is the customs tariff for HS 8703.23?", thread_id=thread_id)
    )
    assert [f"{a.server}.{a.tool}" for a in t5.artifacts] == ["customs.lookup_tariff"]
    t6 = runtime.run_turn(
        make_conversation_event("What if CIF is $12,000 USD?", thread_id=thread_id)
    )
    assert [f"{a.server}.{a.tool}" for a in t6.artifacts] == ["customs.estimate_duties"]
    assert "8703.23" in t6.answer.segments[0].text
    assert "12000" in t6.answer.segments[0].text

    # 4. Guided Journey Step 1 -> Mid-journey side question -> 'Next step' Step 2 -> 'Next step' Step 3
    journey_thread = "thr_adr028_journey_01"
    j1 = runtime.run_turn(
        make_conversation_event("How do I register for a TIN?", thread_id=journey_thread)
    )
    assert j1.intent is not None and j1.intent.intent == IntentName.GUIDED_TIN_REGISTRATION
    assert j1.answer.ui_component is not None
    assert j1.answer.ui_component.props.get("current_step") == 1

    # Mid-journey side question preserves workflow_stack and surfaces resumption cue
    j_side = runtime.run_turn(
        make_conversation_event("How much is PAYE on 400,000 SSP?", thread_id=journey_thread)
    )
    assert j_side.intent is not None and j_side.intent.intent == IntentName.CALCULATE_PAYE
    assert "Guided journey paused at Step 1" in j_side.answer.segments[0].text

    # 'Next step' advances to Step 2, then Step 3 (COMPLETED)
    j2 = runtime.run_turn(make_conversation_event("Next step", thread_id=journey_thread))
    assert j2.intent is not None and j2.intent.intent == IntentName.GUIDED_TIN_REGISTRATION
    assert j2.answer.ui_component is not None
    assert j2.answer.ui_component.props.get("current_step") == 2
    assert "Step 2" in j2.answer.segments[0].text

    j3 = runtime.run_turn(make_conversation_event("Continue", thread_id=journey_thread))
    assert j3.answer.ui_component is not None
    assert j3.answer.ui_component.props.get("current_step") == 3
    assert j3.answer.ui_component.props["resumable_workflow"]["status"] == "COMPLETED"

    # A T4 appeal prefixed with 'Next' must NOT be overridden by guided journey continuation
    j_t4 = runtime.run_turn(
        make_conversation_event("Next, I want to appeal assessment", thread_id=journey_thread)
    )
    assert j_t4.intent is not None and j_t4.intent.intent == IntentName.REQUEST_WAIVER_OR_DISPUTE_T4
    assert j_t4.tier == RiskTier.T4
    assert j_t4.policy_decision == "HANDOFF"


def test_toolathlon_compound_multi_tool_and_quiet_fault_loop_guards() -> None:
    """ADR-028 Phase 2 & 3: Verify Toolathlon compound tool execution, read memoization, loop blocking, and quiet fault detection."""
    from ssra_runtime.nodes.compose import compose_node
    from ssra_runtime.nodes.verifier import verify_plan_outcomes
    from ssra_runtime.schemas import ToolArtifact, TurnBudget

    runtime = SSRAConversationRuntime()

    # 1. Compound T0 turn: PAYE + Withholding Tax executed and synthesized in a single turn
    comp_t0 = runtime.run_turn(
        make_conversation_event(
            "Calculate PAYE on 500,000 SSP and withholding tax on 1,000,000 SSP for rent",
            thread_id="thr_toolathlon_t0",
        )
    )
    assert [f"{a.server}.{a.tool}" for a in comp_t0.artifacts] == [
        "tax-facts.calculate_paye_estimate",
        "tax-facts.calculate_withholding_estimate",
    ]
    assert "500000" in comp_t0.answer.segments[0].text
    assert "1000000" in comp_t0.answer.segments[0].text
    assert len(comp_t0.answer.citations) == 2

    # 2. Compound T1 turn: Balance + Filing Status + Customs Declaration + TCC Status
    comp_t1 = runtime.run_turn(
        make_conversation_event(
            "Check my balance, my filing status, my customs declaration status, and my TCC status",
            thread_id="thr_toolathlon_t1",
        ),
        auth_level=AuthLevel.T1_TIN_BOUND,
        subject_ref="sub_taxpayer_deng_02",
    )
    executed_tools = [f"{a.server}.{a.tool}" for a in comp_t1.artifacts]
    assert "ledger.get_balance" in executed_tools
    assert "ledger.get_filing_status" in executed_tools
    assert "tcc.get_tcc_status" in executed_tools
    assert "TCC status:" in comp_t1.answer.segments[0].text
    assert "Last filed period:" in comp_t1.answer.segments[0].text

    # 3. Turn-scoped read memoization on call #2 and TOOL_LOOP_DETECTED block on call #3
    budget = TurnBudget()
    a1 = runtime.gateway.invoke_tool(
        server_name="tax-facts",
        tool_name="get_tax_fact",
        arguments={"key": "paye.filing.deadline_day"},
        budget=budget,
    )
    a2 = runtime.gateway.invoke_tool(
        server_name="tax-facts",
        tool_name="get_tax_fact",
        arguments={"key": "paye.filing.deadline_day"},
        budget=budget,
    )
    assert a1.id == a2.id  # Memoized artifact returned on second identical read call
    with pytest.raises(SSRAError, match="TOOL_LOOP_DETECTED"):
        runtime.gateway.invoke_tool(
            server_name="tax-facts",
            tool_name="get_tax_fact",
            arguments={"key": "paye.filing.deadline_day"},
            budget=budget,
        )

    # 4. Quiet tool failure detection (arXiv:2610.10062) catches corrupted mathematical figures across PAYE, WHT, Customs & Balance
    from ssra_runtime.tools.mcp_client import bound_overlong_tool_output

    bounded_out = bound_overlong_tool_output({"results": list(range(30)), "numeric_claims": [1, 2]})
    assert len(bounded_out["results"]) == 25
    assert bounded_out["_truncated_items"] is True

    # Explicit CALCULATE_WITHHOLDING without amount inherits prior_slots['amount_ssp']
    wht_inherit = runtime.run_turn(
        make_conversation_event(
            "Calculate withholding tax for consultancy",
            thread_id="thr_adr028_multiturn_01",
        )
    )
    assert (
        wht_inherit.intent is not None
        and wht_inherit.intent.intent == IntentName.CALCULATE_WITHHOLDING
    )

    # Compound PAYE + Customs HS code in a single turn synthesizes both PAYE and Customs Duty figures
    comp_paye_hs = runtime.run_turn(
        make_conversation_event(
            "Calculate PAYE on 400,000 SSP and customs duty for HS 8703.23 with CIF $10,000 USD",
            thread_id="thr_toolathlon_paye_hs",
        )
    )
    assert "customs.estimate_duties" in [f"{a.server}.{a.tool}" for a in comp_paye_hs.artifacts]
    assert "9000000" in comp_paye_hs.answer.segments[0].text
    assert any(c.id == "cit_customs_act" for c in comp_paye_hs.answer.citations)

    # Reverse-order compound WHT + PAYE binds each amount to its own tax cue
    rev_comp = runtime.run_turn(
        make_conversation_event(
            "Calculate withholding tax on 1,000,000 SSP for rent and PAYE on 500,000 SSP",
            thread_id="thr_toolathlon_rev_t0",
        )
    )
    assert rev_comp.artifacts[0].structured_content["gross_monthly_ssp"] == "500000"
    assert rev_comp.artifacts[1].structured_content["gross_amount_ssp"] == "1000000"

    # CIF-first compound Customs + PAYE isolates CIF USD from SSP salary amount
    cif_first_comp = runtime.run_turn(
        make_conversation_event(
            "Estimate customs duty for HS 8703.23 with CIF $10,000 USD and calculate PAYE on 400,000 SSP",
            thread_id="thr_toolathlon_cif_first",
        )
    )
    assert cif_first_comp.artifacts[0].structured_content["gross_monthly_ssp"] == "400000"
    assert cif_first_comp.artifacts[1].structured_content["cif_value_usd"] == "10000"

    # Compound PAYE + Customs tariff lookup (without CIF) and Compound WHT + Customs duty
    comp_paye_tariff = runtime.run_turn(
        make_conversation_event(
            "Calculate PAYE on 400,000 SSP and customs tariff for HS 2203.00",
            thread_id="thr_toolathlon_paye_tariff",
        )
    )
    assert any(c.id == "cit_customs_tariff" for c in comp_paye_tariff.answer.citations)

    comp_wht_duty = runtime.run_turn(
        make_conversation_event(
            "Calculate withholding tax on 1,000,000 SSP for rent and customs duty for HS 8703.23 with CIF $10,000 USD",
            thread_id="thr_toolathlon_wht_duty",
        )
    )
    assert [f"{a.server}.{a.tool}" for a in comp_wht_duty.artifacts] == [
        "tax-facts.calculate_withholding_estimate",
        "customs.estimate_duties",
    ]
    assert any(c.id == "cit_customs_act" for c in comp_wht_duty.answer.citations)

    # Arabic multi-turn anaphoric PAYE follow-up ('ماذا لو كان' with 800,000 SSP)
    runtime.run_turn(
        make_conversation_event(
            "كم ضريبة الدخل PAYE على راتب شهري ٣٠٠٬٠٠٠ SSP؟",
            locale=LocaleCode.AR,
            thread_id="thr_ar_anaphoric",
        )
    )
    ar_followup = runtime.run_turn(
        make_conversation_event(
            "ماذا لو كان ٨٠٠٬٠٠٠ SSP؟",
            locale=LocaleCode.AR,
            thread_id="thr_ar_anaphoric",
        )
    )
    assert ar_followup.intent is not None and ar_followup.intent.intent == IntentName.CALCULATE_PAYE
    assert "800000" in ar_followup.answer.segments[0].text

    corrupted_paye = ToolArtifact(
        id="art_corrupt_01",
        server="tax-facts",
        tool="calculate_paye_estimate",
        tier=RiskTier.T0,
        structured_content={
            "snapshot_version": "2026.10.1",
            "gross_monthly_ssp": "500000",
            "estimated_tax_ssp": "600000",  # Impossible: tax > gross
            "net_monthly_ssp": "450000",
            "effective_rate_percent": "120",
        },
        provenance={"snapshot_version": "2026.10.1"},
        data_classification="PUBLIC",
    )
    corrupted_wht = ToolArtifact(
        id="art_corrupt_02",
        server="tax-facts",
        tool="calculate_withholding_estimate",
        tier=RiskTier.T0,
        structured_content={
            "snapshot_version": "2026.10.1",
            "gross_amount_ssp": "100000",
            "withholding_tax_ssp": "200000",
            "net_payable_ssp": "50000",
            "rate_percent": "150",
        },
        provenance={"snapshot_version": "2026.10.1"},
        data_classification="PUBLIC",
    )
    corrupted_duty = ToolArtifact(
        id="art_corrupt_03",
        server="customs",
        tool="estimate_duties",
        tier=RiskTier.T0,
        structured_content={
            "snapshot_version": "2026.10.1",
            "cif_value_usd": "0",
            "boss_official_fx_rate_ssp_per_usd": "0",
            "estimated_duty_ssp": "-10",
        },
        provenance={"snapshot_version": "2026.10.1"},
        data_classification="PUBLIC",
    )
    corrupted_bal = ToolArtifact(
        id="art_corrupt_04",
        server="ledger",
        tool="get_balance",
        tier=RiskTier.T1,
        structured_content={
            "as_of": "2026-10-24",
            "total_outstanding_ssp": "-500",
            "tin_masked": "",
        },
        provenance={"source_id": "etax"},
        data_classification="RESTRICTED",
    )
    corrupted_tariff = ToolArtifact(
        id="art_corrupt_05",
        server="customs",
        tool="lookup_tariff",
        tier=RiskTier.T0,
        structured_content={
            "snapshot_version": "2026.10.1",
            "duty_rate_percent": "-5",
            "excise_rate_percent": "20",
            "boss_official_fx_rate_ssp_per_usd": "0",
        },
        provenance={"snapshot_version": "2026.10.1"},
        data_classification="PUBLIC",
    )
    verif = verify_plan_outcomes(
        None,
        [corrupted_paye, corrupted_wht, corrupted_duty, corrupted_bal, corrupted_tariff],
    )
    assert verif.verified is False
    assert (
        "QUIET_FAULT_DETECTED:customs.lookup_tariff:CUSTOMS_TARIFF_INVARIANT_VIOLATION"
        in verif.blocker_codes
    )
    assert (
        "QUIET_FAULT_DETECTED:tax-facts.calculate_paye_estimate:PAYE_INVARIANT_VIOLATION"
        in verif.blocker_codes
    )
    assert (
        "QUIET_FAULT_DETECTED:tax-facts.calculate_withholding_estimate:WHT_INVARIANT_VIOLATION"
        in verif.blocker_codes
    )
    assert (
        "QUIET_FAULT_DETECTED:customs.estimate_duties:CUSTOMS_DUTY_INVARIANT_VIOLATION"
        in verif.blocker_codes
    )
    abstained_comp = compose_node(
        {
            "artifacts": [corrupted_paye],
            "outcome_verification": verif.model_dump(mode="json"),
        }
    )
    assert abstained_comp["answer"].abstained is True
    assert abstained_comp["answer"].numbers == []
    assert (
        "QUIET_FAULT_DETECTED:ledger.get_balance:BALANCE_INVARIANT_VIOLATION" in verif.blocker_codes
    )
