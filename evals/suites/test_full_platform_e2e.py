"""Full 12-Layer End-to-End Platform Integration Suite across Phases 0-4 (`evals/suites/test_full_platform_e2e.py`)."""

from __future__ import annotations

import hashlib
import hmac
import json

from fastapi.testclient import TestClient
from ssra_api import create_api_app
from ssra_channel_gateway import (
    CHANNEL_PORT_REGISTRY,
    create_channel_gateway_app,
    get_channel_port,
)
from ssra_core import AuthLevel, ChannelName, ConversationEvent, LocaleCode
from ssra_runtime import create_runtime_app
from ssra_runtime.gateway_server import create_agentgateway_app
from ssra_security import format_audit_event_as_cef, format_audit_event_as_ocsf


def test_end_to_end_12_layer_omnichannel_lifecycle() -> None:
    cgw_secret = "e2e-webhook-secret"
    cgw_client = TestClient(create_channel_gateway_app(webhook_secret=cgw_secret))
    api_client = TestClient(create_api_app())
    rt_client = TestClient(create_runtime_app())
    gw_client = TestClient(create_agentgateway_app(daily_usd_cap=150.0))

    # Layer 4: Channel Gateway verifies WhatsApp webhook HMAC & normalises to CloudEvents 1.0
    inbound_payload = {
        "message_id": "wamid.e2e.001",
        "channel": "whatsapp",
        "sender_ref": "taxpayer_deng",
        "text": "How much is PAYE on 250,000 SSP per month?",
        "locale": "en",
    }
    raw_bytes = json.dumps(inbound_payload).encode("utf-8")
    sig = "sha256=" + hmac.new(cgw_secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()
    r_wh = cgw_client.post(
        "/v1/webhooks/inbound",
        content=raw_bytes,
        headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )
    assert r_wh.status_code == 200
    cloud_evt = ConversationEvent.model_validate(r_wh.json()["cloud_event"])

    # Layer 5 & 6: Agent Runtime executes 11-node LangGraph turn through Governed MCP Gateway
    r_turn = rt_client.post(
        "/v1/turns",
        json={
            "message": cloud_evt.data.parts[0].value,
            "thread_id": cloud_evt.subject,
            "locale": cloud_evt.data.locale.value,
            "channel": cloud_evt.data.channel.value,
        },
    )
    assert r_turn.status_code == 200
    turn_data = r_turn.json()
    assert turn_data["tier"] == "T0"
    assert turn_data["answer"]["is_estimate"] is True
    assert any(n["value"] == "25000" for n in turn_data["answer"]["numbers"])

    # Principle 9: Forensic conversation replay reconstructs the turn & audit hash
    r_replay = rt_client.get(f"/v1/turns/{cloud_evt.subject}/replay")
    assert r_replay.status_code == 200
    replay_list = r_replay.json()
    assert len(replay_list) == 1
    assert replay_list[0]["audit_event_hash"] == turn_data["audit_event_hash"]

    # Layer 6 & 7: Direct agentgateway stateless MCP 2026-07-28 call with Subject Binding
    r_otp = api_client.post(
        "/v1/identity-link/verify-otp",
        json={"tin": "2003005678", "otp_code": "123456", "step_up": False},
    )
    assert r_otp.status_code == 200
    subject_ref = r_otp.json()["subject_ref"]

    r_mcp = gw_client.post(
        "/mcp",
        headers={
            "Mcp-Method": "tools/call",
            "Mcp-Name": "ledger",
            "X-SSRA-Auth-Level": AuthLevel.T1_TIN_BOUND.value,
            "X-SSRA-Subject-Ref": subject_ref,
        },
        json={"params": {"name": "get_balance", "arguments": {}}},
    )
    assert r_mcp.status_code == 200
    assert r_mcp.json()["structured_content"]["tin_masked"] == "••••5678"
    assert r_mcp.json()["structured_content"]["total_outstanding_ssp"] == "1450000"

    # Layer 11: ChannelPort formats outbound response for all 6 channels & SIEM exports audit
    assert len(CHANNEL_PORT_REGISTRY) == 6
    wa_port = get_channel_port(ChannelName.WHATSAPP)
    from ssra_core import Answer

    ans_model = Answer.model_validate(turn_data["answer"])
    wa_out = wa_port.format_outbound(ans_model)
    assert "https://etax.nra.gov.ss/" in wa_out["text"]

    # Layer 5 Core API: Staff Console inbox & Knowledge Snapshot status
    r_conv = api_client.post(
        "/v1/conversations",
        json={"channel": "whatsapp", "locale": LocaleCode.EN.value},
    )
    conv_id = r_conv.json()["id"]
    r_copilot = api_client.post(
        f"/v1/conversations/{conv_id}/copilot-draft",
        json={"taxpayer_question": "Where do I pay my assessment?"},
    )
    assert r_copilot.status_code == 200
    assert "https://etax.nra.gov.ss/" in r_copilot.json()["cited_reply_draft"]

    # Verify SIEM OCSF/CEF formatting
    from ssra_security import HashChainedAuditLedger

    ledger = HashChainedAuditLedger()
    ev = ledger.append(
        actor="ssra-e2e",
        on_behalf_of=subject_ref,
        action="e2e.verified",
        resource=f"thread://{cloud_evt.subject}",
        payload={"ok": True},
    )
    assert format_audit_event_as_ocsf(ev).severity == "SEV-4"
    assert "CEF:0|SSRA|SSRAAssist|" in format_audit_event_as_cef(ev)
