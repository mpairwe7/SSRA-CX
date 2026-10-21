"""Hypothesis Property-Based API Fuzzing, Field-Officer Assist & Numeric Provenance Boundary Suite (Sections 3, 10.5, 14.1)."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from ssra_api import create_api_app
from ssra_core import (
    Answer,
    AnswerSegment,
    Citation,
    NumericClaim,
    NumericUnit,
)
from ssra_runtime import create_runtime_app
from ssra_runtime.guardrails import validate_numeric_provenance
from ssra_testing import AsgiTestClient

_api_client = AsgiTestClient(create_api_app())
_rt_client = AsgiTestClient(create_runtime_app())


@settings(max_examples=25)
@given(
    amount_int=st.integers(min_value=1, max_value=999_999_999),
    hallucinated_delta=st.integers(min_value=1, max_value=10_000),
)
def test_property_numeric_provenance_always_catches_any_deviating_number(
    amount_int: int, hallucinated_delta: int
) -> None:
    true_str = str(amount_int)
    fake_str = str(amount_int + hallucinated_delta)
    cit = Citation(
        id="cit_prop",
        snapshot_version="2026.10.1",
        doc_title="Taxation Act 2009",
        section_anchor="Part-IV-Sec-18",
        effective_from="2024-07-01",
    )

    # 1. Exact match with tool artifact passes
    good_ans = Answer(
        segments=[
            AnswerSegment(text=f"Estimated tax is {true_str} SSP.", citation_ids=["cit_prop"])
        ],
        citations=[cit],
        numbers=[NumericClaim(value=true_str, unit=NumericUnit.SSP, source_ref="calc.tax")],
        is_estimate=True,
        abstained=False,
    )
    assert (
        validate_numeric_provenance(
            good_ans, tool_artifacts=[{"estimated_tax_ssp": true_str}]
        ).passed
        is True
    )

    # 2. Any hallucinated deviation in prose is blocked
    bad_ans = Answer(
        segments=[
            AnswerSegment(text=f"Estimated tax is {fake_str} SSP.", citation_ids=["cit_prop"])
        ],
        citations=[cit],
        numbers=[NumericClaim(value=true_str, unit=NumericUnit.SSP, source_ref="calc.tax")],
        is_estimate=True,
        abstained=False,
    )
    assert (
        validate_numeric_provenance(
            bad_ans, tool_artifacts=[{"estimated_tax_ssp": true_str}]
        ).passed
        is False
    )


def test_field_officer_assist_requires_staff_passkey_and_audits_tariff_check() -> None:
    # 1. Non-passkey auth level is rejected with 403
    r_denied = _rt_client.post(
        "/v1/field-officer/assist",
        json={
            "officer_id": "off_nimule_01",
            "office_code": "NIMULE_CUSTOMS",
            "auth_level": "T1_TIN_BOUND",
            "task_type": "TARIFF_CHECK",
            "hs_code": "8703.23",
            "cif_value_usd": "10000",
        },
    )
    assert r_denied.status_code == 403

    # 2. STAFF_PASSKEY succeeds and returns official BoSS FX-converted duty guidance + audit hash
    r_ok = _rt_client.post(
        "/v1/field-officer/assist",
        json={
            "officer_id": "off_nimule_01",
            "office_code": "NIMULE_CUSTOMS",
            "auth_level": "STAFF_PASSKEY",
            "task_type": "TARIFF_CHECK",
            "hs_code": "8703.23",
            "cif_value_usd": "10000",
        },
    )
    assert r_ok.status_code == 200
    body = r_ok.json()
    assert "4500" in body["cited_guidance"]
    assert len(body["audit_event_hash"]) == 64


@settings(max_examples=20)
@given(
    channel=st.sampled_from(["web", "whatsapp", "sms", "ussd", "voice"]),
    locale=st.sampled_from(["en", "pga", "ar", "din", "nus", "bfa", "zne", "shk"]),
)
def test_api_fuzz_create_conversation_across_all_channels_and_locales(
    channel: str, locale: str
) -> None:
    res = _api_client.post(
        "/v1/conversations",
        json={"channel": channel, "locale": locale, "office_code": "JUBA_HQ"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["channel"] == channel
    assert data["locale"] == locale
    assert "traceparent" in res.headers
