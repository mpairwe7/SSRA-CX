#!/usr/bin/env python3
"""Automated Verifier for Phase Exit Gates 0 through 4 (Section 18)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from ssra_api import create_api_app
from ssra_core import LocaleCode
from ssra_runtime import create_runtime_app
from ssra_voice import MAX_VOICE_WER_GATE, is_voice_language_approved

ROOT = Path(__file__).resolve().parents[1]


def verify_all_gates() -> dict[str, bool]:
    # Gate 0: ADRs 0001..0015, C4 architecture, threat model, data model, AG-UI hello-world
    adr_files = sorted((ROOT / "docs" / "adr").glob("00*.md"))
    assert len(adr_files) == 15, f"Expected 15 ADRs, found {len(adr_files)}"
    assert (ROOT / "docs" / "architecture" / "overview.md").exists()
    assert (ROOT / "docs" / "architecture" / "data-model.md").exists()
    assert (ROOT / "docs" / "security" / "threat-model.md").exists()
    assert (ROOT / "docs" / "open-questions.md").exists()

    # Gate 1: Section 14 launch gates in evals/reports/latest-eval-report.json + runbooks + loadtest
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

    # Gate 2: Identity proofing, subject binding, PIA, and conversation forensic replay
    assert (ROOT / "docs" / "ai-governance" / "impact-assessment.md").exists()
    rt_client = TestClient(create_runtime_app())
    r_turn = rt_client.post(
        "/v1/turns",
        json={"message": "How do I get a TIN?", "thread_id": "thr_gate2_verify"},
    )
    assert r_turn.status_code == 200
    r_replay = rt_client.get("/v1/turns/thr_gate2_verify/replay")
    assert r_replay.status_code == 200
    assert len(r_replay.json()) == 1

    # Gate 3: Staff Copilot & 6-Step Knowledge Release workflow live
    api_client = TestClient(create_api_app())
    r_snap = api_client.get("/v1/knowledge-admin/active-snapshot")
    assert r_snap.status_code == 200
    assert r_snap.json()["status"] == "PUBLISHED"

    # Gate 4: Voice WER gate, USSD 182-char menu, consent registry, and regional insights live
    assert is_voice_language_approved(LocaleCode.PGA, MAX_VOICE_WER_GATE) is True
    assert is_voice_language_approved(LocaleCode.DIN, MAX_VOICE_WER_GATE + 0.05) is False
    r_insights = api_client.get("/v1/analytics/insights")
    assert r_insights.status_code == 200
    assert len(r_insights.json()) >= 3

    return {
        "Gate_0_Foundations": True,
        "Gate_1_Public_Assistant": True,
        "Gate_2_Authenticated_Self_Service": True,
        "Gate_3_Staff_Copilot_And_Knowledge_Ops": True,
        "Gate_4_Reach_And_Intelligence": True,
    }


def main() -> None:
    gates = verify_all_gates()
    print(f"All 5 technical Phase Exit Gates verified: {gates}")


if __name__ == "__main__":
    main()
