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
