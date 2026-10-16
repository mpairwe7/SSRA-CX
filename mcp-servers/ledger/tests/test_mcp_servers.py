"""Contract tests for Stateless MCP 2026-07-28 servers (Section 8.1-8.4)."""

from __future__ import annotations

import pytest
from ssra_core import AuthLevel, McpErrorCode, SSRAError
from ssra_mcp import MCP_PROTOCOL_VERSION
from ssra_mcp_cases import create_cases_mcp_server
from ssra_mcp_customs import create_customs_mcp_server
from ssra_mcp_knowledge import create_knowledge_mcp_server
from ssra_mcp_ledger import create_ledger_mcp_server
from ssra_mcp_official_channels import create_official_channels_mcp_server
from ssra_mcp_payments_info import create_payments_info_mcp_server
from ssra_mcp_tax_facts import create_tax_facts_mcp_server
from ssra_mcp_tcc import create_tcc_mcp_server


def test_knowledge_and_tax_facts_stateless_t0_calls() -> None:
    kn = create_knowledge_mcp_server()
    listing = kn.handle_list_tools()
    assert listing["_meta"]["protocolVersion"] == MCP_PROTOCOL_VERSION
    assert listing["_meta"]["ttlMs"] == 300_000
    assert len(listing["tools"]) == 4

    search_res = kn.handle_call_tool(
        tool_name="search_knowledge",
        arguments={"query": "NRA TIN registration eTax", "language": "en"},
        bearer_token=None,
    )
    assert search_res["data_classification"] == "PUBLIC"
    assert len(search_res["structuredContent"]["results"]) >= 1

    tf = create_tax_facts_mcp_server()
    paye_res = tf.handle_call_tool(
        tool_name="calculate_paye_estimate",
        arguments={"gross_monthly_ssp": "250000"},
        bearer_token=None,
    )
    assert paye_res["structuredContent"]["estimated_tax_ssp"] == "25000"
    assert paye_res["structuredContent"]["is_estimate"] is True


def test_ledger_t1_enforces_subject_binding_and_blocks_anonymous_or_idor() -> None:
    ledger = create_ledger_mcp_server()

    # 1. Anonymous call to T1 tool is rejected
    with pytest.raises(SSRAError) as anon_exc:
        ledger.handle_call_tool(
            tool_name="get_balance",
            arguments={},
            bearer_token=None,
        )
    assert anon_exc.value.code == McpErrorCode.NOT_AUTHORIZED

    # 2. Exchanged RFC 8693 token for sub_taxpayer_deng_02 succeeds and masks TIN
    token = ledger.token_service.mint_exchanged_token(
        audience="mcp-ledger",
        auth_level=AuthLevel.T1_TIN_BOUND,
        subject_ref="sub_taxpayer_deng_02",
    )
    bal = ledger.handle_call_tool(
        tool_name="get_balance",
        arguments={},
        bearer_token=f"Bearer {token}",
    )
    assert bal["structuredContent"]["tin_masked"] == "••••5678"
    assert bal["structuredContent"]["total_outstanding_ssp"] == "1450000"

    # 3. Attempting to pass a victim's `tin` in arguments is rejected by JSON Schema 2020-12 (additionalProperties: false)
    with pytest.raises(SSRAError) as idor_exc:
        ledger.handle_call_tool(
            tool_name="get_balance",
            arguments={"tin": "1002001234"},
            bearer_token=f"Bearer {token}",
        )
    assert idor_exc.value.code == McpErrorCode.VALIDATION_FAILED


def test_official_channels_t2_report_scam_requires_confirmation_token() -> None:
    oc = create_official_channels_mcp_server()
    verify = oc.handle_call_tool(
        tool_name="verify_payment_account",
        arguments={"account_or_portal": "https://etax.nra.gov.ss/"},
        bearer_token=None,
    )
    assert verify["structuredContent"]["status"] == "OFFICIAL_VERIFIED"

    scam_check = oc.handle_call_tool(
        tool_name="verify_payment_account",
        arguments={"account_or_portal": "pay-tax-cash-collector.com"},
        bearer_token=None,
    )
    assert scam_check["structuredContent"]["status"] == "UNVERIFIED_OR_SCAM"

    # T2 write tool `report_scam` without confirmation_token is blocked
    t1_tok = oc.token_service.mint_exchanged_token(
        audience="mcp-official-channels",
        auth_level=AuthLevel.T1_TIN_BOUND,
        subject_ref="sub_taxpayer_amina_01",
    )
    scam_args = {
        "suspected_identifier": "+211999000111",
        "summary": "Caller demanded cash tax payment to personal mobile money",
    }
    with pytest.raises(SSRAError) as unconfirmed_exc:
        oc.handle_call_tool(
            tool_name="report_scam",
            arguments=scam_args,
            bearer_token=f"Bearer {t1_tok}",
        )
    assert unconfirmed_exc.value.code == McpErrorCode.NOT_AUTHORIZED

    # Issue single-use confirmation token and invoke
    cfm = oc.confirmation_manager.issue_token(
        conversation_id="thr_scam_01",
        tool_name="report_scam",
        arguments=scam_args,
        subject_ref="sub_taxpayer_amina_01",
    )
    confirmed_res = oc.handle_call_tool(
        tool_name="report_scam",
        arguments={
            **scam_args,
            "confirmation_token": cfm.token,
            "idempotency_key": cfm.idempotency_key,
        },
        bearer_token=f"Bearer {t1_tok}",
    )
    assert confirmed_res["structuredContent"]["status"] == "RECEIVED_BY_SSRA_SECOPS"


