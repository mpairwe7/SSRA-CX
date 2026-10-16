"""Tests for services/channel-gateway (WhatsApp HMAC, SMS GSM-7 vs UCS-2, and Phase 4 USSD 182-char menu engine)."""

from __future__ import annotations

import hashlib
import hmac
import json

from fastapi.testclient import TestClient
from ssra_channel_gateway import (
    CHANNEL_PORT_REGISTRY,
    USSD_MAX_CHARS,
    compute_sms_segments,
    create_channel_gateway_app,
    get_channel_port,
    prepare_whatsapp_outbound_message,
    render_ussd_screen,
)


def test_sms_segmentation_gsm7_vs_arabic_ucs2() -> None:
    en_metrics = compute_sms_segments("SSRA eTax filing is due by the 15th.")
    assert en_metrics["encoding"] == "GSM-7"
    assert en_metrics["per_segment_limit"] == 160
    assert en_metrics["segments"] == 1

    ar_metrics = compute_sms_segments(
        "هيئة إيرادات جنوب السودان: يتم التسجيل عبر بوابة الضرائب الرسمية"
    )
    assert ar_metrics["encoding"] == "UCS-2"
    assert ar_metrics["per_segment_limit"] == 70
    assert ar_metrics["segments"] == 1


def test_webhook_hmac_verification_and_deduplication() -> None:
    secret = "test-secret"
    client = TestClient(create_channel_gateway_app(webhook_secret=secret))
    payload = {
        "message_id": "wamid.001",
        "channel": "whatsapp",
        "sender_ref": "anon_hash_01",
        "text": "How do I get a TIN?",
        "locale": "en",
    }
    raw = json.dumps(payload).encode("utf-8")
    sig = "sha256=" + hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()

    r1 = client.post(
        "/v1/webhooks/inbound",
        content=raw,
        headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )
    assert r1.status_code == 200
    assert r1.json()["status"] == "normalised"
    assert r1.json()["cloud_event"]["specversion"] == "1.0"

    # Duplicate delivery is dropped
    r2 = client.post(
        "/v1/webhooks/inbound",
        content=raw,
        headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "deduplicated_drop"


def test_phase4_ussd_deterministic_menu_182_char_limit_and_sms_followup() -> None:
    client = TestClient(create_channel_gateway_app())

    for opt in ("", "1", "2", "3", "4", "9", "0", "99"):
        screen = render_ussd_screen(session_id="ussd_01", ussd_input=opt)
        assert len(screen.screen_text) <= USSD_MAX_CHARS

    # Option 9 triggers SMS follow-up
    r_sms = client.post(
        "/v1/ussd/session",
        json={"session_id": "ussd_01", "ussd_input": "1*9", "elapsed_seconds": 15},
    )
    assert r_sms.status_code == 200
    assert r_sms.json()["send_sms_followup"] is True
    assert r_sms.json()["char_length"] <= 182

    # Operator timeout (> 120s) terminates cleanly
    r_timeout = client.post(
        "/v1/ussd/session",
        json={"session_id": "ussd_01", "ussd_input": "1", "elapsed_seconds": 150},
    )
    assert r_timeout.status_code == 200
    assert r_timeout.json()["response_type"] == "END"


def test_whatsapp_24h_service_window_and_template_consent_gate() -> None:
    from datetime import UTC, datetime, timedelta

    import pytest
    from ssra_core import SSRAError

    now = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)

    # 1. Within 24h window: free service reply + anti-impersonation footer attached
    in_window = prepare_whatsapp_outbound_message(
        recipient_ref="sub_01",
        body_text="Your PAYE filing is due on day 15.",
        last_inbound_at=now - timedelta(hours=2),
        opt_in_consent_active=False,
        now=now,
    )
    assert in_window.within_24h_window is True
    assert in_window.estimated_cost_usd == 0.0
    assert "https://etax.nra.gov.ss/" in in_window.formatted_body

    # 2. Outside 24h window without consent is blocked
    with pytest.raises(SSRAError):
        prepare_whatsapp_outbound_message(
            recipient_ref="sub_01",
            body_text="Reminder",
            last_inbound_at=now - timedelta(hours=30),
            opt_in_consent_active=False,
            template_id="ssra_filing_reminder_v1",
            now=now,
        )

    # 3. Outside 24h window with consent + approved template succeeds
    out_window = prepare_whatsapp_outbound_message(
        recipient_ref="sub_01",
        body_text="Monthly PAYE reminder.",
        last_inbound_at=now - timedelta(hours=30),
        opt_in_consent_active=True,
        template_id="ssra_filing_reminder_v1",
        now=now,
    )
    assert out_window.within_24h_window is False
    assert out_window.estimated_cost_usd == 0.014

    # 4. All 6 channels registered in CHANNEL_PORT_REGISTRY with capability bounds
    from ssra_core import Answer, AnswerSegment, ChannelName

    sample_ans = Answer(
        segments=[
            AnswerSegment(text="Official portal is https://etax.nra.gov.ss/", citation_ids=[])
        ],
        citations=[],
        numbers=[],
        is_estimate=False,
        abstained=False,
    )
    assert len(CHANNEL_PORT_REGISTRY) == 6
    for ch in ChannelName:
        port = get_channel_port(ch)
        formatted = port.format_outbound(sample_ans)
        assert formatted["channel"] == ch.value
