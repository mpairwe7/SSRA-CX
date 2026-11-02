#!/usr/bin/env python3
"""Live Call Receptionist & Cloudflare Voice/Speech Fallback Regression Suite against Hugging Face Space."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from typing import Any

import httpx

DEFAULT_HF_SPACE_URL = "https://landwind22-ssra-assist.hf.space"


def _post_json(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> tuple[int, dict[str, Any]]:
    resp = httpx.post(url, json=payload, headers=headers, timeout=timeout)
    try:
        data = resp.json()
    except Exception:
        data = {"raw_text": resp.text[:500]}
    return resp.status_code, data


def _get_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 20.0,
) -> tuple[int, dict[str, Any]]:
    resp = httpx.get(url, headers=headers, timeout=timeout)
    try:
        data = resp.json()
    except Exception:
        data = {"raw_text": resp.text[:500]}
    return resp.status_code, data


def run_regression_suite(base_url: str) -> dict[str, Any]:
    base = base_url.rstrip("/")
    results: list[dict[str, Any]] = []
    started_at = time.perf_counter()

    # 1. Check /api/voice/status fallback chain & Cloudflare configuration
    status_code, status_body = _get_json(f"{base}/api/voice/status", timeout=20.0)
    assert status_code == 200, f"/api/voice/status returned {status_code}: {status_body}"
    chain = status_body.get("fallback_chain") or {}
    cf_cfg = status_body.get("cloudflare_fallback") or {}
    asr_chain = chain.get("asr_chain") or []
    tts_chain = chain.get("tts_chain") or []
    assert len(asr_chain) >= 3 and asr_chain[0].get("provider") == "local_hf_cache", (
        f"Unexpected ASR fallback chain: {asr_chain}"
    )
    assert asr_chain[1].get("provider") == "cloudflare_workers_ai", (
        f"Expected Cloudflare Workers AI at ASR tier 2: {asr_chain}"
    )
    assert len(tts_chain) >= 4 and tts_chain[0].get("provider") == "local_hf_cache", (
        f"Unexpected TTS fallback chain: {tts_chain}"
    )
    assert tts_chain[2].get("provider") == "cloudflare_workers_ai", (
        f"Expected Cloudflare Workers AI at TTS tier 3: {tts_chain}"
    )
    assert cf_cfg.get("stt_fallback_active") is True, (
        f"Expected stt_fallback_active=True on target {base}: {cf_cfg}"
    )
    assert cf_cfg.get("tts_fallback_active") is True, (
        f"Expected tts_fallback_active=True on target {base}: {cf_cfg}"
    )
    results.append(
        {
            "check": "1_voice_status_and_fallback_chain",
            "status": "PASS",
            "stt_primary": cf_cfg.get("stt_model_primary"),
            "tts_primary": cf_cfg.get("tts_model_primary"),
            "tts_secondary": cf_cfg.get("tts_model_secondary"),
        }
    )

    # 2. Direct TTS synthesis via Cloudflare fallback (/api/voice/tts)
    tts_prompt = (
        "Welcome to the South Sudan Revenue Authority Call Receptionist. "
        "PAYE monthly returns are due by the fifteenth of the following month."
    )
    tts_code, tts_body = _post_json(
        f"{base}/api/voice/tts",
        {"text": tts_prompt, "locale": "en"},
        timeout=30.0,
    )
    assert tts_code == 200, f"/api/voice/tts returned {tts_code}: {tts_body}"
    assert tts_body.get("status") == "ok", f"TTS synthesis failed: {tts_body}"
    assert int(tts_body.get("audio_bytes_len") or 0) > 1000, f"TTS audio too short: {tts_body}"
    audio_b64 = str(tts_body.get("audio_base64") or "")
    assert len(audio_b64) > 1000, "Missing audio_base64 in TTS response"
    results.append(
        {
            "check": "2_cloudflare_tts_synthesis",
            "status": "PASS",
            "backend": tts_body.get("backend"),
            "voice": tts_body.get("voice"),
            "audio_bytes_len": tts_body.get("audio_bytes_len"),
            "latency_ms": tts_body.get("latency_ms"),
        }
    )

    # 3. Direct ASR round-trip transcription via Cloudflare fallback (/api/voice/asr)
    asr_code, asr_body = _post_json(
        f"{base}/api/voice/asr",
        {"audio_base64": audio_b64, "locale": "en", "duration_seconds": 8.0},
        timeout=30.0,
    )
    assert asr_code == 200, f"/api/voice/asr returned {asr_code}: {asr_body}"
    assert asr_body.get("status") == "ok", f"ASR transcription failed: {asr_body}"
    tx_text = str(asr_body.get("text") or "").strip()
    assert len(tx_text) >= 15, f"ASR transcript unexpectedly short: {asr_body}"
    results.append(
        {
            "check": "3_cloudflare_asr_roundtrip",
            "status": "PASS",
            "backend": asr_body.get("backend"),
            "model": asr_body.get("model"),
            "transcript": tx_text,
        }
    )

    # 4. Call Receptionist multi-turn regression suite (/api/voice/receptionist/turn)
    call_sid = f"hf_reg_{uuid.uuid4().hex[:10]}"

    # 4a. Consent via DTMF 1
    c1_code, c1 = _post_json(
        f"{base}/api/voice/receptionist/turn",
        {
            "session_id": call_sid,
            "dtmf_digit": "1",
            "locale": "en",
            "disclosure_finished": True,
        },
        timeout=20.0,
    )
    assert c1_code == 200 and c1.get("phase") == "active_ai", f"Consent turn failed: {c1}"
    assert c1.get("recording_consent_granted") is True, f"Consent not granted: {c1}"
    sess_tok = str(c1.get("session_token") or "")
    assert sess_tok, f"Missing session_token on created session: {c1}"
    assert c1.get("opening_prompts"), f"Missing opening_prompts on created session: {c1}"
    results.append(
        {
            "check": "4a_receptionist_dtmf_consent",
            "status": "PASS",
            "phase": c1.get("phase"),
            "recording_consent_granted": c1.get("recording_consent_granted"),
        }
    )

    # 4b. Grounded Tax Q&A (PAYE salary tax calculation + deadline) + TTS synthesis
    c2_code, c2 = _post_json(
        f"{base}/api/voice/receptionist/turn",
        {
            "session_id": call_sid,
            "session_token": sess_tok,
            "transcript": "How much is PAYE salary tax on 250000 SSP per month?",
            "locale": "en",
            "synthesize_tts": True,
        },
        timeout=35.0,
    )
    assert c2_code == 200, f"Tax Q&A turn failed ({c2_code}): {c2}"
    assert c2.get("decision_action") == "STREAM_ASR", f"Unexpected decision_action: {c2}"
    spoken_qna = str(c2.get("spoken_response_text") or "")
    assert "25000 SSP" in spoken_qna and "day 15" in spoken_qna, (
        f"Expected PAYE 25000 SSP and day 15 deadline in spoken reply: {spoken_qna}"
    )
    tts_turn = c2.get("tts") or {}
    assert int(tts_turn.get("audio_bytes_len") or 0) > 1000, f"Missing turn TTS audio: {tts_turn}"
    results.append(
        {
            "check": "4b_receptionist_grounded_paye_qna_with_tts",
            "status": "PASS",
            "intent": c2.get("intent"),
            "spoken_response_text": spoken_qna,
            "tts_backend": tts_turn.get("backend"),
            "tts_voice": tts_turn.get("voice"),
            "tts_audio_bytes": tts_turn.get("audio_bytes_len"),
        }
    )

    # 4c. Self-monitor / echo suppression guard
    c3_code, c3 = _post_json(
        f"{base}/api/voice/receptionist/turn",
        {
            "session_id": call_sid,
            "session_token": sess_tok,
            "transcript": spoken_qna,
            "elapsed_since_tts_end_ms": 250.0,
            "locale": "en",
        },
        timeout=20.0,
    )
    assert c3_code == 200 and c3.get("ignored_as_echo") is True, f"Echo guard failed: {c3}"
    results.append(
        {
            "check": "4c_receptionist_echo_guard",
            "status": "PASS",
            "ignored_as_echo": c3.get("ignored_as_echo"),
        }
    )

    # 4d. Backchannel suppression while assistant is speaking
    c4_code, c4 = _post_json(
        f"{base}/api/voice/receptionist/turn",
        {
            "session_id": call_sid,
            "session_token": sess_tok,
            "transcript": "uh huh",
            "assistant_speaking": True,
            "locale": "en",
        },
        timeout=20.0,
    )
    assert c4_code == 200 and c4.get("ignored_as_backchannel") is True, (
        f"Backchannel guard failed: {c4}"
    )
    results.append(
        {
            "check": "4d_receptionist_backchannel_guard",
            "status": "PASS",
            "ignored_as_backchannel": c4.get("ignored_as_backchannel"),
        }
    )

    # 4e. Spoken pace control ("speak slower")
    c5_code, c5 = _post_json(
        f"{base}/api/voice/receptionist/turn",
        {
            "session_id": call_sid,
            "session_token": sess_tok,
            "transcript": "please speak slower",
            "locale": "en",
        },
        timeout=20.0,
    )
    assert c5_code == 200 and c5.get("control_action_applied") == "slower", (
        f"Slower pace control failed: {c5}"
    )
    assert c5.get("speech_rate_slow") is True
    results.append(
        {
            "check": "4e_receptionist_pace_control_slower",
            "status": "PASS",
            "control_action_applied": c5.get("control_action_applied"),
            "speech_rate_slow": c5.get("speech_rate_slow"),
        }
    )

    # 4f. Spoken repeat control ("repeat that")
    c6_code, c6 = _post_json(
        f"{base}/api/voice/receptionist/turn",
        {
            "session_id": call_sid,
            "session_token": sess_tok,
            "transcript": "can you repeat that",
            "locale": "en",
        },
        timeout=20.0,
    )
    assert c6_code == 200 and c6.get("control_action_applied") == "repeat", (
        f"Repeat control failed: {c6}"
    )
    assert "25000 SSP" in str(c6.get("spoken_response_text") or "")
    results.append(
        {
            "check": "4f_receptionist_repeat_last_answer",
            "status": "PASS",
            "control_action_applied": c6.get("control_action_applied"),
            "spoken_response_text": c6.get("spoken_response_text"),
        }
    )

    # 4g. Warm transfer to human tax officer
    c7_code, c7 = _post_json(
        f"{base}/api/voice/receptionist/turn",
        {
            "session_id": call_sid,
            "session_token": sess_tok,
            "transcript": "please transfer me to a human tax officer",
            "locale": "en",
            "synthesize_tts": True,
        },
        timeout=30.0,
    )
    assert c7_code == 200 and c7.get("phase") == "transferred", f"Officer transfer failed: {c7}"
    assert c7.get("decision_action") == "WARM_TRANSFER_TO_OFFICER"
    results.append(
        {
            "check": "4g_receptionist_warm_officer_transfer",
            "status": "PASS",
            "phase": c7.get("phase"),
            "decision_action": c7.get("decision_action"),
            "spoken_response_text": c7.get("spoken_response_text"),
        }
    )

    # 4h. Callback request while waiting for officer + clean hangup
    _, s2_cb = _post_json(
        f"{base}/api/voice/receptionist/turn",
        {
            "session_id": call_sid,
            "session_token": sess_tok,
            "transcript": "I want a callback",
            "locale": "en",
        },
        timeout=20.0,
    )
    assert s2_cb.get("control_action_applied") == "callback_requested", f"Callback failed: {s2_cb}"
    assert s2_cb.get("needs_callback") is True

    _, s2_end = _post_json(
        f"{base}/api/voice/receptionist/turn",
        {
            "session_id": call_sid,
            "session_token": sess_tok,
            "transcript": "goodbye thank you",
            "locale": "en",
        },
        timeout=20.0,
    )
    assert s2_end.get("phase") == "ended", f"Hangup failed: {s2_end}"
    assert s2_end.get("control_action_applied") in ("caller_voice_hangup", "hangup")
    results.append(
        {
            "check": "4h_receptionist_callback_and_hangup",
            "status": "PASS",
            "needs_callback": s2_cb.get("needs_callback"),
            "final_phase": s2_end.get("phase"),
        }
    )

    elapsed_s = round(time.perf_counter() - started_at, 2)
    return {
        "target_url": base,
        "total_checks": len(results),
        "passed_checks": sum(1 for r in results if r["status"] == "PASS"),
        "elapsed_seconds": elapsed_s,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.environ.get("SSRA_HF_SPACE_URL", DEFAULT_HF_SPACE_URL),
        help="Base URL of the deployed SSRA Assist Hugging Face Space or local BFF.",
    )
    args = parser.parse_args()
    summary = run_regression_suite(args.url)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