def test_phase2_customs_cases_and_t3_step_up_controls() -> None:
    customs = create_customs_mcp_server()
    tariff = customs.handle_call_tool(
        tool_name="lookup_tariff",
        arguments={"hs_code": "8703.23"},
        bearer_token=None,
    )
    assert tariff["structuredContent"]["duty_rate_percent"] == "20"

    duties = customs.handle_call_tool(
        tool_name="estimate_duties",
        arguments={"hs_code": "8703.23", "cif_value_usd": "10000"},
        bearer_token=None,
    )
    assert duties["structuredContent"]["is_estimate"] is True
    assert duties["structuredContent"]["boss_official_fx_rate_ssp_per_usd"] == "4500"

    # Cases subject-bound isolation
    cases = create_cases_mcp_server()
    tok_amina = cases.token_service.mint_exchanged_token(
        audience="mcp-cases",
        auth_level=AuthLevel.T1_TIN_BOUND,
        subject_ref="sub_taxpayer_amina_01",
    )
    c_status = cases.handle_call_tool(
        tool_name="get_case_status",
        arguments={"case_id": "case_seed_001"},
        bearer_token=f"Bearer {tok_amina}",
    )
    assert c_status["structuredContent"]["status"] == "IN_PROGRESS"

    # T3 tool (request_tcc) requires T3_STEP_UP + confirmation_token + upstream feature flag
    tcc = create_tcc_mcp_server(enable_t3_request_tcc=True)
    tok_t3 = tcc.token_service.mint_exchanged_token(
        audience="mcp-tcc",
        auth_level=AuthLevel.T3_STEP_UP,
        subject_ref="sub_taxpayer_amina_01",
    )
    tcc_args = {"purpose": "TENDER"}
    cfm_tcc = tcc.confirmation_manager.issue_token(
        conversation_id="thr_t3_01",
        tool_name="request_tcc",
        arguments=tcc_args,
        subject_ref="sub_taxpayer_amina_01",
    )
    tcc_res = tcc.handle_call_tool(
        tool_name="request_tcc",
        arguments={
            **tcc_args,
            "confirmation_token": cfm_tcc.token,
            "idempotency_key": cfm_tcc.idempotency_key,
        },
        bearer_token=f"Bearer {tok_t3}",
    )
    assert tcc_res["structuredContent"]["status"] == "SUBMITTED_ON_ETAX"

    # When upstream capability flag is disabled (default), T3 tool returns UPSTREAM_UNAVAILABLE
    pay_default = create_payments_info_mcp_server(enable_t3_payment_ref=False)
    tok_pay_t3 = pay_default.token_service.mint_exchanged_token(
        audience="mcp-payments-info",
        auth_level=AuthLevel.T3_STEP_UP,
        subject_ref="sub_taxpayer_amina_01",
    )
    pay_args = {"tax_type": "PAYE", "amount_ssp": "25000"}
    cfm_pay = pay_default.confirmation_manager.issue_token(
        conversation_id="thr_t3_02",
        tool_name="generate_payment_reference",
        arguments=pay_args,
        subject_ref="sub_taxpayer_amina_01",
    )
    with pytest.raises(SSRAError) as up_exc:
        pay_default.handle_call_tool(
            tool_name="generate_payment_reference",
            arguments={
                **pay_args,
                "confirmation_token": cfm_pay.token,
                "idempotency_key": cfm_pay.idempotency_key,
            },
            bearer_token=f"Bearer {tok_pay_t3}",
        )
    assert up_exc.value.code == McpErrorCode.UPSTREAM_UNAVAILABLE


