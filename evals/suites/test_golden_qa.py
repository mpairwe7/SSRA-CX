"""Golden evaluation suite enforcing Section 14.1 & 14.2 Launch Gates across 600 items (300 en, 150 ar, 150 pga)."""

from __future__ import annotations

import json
from pathlib import Path

from ssra_core import ChannelName, LocaleCode
from ssra_runtime import SSRAConversationRuntime
from ssra_runtime.guardrails import validate_grounding, validate_numeric_provenance
from ssra_testing import make_conversation_event

_PHASE1_DATASET_PATH = Path(__file__).resolve().parents[1] / "datasets" / "golden-qa-phase1.json"


def test_phase1_600_item_golden_dataset_and_launch_gates() -> None:
    dataset = json.loads(_PHASE1_DATASET_PATH.read_text(encoding="utf-8"))
    items = dataset["items"]

    # Section 14.1: Before Phase 1 launch, seed at least 300 English, 150 Arabic and 150 Juba Arabic items
    en_count = sum(1 for it in items if it["locale"] == "en")
    ar_count = sum(1 for it in items if it["locale"] == "ar")
    pga_count = sum(1 for it in items if it["locale"] == "pga")
    assert en_count >= 300
    assert ar_count >= 150
    assert pga_count >= 150
    assert len(items) >= 600

    runtime = SSRAConversationRuntime()

    numeric_checks = 0
    numeric_passed = 0
    citation_checks = 0
    citation_passed = 0
    grounded_checks = 0
    grounded_passed = 0
    abstention_checks = 0
    abstention_passed = 0

    per_locale_scores: dict[str, list[int]] = {"en": [], "ar": [], "pga": []}

    for item in items:
        locale = LocaleCode(item["locale"])
        channel = ChannelName(item["channel"])
        evt = make_conversation_event(item["query"], locale=locale, channel=channel)
        turn = runtime.run_turn(evt)

        assert turn.tier.value == item["expected_tier"], f"Failed tier on {item['id']}"

        if item["expected_abstained"]:
            abstention_checks += 1
            if turn.answer.abstained:
                abstention_passed += 1
                per_locale_scores[locale.value].append(1)
            else:
                per_locale_scores[locale.value].append(0)
            continue

        # Groundedness check
        grounded_checks += 1
        g_res = validate_grounding(turn.answer)
        if g_res.passed:
            grounded_passed += 1

        # Citation precision check
        citation_checks += 1
        anchors = [c.section_anchor for c in turn.answer.citations]
        if item["expected_citation_anchor"] in anchors:
            citation_passed += 1

        # Numeric accuracy check (100% gate)
        if item["expected_numbers"]:
            numeric_checks += 1
            num_res = validate_numeric_provenance(
                turn.answer,
                tool_artifacts=[a.structured_content for a in turn.artifacts],
            )
            claimed_vals = {n.value for n in turn.answer.numbers}
            if num_res.passed and set(item["expected_numbers"]).issubset(claimed_vals):
                numeric_passed += 1

        item_ok = (
            g_res.passed
            and (item["expected_citation_anchor"] in anchors)
            and not turn.answer.abstained
        )
        per_locale_scores[locale.value].append(1 if item_ok else 0)

    numeric_accuracy = numeric_passed / max(1, numeric_checks)
    citation_precision = citation_passed / max(1, citation_checks)
    groundedness = grounded_passed / max(1, grounded_checks)
    abstention_rate = abstention_passed / max(1, abstention_checks)

    assert numeric_accuracy == 1.0, f"Numeric accuracy {numeric_accuracy} < 1.00 gate"
    assert citation_precision >= 0.95, f"Citation precision {citation_precision} < 0.95 gate"
    assert groundedness >= 0.95, f"Groundedness {groundedness} < 0.95 gate"
    assert abstention_rate >= 0.95, f"Abstention accuracy {abstention_rate} < 0.95 gate"

    # Language parity gap: Tier B (ar, pga) vs Tier A (en) <= 5 percentage points
    en_score = (sum(per_locale_scores["en"]) / len(per_locale_scores["en"])) * 100.0
    for tier_b_loc in ("ar", "pga"):
        b_score = (sum(per_locale_scores[tier_b_loc]) / len(per_locale_scores[tier_b_loc])) * 100.0
        gap = en_score - b_score
        assert gap <= 5.0, f"Language parity gap for {tier_b_loc} is {gap} points (> 5.0 gate)"
