"""Tests for libs/ssra_llm: SovereignModelRouter, 5-step degradation ladder, and T0-only semantic cache."""

from __future__ import annotations

import pytest
from ssra_core import (
    Answer,
    AnswerSegment,
    AuthLevel,
    Citation,
    LocaleCode,
    McpErrorCode,
    RiskTier,
    SSRAError,
)
from ssra_llm import (
    AnonymousT0SemanticCache,
    PromptRegistry,
    SovereignModelRouter,
    compact_context_for_node,
)


def test_sovereign_model_router_and_5_step_degradation_ladder() -> None:
    router = SovereignModelRouter(force_degradation_level=1)
    r1 = router.select_route(node_name="compose", tier=RiskTier.T0)
    assert r1.degradation_mode == "PRIMARY_SOVEREIGN_VLLM"
    assert r1.llm_enabled is True
    assert r1.enable_thinking is True
    assert r1.reasoner_model == "Qwen/Qwen3.8-27B-FP8"

    router.set_degradation_level(4)
    r4 = router.select_route(node_name="compose", tier=RiskTier.T0)
    assert r4.degradation_mode == "RETRIEVAL_ONLY_ANSWER_CARDS"
    assert r4.llm_enabled is False
    assert r4.enable_thinking is False
    assert r4.reasoner_model is None

    from ssra_llm import VllmServingGuard

    guard = VllmServingGuard()
    req = guard.build_thinking_chat_request(
        model="Qwen/Qwen3.8-27B-FP8",
        system_prompt="You are SSRA Assist.",
        user_prompt="How do I register for a TIN?",
    )
    assert req["chat_template_kwargs"] == {"enable_thinking": True}
    think, ans = guard.extract_thinking_and_answer(
        "<think>Check TIN steps</think>\n\nRegister at https://etax.nra.gov.ss/."
    )
    assert think == "Check TIN steps"
    assert ans == "Register at https://etax.nra.gov.ss/."
    think2, ans2 = guard.extract_thinking_and_answer(
        {"reasoning": "Verify statutory rate", "content": "PAYE is 10%."}
    )
    assert think2 == "Verify statutory rate"
    assert ans2 == "PAYE is 10%."
    think3, ans3 = guard.extract_thinking_and_answer("<think>Truncated reasoning without closing")
    assert think3 == "Truncated reasoning without closing"
    assert ans3 == ""

    router.set_degradation_level(5)
    r5 = router.select_route(node_name="compose", tier=RiskTier.T0)
    assert r5.degradation_mode == "STATIC_FAQ_PLUS_CALLBACK"
    assert r5.llm_enabled is False

    # External providers are blocked by default until OQ-004 is approved
    with pytest.raises(SSRAError) as exc_info:
        router.select_route(
            node_name="compose",
            tier=RiskTier.T0,
            request_external_provider=True,
        )
    assert exc_info.value.code == McpErrorCode.NOT_AUTHORIZED


def test_anonymous_t0_semantic_cache_isolates_snapshots_and_rejects_t1() -> None:
    cache = AnonymousT0SemanticCache()
    sample_answer = Answer(
        segments=[AnswerSegment(text="Register on etax.nra.gov.ss", citation_ids=["cit_1"])],
        citations=[
            Citation(
                id="cit_1",
                snapshot_version="2026.10.1",
                doc_title="SSRA Guide",
                section_anchor="Sec-1",
                effective_from="2021-07-01",
            )
        ],
        numbers=[],
        is_estimate=False,
        abstained=False,
    )

    # T0 anonymous is cached
    stored = cache.put(
        snapshot_version="2026.10.1",
        locale=LocaleCode.EN,
        query="How do I register for a TIN?",
        tier=RiskTier.T0,
        auth_level=AuthLevel.ANONYMOUS,
        answer=sample_answer,
    )
    assert stored is True
    hit = cache.get(
        snapshot_version="2026.10.1",
        locale=LocaleCode.EN,
        query="  how do i register for a tin? ",
        tier=RiskTier.T0,
        auth_level=AuthLevel.ANONYMOUS,
    )
    assert hit is not None

    # T1 authenticated or different snapshot never hits cache
    assert (
        cache.get(
            snapshot_version="2026.10.1",
            locale=LocaleCode.EN,
            query="How do I register for a TIN?",
            tier=RiskTier.T1,
            auth_level=AuthLevel.T1_TIN_BOUND,
        )
        is None
    )
    assert (
        cache.get(
            snapshot_version="2026.11.0",
            locale=LocaleCode.EN,
            query="How do I register for a TIN?",
            tier=RiskTier.T0,
            auth_level=AuthLevel.ANONYMOUS,
        )
        is None
    )
    assert cache.invalidate_snapshot("2026.10.1") == 1

    # Context compaction & static prefix hashing (Section 6.3)
    from ssra_core import ChannelCapabilities

    reg = PromptRegistry.load_default()
    env = reg.build_layered_prompt(
        prompt_id="compose_v1",
        locale=LocaleCode.EN,
        capabilities=ChannelCapabilities(),
        user_input_redacted="How do I get a TIN?",
        retrieved_evidence=[{"id": "chk_1", "text": "Use etax.nra.gov.ss"}],
        tool_artifacts=[],
    )
    compacted = compact_context_for_node(
        env,
        running_summary="turn " * 500,
        node_token_budget=1024,
    )
    assert len(compacted.static_prefix_hash) == 64
    assert compacted.within_node_budget is True