def test_mcp_2026_07_28_tasks_extension_and_deprecated_features_rejected() -> None:
    from fastapi.testclient import TestClient

    kn = create_knowledge_mcp_server()
    client = TestClient(kn.create_fastapi_app())

    # 1. Deprecated Roots/Sampling/Logging features are rejected per Section 8.1
    for deprecated_method in ("roots/list", "sampling/createMessage", "logging/setLevel"):
        r_dep = client.post(
            "/mcp",
            headers={"Mcp-Method": deprecated_method, "Mcp-Name": "knowledge"},
            json={"method": deprecated_method, "params": {}},
        )
        assert r_dep.status_code == 400
        assert r_dep.json()["error"]["code"] == "VALIDATION_FAILED"

    # 2. Tasks extension (tasks/create, tasks/get, tasks/cancel) works
    r_create = client.post(
        "/mcp",
        headers={"Mcp-Method": "tasks/create", "Mcp-Name": "knowledge"},
        json={"method": "tasks/create", "params": {"operation": "reindex_snapshot"}},
    )
    assert r_create.status_code == 200
    task_id = r_create.json()["task"]["taskId"]

    r_cancel = client.post(
        "/mcp",
        headers={"Mcp-Method": "tasks/cancel", "Mcp-Name": "knowledge"},
        json={"method": "tasks/cancel", "params": {"taskId": task_id}},
    )
    assert r_cancel.status_code == 200
    assert r_cancel.json()["task"]["status"] == "CANCELLED"

    # 3. State-Handle Hijacking (MCP 2026-07-28): another subject cannot access or cancel taskId
    tok_other = kn.token_service.mint_exchanged_token(
        audience="mcp-knowledge",
        auth_level=AuthLevel.T1_TIN_BOUND,
        subject_ref="sub_attacker_99",
    )
    r_hijack = client.post(
        "/mcp",
        headers={
            "Mcp-Method": "tasks/get",
            "Mcp-Name": "knowledge",
            "Authorization": f"Bearer {tok_other}",
        },
        json={"method": "tasks/get", "params": {"taskId": task_id}},
    )
    assert r_hijack.status_code == 403
    assert "WWW-Authenticate" in r_hijack.headers


def test_mcp_server_template_generator_blocks_t4_and_renders_valid_code() -> None:
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / "tools"))
    from generate_mcp_server import render_mcp_server_code  # type: ignore[import-not-found]

    code = render_mcp_server_code(
        server_name="eservices-bridge",
        tool_name="verify_business_registry",
        tool_description="Verify Ministry of Justice business registry entry.",
        tier="T0",
    )
    assert "create_eservices_bridge_mcp_server" in code
    assert "verify_business_registry" in code

    with pytest.raises(ValueError, match="T4 is human-only"):
        render_mcp_server_code(
            server_name="waiver-bot",
            tool_name="grant_waiver",
            tool_description="Forbidden T4 tool",
            tier="T4",
        )


def test_mcp_output_sanitiser_redacts_unallowlisted_urls_and_wraps_data() -> None:
    from ssra_mcp import scrub_untrusted_urls_and_cap_length, wrap_tool_result_as_untrusted_data

    cleaned = scrub_untrusted_urls_and_cap_length(
        "Official https://etax.nra.gov.ss/ vs phishing https://evil-tax-scam.example.org/pay"
    )
    assert "https://etax.nra.gov.ss/" in cleaned
    assert "evil-tax-scam" not in cleaned
    assert "[REDACTED_UNALLOWLISTED_URL]" in cleaned

    wrapped = wrap_tool_result_as_untrusted_data(
        "verify_sender",
        {"url": "https://evil.example.com", "official": "https://etax.nra.gov.ss/"},
    )
    assert wrapped.startswith('<untrusted_tool_result tool="verify_sender">')
    assert "[REDACTED_UNALLOWLISTED_URL]" in wrapped


