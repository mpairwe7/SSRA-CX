#!/usr/bin/env python3
"""Automated Verifier for Phase Exit Gates 0 through 4 (Section 18)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

from ssra_api import create_api_app
from ssra_core import LocaleCode
from ssra_runtime import create_runtime_app
from ssra_testing import AsgiTestClient
from ssra_voice import MAX_VOICE_WER_GATE, VoiceWerEvidence, is_voice_language_approved

ROOT = Path(__file__).resolve().parents[1]


def verify_all_gates() -> dict[str, str]:
    """Verify local evidence and report external/production gates without advancing them."""
    # Gate 0: repository artifacts only; SSRA and hosting sign-off remain external.
    adr_files = sorted((ROOT / "docs" / "adr").glob("00*.md"))
    assert len(adr_files) >= 16, f"Expected >= 16 ADRs, found {len(adr_files)}"
    assert (ROOT / "docs" / "architecture" / "overview.md").exists()
    assert (ROOT / "docs" / "architecture" / "data-model.md").exists()
    assert (ROOT / "docs" / "security" / "threat-model.md").exists()
    assert (ROOT / "docs" / "open-questions.md").exists()

    # Gate 1: local reference-evaluation evidence, not production launch approval.
    eval_report_path = ROOT / "evals" / "reports" / "latest-eval-report.json"
    assert eval_report_path.exists(), "Run `task eval` first to generate latest-eval-report.json"
    report = json.loads(eval_report_path.read_text(encoding="utf-8"))
    metrics = report["metrics"]
    assert report["dataset_total_items"] >= 600
    assert metrics["numeric_accuracy"] == 1.0
    assert metrics["citation_precision"] >= 0.95
    assert metrics["groundedness"] >= 0.95
    assert metrics["abstention_accuracy"] >= 0.95
    assert metrics["cross_subject_leakage_cases"] == 0
    assert metrics["language_parity_gap_ar_points"] <= 5.0
    assert metrics["language_parity_gap_pga_points"] <= 5.0
    assert (ROOT / "docs" / "runbooks" / "README.md").exists()
    assert (ROOT / "docs" / "runbooks" / "ai-incident-playbook.md").exists()
    assert (ROOT / "infra" / "loadtest" / "k6-agui-stream.js").exists()

    # Gate 2: confirm reference runtime behavior and expected production/identity blocks.
    assert (ROOT / "docs" / "ai-governance" / "impact-assessment.md").exists()
    with patch.dict("os.environ", {"SSRA_RUNTIME_MODE": "production"}):
        production_runtime_client = AsgiTestClient(create_runtime_app())
        production_turn = production_runtime_client.post(
            "/v1/turns",
            json={"message": "How do I get a TIN?", "thread_id": "thr_gate2_verify"},
        )
        assert production_turn.status_code == 503
        assert production_turn.json()["code"] == "UPSTREAM_UNAVAILABLE"

    with patch.dict("os.environ", {"SSRA_RUNTIME_MODE": "reference"}):
        rt_client = AsgiTestClient(create_runtime_app())
        r_turn = rt_client.post(
            "/v1/turns",
            json={"message": "How do I get a TIN?", "thread_id": "thr_gate2_verify"},
        )
        assert r_turn.status_code == 200
        assert r_turn.headers.get("X-SSRA-Runtime-Mode") == "reference"
        r_replay = rt_client.get("/v1/turns/thr_gate2_verify/replay")
        assert r_replay.status_code == 200
        assert len(r_replay.json()) == 1

        api_client = AsgiTestClient(create_api_app())
        r_identity = api_client.post(
            "/v1/identity-link/verify-otp",
            json={"tin": "2003005678", "otp_code": "123456"},
        )
        assert r_identity.status_code == 503
        assert r_identity.json()["code"] == "UPSTREAM_UNAVAILABLE"

    # Gate 3: the process-local snapshot fixture is not exposed through staff-only HTTP routes.
    with patch.dict("os.environ", {"SSRA_RUNTIME_MODE": "reference"}):
        api_client = AsgiTestClient(create_api_app())
        r_snap = api_client.get("/v1/knowledge-admin/active-snapshot")
        assert r_snap.status_code == 403
        assert r_snap.json()["code"] == "NOT_AUTHORIZED"
        r_publish = api_client.post(
            "/v1/knowledge-admin/snapshots/2026.11.0/publish",
            json={"eval_regression_passed": True},
        )
        assert r_publish.status_code == 403
        r_staff = api_client.get(
            "/v1/admin/feature-flags", headers={"X-SSRA-Staff-Id": "unverified_caller"}
        )
        assert r_staff.status_code == 403
        r_claimed_staff = api_client.get(
            "/v1/admin/feature-flags", headers={"X-SSRA-Staff-Id": "secops_admin"}
        )
        assert r_claimed_staff.status_code == 403
        r_inbox = api_client.get("/v1/conversations/inbox?office_code=JUBA_HQ")
        assert r_inbox.status_code == 403

    # Gate 4: no language has governed voice WER evidence (OQ-008), and the gate itself holds
    # for synthetic evidence at and above the limit. Operational analytics remain unavailable.
    assert not any(is_voice_language_approved(locale) for locale in LocaleCode)

    def _synthetic(locale: LocaleCode, wer: float) -> dict[LocaleCode, VoiceWerEvidence]:
        return {
            locale: VoiceWerEvidence(
                locale=locale,
                word_error_rate=wer,
                test_set="synthetic-gate-check",
                measured_on=date(2026, 10, 24),
                utterance_count=1,
            )
        }

    assert is_voice_language_approved(
        LocaleCode.PGA, _synthetic(LocaleCode.PGA, MAX_VOICE_WER_GATE)
    )
    assert not is_voice_language_approved(
        LocaleCode.DIN, _synthetic(LocaleCode.DIN, MAX_VOICE_WER_GATE + 0.05)
    )
    with patch.dict("os.environ", {"SSRA_RUNTIME_MODE": "reference"}):
        r_insights = AsgiTestClient(create_api_app()).get("/v1/analytics/insights")
        assert r_insights.status_code == 503
        assert r_insights.json()["code"] == "UPSTREAM_UNAVAILABLE"

    return {
        "Gate_0_Foundations": "repository artifacts present; SSRA sign-off remains open",
        "Gate_1_Public_Assistant": "reference evaluation evidence verified; not launch approval",
        "Gate_2_Authenticated_Self_Service": "blocked pending OQ-005 and OQ-015",
        "Gate_3_Staff_Copilot_And_Knowledge_Ops": "blocked pending OQ-014 and OQ-015",
        "Gate_4_Reach_And_Intelligence": "blocked pending OQ-008 voice WER evidence, OQ-013, and operational approval",
    }


def main() -> None:
    gates = verify_all_gates()
    print(f"Phase readiness audit (no gate advanced): {gates}")


if __name__ == "__main__":
    main()