def test_remaining_mcp_catalog_tools_and_hybrid_retrieval_postprocessing() -> None:
    from ssra_mcp_appointments import create_appointments_mcp_server
    from ssra_mcp_notifications import create_notifications_mcp_server
    from ssra_mcp_taxpayer import create_taxpayer_mcp_server
    from ssra_runtime.retrieval import postprocess_retrieved_chunks

    kn = create_knowledge_mcp_server()
    sec = kn.handle_call_tool(
        tool_name="get_section",
        arguments={"section_anchor": "Part-I-Sec-1-TIN-Registration"},
        bearer_token=None,
    )
    assert sec["structuredContent"]["section"]["id"] == "chk_etax_tin_01"

    forms = kn.handle_call_tool(tool_name="list_forms", arguments={}, bearer_token=None)
    assert len(forms["structuredContent"]["forms"]) == 4

    office = kn.handle_call_tool(
        tool_name="get_office_info",
        arguments={"office_code": "NIMULE_CUSTOMS"},
        bearer_token=None,
    )
    assert office["structuredContent"]["office"]["city"] == "Nimule"

    tf = create_tax_facts_mcp_server()
    facts = tf.handle_call_tool(
        tool_name="list_tax_facts",
        arguments={"prefix": "paye."},
        bearer_token=None,
    )
    assert len(facts["structuredContent"]["facts"]) >= 5

    wht = tf.handle_call_tool(
        tool_name="calculate_withholding_estimate",
        arguments={"gross_amount_ssp": "500000", "category": "rent"},
        bearer_token=None,
    )
    assert wht["structuredContent"]["withholding_tax_ssp"] == "50000"

    tp = create_taxpayer_mcp_server()
    tok_tp = tp.token_service.mint_exchanged_token(
        audience="mcp-taxpayer",
        auth_level=AuthLevel.T1_TIN_BOUND,
        subject_ref="sub_taxpayer_amina_01",
    )
    prof = tp.handle_call_tool(
        tool_name="get_profile_masked",
        arguments={},
        bearer_token=f"Bearer {tok_tp}",
    )
    assert prof["structuredContent"]["tin_masked"] == "••••1234"

    ledger = create_ledger_mcp_server()
    tok_led = ledger.token_service.mint_exchanged_token(
        audience="mcp-ledger",
        auth_level=AuthLevel.T1_TIN_BOUND,
        subject_ref="sub_taxpayer_amina_01",
    )
    for t_name in ("get_filing_status", "list_assessments", "list_payments"):
        res = ledger.handle_call_tool(
            tool_name=t_name,
            arguments={},
            bearer_token=f"Bearer {tok_led}",
        )
        assert res["structuredContent"]["tin_masked"] == "••••1234"

    appt = create_appointments_mcp_server()
    slots = appt.handle_call_tool(
        tool_name="list_slots",
        arguments={"office_code": "JUBA_HQ"},
        bearer_token=None,
    )
    assert len(slots["structuredContent"]["slots"]) == 2

    tok_appt = appt.token_service.mint_exchanged_token(
        audience="mcp-appointments",
        auth_level=AuthLevel.T1_TIN_BOUND,
        subject_ref="sub_taxpayer_amina_01",
    )
    cancel_args = {"appointment_id": "appt_seed_01"}
    cfm_cancel = appt.confirmation_manager.issue_token(
        conversation_id="thr_c1",
        tool_name="cancel_appointment",
        arguments=cancel_args,
        subject_ref="sub_taxpayer_amina_01",
    )
    cancelled = appt.handle_call_tool(
        tool_name="cancel_appointment",
        arguments={
            **cancel_args,
            "confirmation_token": cfm_cancel.token,
            "idempotency_key": cfm_cancel.idempotency_key,
        },
        bearer_token=f"Bearer {tok_appt}",
    )
    assert cancelled["structuredContent"]["status"] == "CANCELLED"

    ntf = create_notifications_mcp_server()
    tok_ntf = ntf.token_service.mint_exchanged_token(
        audience="mcp-notifications",
        auth_level=AuthLevel.T1_TIN_BOUND,
        subject_ref="sub_taxpayer_amina_01",
    )
    ntf_args = {"template_id": "ssra_filing_reminder_v1", "consent_verified": True}
    cfm_ntf = ntf.confirmation_manager.issue_token(
        conversation_id="thr_n1",
        tool_name="send_template_message",
        arguments=ntf_args,
        subject_ref="sub_taxpayer_amina_01",
    )
    sent = ntf.handle_call_tool(
        tool_name="send_template_message",
        arguments={
            **ntf_args,
            "confirmation_token": cfm_ntf.token,
            "idempotency_key": cfm_ntf.idempotency_key,
        },
        bearer_token=f"Bearer {tok_ntf}",
    )
    assert sent["structuredContent"]["status"] == "QUEUED_WITH_VERIFICATION_FOOTER"

    ranked = postprocess_retrieved_chunks(
        [sec["structuredContent"]["section"]],
        query="TIN registration",
        locale="en",
    )
    assert len(ranked) == 1

    # Verify official South Sudan portals, support email & eTax helpdesk numbers in official-channels
    oc = create_official_channels_mcp_server()
    for official_id in (
        "https://www.nra.gov.ss/",
        "https://business.eservices.gov.ss/",
        "https://customs.eservices.gov.ss/",
        "https://ecustoms.nra.gov.ss/",
        "https://www.trade.eservices.gov.ss/",
        "https://mofp.gov.ss/",
        "https://boss.gov.ss/",
        "support@nra.gov.ss",
        "+211 918806493",
    ):
        v_res = oc.handle_call_tool(
            tool_name="verify_sender",
            arguments={"sender_id_or_url": official_id},
            bearer_token=None,
        )
        assert v_res["structuredContent"]["status"] == "OFFICIAL_VERIFIED"
