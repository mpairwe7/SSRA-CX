"""Phase 4 Voice/IVR ASR, TTS/MMS, Call Receptionist, Officer Call Brief & Lobby Engine (Section 11, CVE-2026-54233)."""

from __future__ import annotations

import base64
import difflib
import hashlib
import hmac
import json
import math
import os
import re
import struct
import time
import unicodedata
import uuid
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import Any, Literal, Protocol

from ssra_core import (
    MAX_SPOKEN_SENTENCES,
    LocaleCode,
    McpErrorCode,
    SSRAError,
    compose_spoken_reply,
    count_sms_segments,
    fit_text,
    sms_encoding,
)
from ssra_core import split_sentences as split_tts_sentences
from ssra_security import redact_pii

# Launch a language on voice only after its word-error rate on SSRA test sets meets the gate (<= 0.12)
MAX_VOICE_WER_GATE: float = 0.12
MIN_UTTERANCE_ASR_CONFIDENCE: float = 0.75
MAX_VOICE_SPOKEN_SENTENCES: int = MAX_SPOKEN_SENTENCES
# The SMS follow-up budget is 160 characters: one GSM-7 segment, or up to three UCS-2 segments
# (Arabic). The result reports the real encoding and segment count; the per-language segment budget
# is for SSRA's channel owners (OQ-007).
MAX_SMS_CONTINUATION_CHARS: int = 160

# CVE-2026-54233: Cap decoded float32 PCM output at 15.36 MB (120s @ 16kHz mono float32) to prevent OPUS decompression bombs
MAX_DECODED_PCM_BYTES: int = 15_360_000
MAX_COMPRESSED_AUDIO_BYTES: int = 2_097_152

# ASR model selection per Section 11: vLLM Whisper Large v3 Turbo for en/ar; HF Meta MMS/Omnilingual ASR for pga & local languages
ASR_MODEL_BY_LOCALE: dict[LocaleCode, str] = {
    LocaleCode.EN: "openai/whisper-large-v3-turbo",
    LocaleCode.AR: "openai/whisper-large-v3-turbo",
    LocaleCode.PGA: "facebook/omnilingual-asr-mms-1b-all",
    LocaleCode.DIN: "facebook/omnilingual-asr-mms-1b-all",
    LocaleCode.NUS: "facebook/omnilingual-asr-mms-1b-all",
    LocaleCode.BFA: "facebook/omnilingual-asr-mms-1b-all",
    LocaleCode.ZNE: "facebook/omnilingual-asr-mms-1b-all",
    LocaleCode.SHK: "facebook/omnilingual-asr-mms-1b-all",
}

# TTS (Text-to-Speech) model selection via HuggingFace offline cache (`facebook/mms-tts-*` VITS checkpoints)
TTS_MODEL_BY_LOCALE: dict[LocaleCode, str] = {
    LocaleCode.EN: "facebook/mms-tts-eng",
    LocaleCode.AR: "facebook/mms-tts-ara",
    LocaleCode.PGA: "facebook/mms-tts-ara",
    LocaleCode.DIN: "facebook/mms-tts-dik",
    LocaleCode.NUS: "facebook/mms-tts-nus",
    LocaleCode.BFA: "facebook/mms-tts-bfa",
    LocaleCode.ZNE: "facebook/mms-tts-zne",
    LocaleCode.SHK: "facebook/mms-tts-shk",
}


@dataclass(frozen=True)
class VoiceSessionDecision:
    session_id: str
    locale: LocaleCode
    asr_engine: str
    tts_engine: str
    recording_enabled: bool
    action: str  # STREAM_ASR | CLARIFY_INTENT_SPOKEN | DTMF_MENU | WARM_TRANSFER_TO_OFFICER
    warm_transfer_summary: str | None = None
    # True when the caller talked over the assistant: stop playback and cancel the reply being generated.
    cancel_active_reply: bool = False
    asr_rejected_reason: str | None = None


@dataclass(frozen=True)
class HfVoiceModelDescriptor:
    locale: LocaleCode
    asr_repo_id: str
    tts_repo_id: str
    serving_backend: str
    hf_cache_dir: str
    local_files_only: bool


def resolve_hf_voice_model_cache(
    locale: LocaleCode,
    *,
    hf_home: str = "/home/developer/huggingface_cache",
) -> HfVoiceModelDescriptor:
    """Resolve local HuggingFace cache paths for ASR (`vLLM` / `MMS`) and TTS (`MMS-TTS`) with `local_files_only=True`."""
    asr_repo = ASR_MODEL_BY_LOCALE[locale]
    tts_repo = TTS_MODEL_BY_LOCALE[locale]
    backend = (
        "vllm-audio-transcriptions"
        if locale in (LocaleCode.EN, LocaleCode.AR)
        else "hf-mms-offline"
    )
    return HfVoiceModelDescriptor(
        locale=locale,
        asr_repo_id=asr_repo,
        tts_repo_id=tts_repo,
        serving_backend=backend,
        hf_cache_dir=f"{hf_home.rstrip('/')}/hub",
        local_files_only=True,
    )


def validate_audio_pcm_expansion_budget(
    *,
    compressed_bytes: int,
    duration_seconds: float,
    sample_rate_hz: int = 16000,
) -> int:
    """Guard vLLM /v1/audio/transcriptions against OPUS/float32 PCM decompression bombs (CVE-2026-54233)."""
    if compressed_bytes <= 0 or compressed_bytes > MAX_COMPRESSED_AUDIO_BYTES:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            f"Compressed audio size ({compressed_bytes} bytes) exceeds 2 MB limit",
            status_code=413,
        )
    if duration_seconds <= 0 or sample_rate_hz <= 0:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "Audio duration_seconds and sample_rate_hz must be positive",
            status_code=400,
        )
    estimated_pcm_bytes = int(duration_seconds * sample_rate_hz * 4)  # float32 = 4 bytes/sample
    if estimated_pcm_bytes > MAX_DECODED_PCM_BYTES:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            f"Decoded PCM expansion ({estimated_pcm_bytes} bytes) exceeds CVE-2026-54233 safety cap ({MAX_DECODED_PCM_BYTES} bytes)",
            status_code=413,
        )
    return estimated_pcm_bytes


def synthesize_tts_speech_envelope(
    *,
    text: str,
    locale: LocaleCode,
    voice: str | None = None,
    hf_home: str = "/home/developer/huggingface_cache",
    recommended_tone: Literal[
        "standard_clear",
        "reassuring_step_by_step",
        "concise_urgent",
        "empathetic_deescalation",
    ] = "standard_clear",
) -> dict[str, Any]:
    """Build deterministic offline HuggingFace MMS-TTS / Orpheus synthesis envelope with locale-validated speaker tag and EQ prosody modulation."""
    desc = resolve_hf_voice_model_cache(locale, hf_home=hf_home)
    resolved_voice = resolve_tts_voice(locale.value, voice)
    speaking_rate = (
        0.92 if recommended_tone in ("reassuring_step_by_step", "empathetic_deescalation") else 1.0
    )
    sentence_pause_ms = (
        350 if recommended_tone in ("reassuring_step_by_step", "empathetic_deescalation") else 200
    )
    return {
        "tts_model": desc.tts_repo_id,
        "voice": resolved_voice,
        "locale": locale.value,
        "hf_cache_dir": desc.hf_cache_dir,
        "local_files_only": desc.local_files_only,
        "sample_rate_hz": 16000,
        "text_length": len(text.strip()),
        "recommended_tone": recommended_tone,
        "speaking_rate": speaking_rate,
        "sentence_pause_ms": sentence_pause_ms,
    }


def build_voice_prosody_eq_metadata(
    *,
    barge_in_count: int = 0,
    rms_energy_delta: float = 0.0,
    speech_rate_ratio: float = 1.0,
    consecutive_low_confidence_turns: int = 0,
) -> dict[str, str]:
    """Serialize voice acoustic prosody features into string metadata for `ConversationEvent.data.metadata`."""
    return {
        "voice_barge_in_count": str(max(0, barge_in_count)),
        "voice_rms_energy_delta": f"{max(0.0, rms_energy_delta):.2f}",
        "voice_speech_rate_ratio": f"{max(0.5, speech_rate_ratio):.2f}",
        "consecutive_low_confidence_turns": str(max(0, consecutive_low_confidence_turns)),
    }


@dataclass(frozen=True)
class VoiceWerEvidence:
    """A measured word-error rate for one language on a named SSRA test set (OQ-008)."""

    locale: LocaleCode
    word_error_rate: float
    test_set: str
    measured_on: date
    utterance_count: int


# Governed launch evidence for voice languages. An entry needs an SSRA-approved measurement on an
# SSRA test set (OQ-008). There is none yet, so every language routes callers to an officer.
APPROVED_VOICE_WER_EVIDENCE: Mapping[LocaleCode, VoiceWerEvidence] = MappingProxyType({})


def _wer_gate_failure(
    locale: LocaleCode, evidence: Mapping[LocaleCode, VoiceWerEvidence]
) -> str | None:
    """Return why a language may not run on voice, or None when its evidence meets the gate."""
    record = evidence.get(locale)
    if (
        record is None
        or record.locale != locale
        or record.utterance_count <= 0
        or not record.test_set.strip()
        or not math.isfinite(record.word_error_rate)
        or record.word_error_rate < 0.0
    ):
        return f"no approved word-error-rate evidence for {locale.value} (OQ-008)"
    if record.word_error_rate > MAX_VOICE_WER_GATE:
        return (
            f"{locale.value} word-error rate {record.word_error_rate:.2f} on {record.test_set} "
            f"is above the {MAX_VOICE_WER_GATE:.2f} gate"
        )
    return None


def is_voice_language_approved(
    locale: LocaleCode,
    evidence: Mapping[LocaleCode, VoiceWerEvidence] = APPROVED_VOICE_WER_EVIDENCE,
) -> bool:
    """Return whether governed word-error-rate evidence allows this language on voice."""
    return _wer_gate_failure(locale, evidence) is None


@dataclass(frozen=True)
class WhisperSegmentSignals:
    """Per-segment signals reported by Whisper-family decoders."""

    no_speech_prob: float
    avg_logprob: float
    compression_ratio: float


# openai/whisper `transcribe()` defaults. A segment is silence when no_speech_prob > 0.6 and
# avg_logprob < -1.0, and unreliable when compression_ratio > 2.4 (repetition) or avg_logprob < -1.0.
WHISPER_NO_SPEECH_THRESHOLD: float = 0.6
WHISPER_LOGPROB_THRESHOLD: float = -1.0
WHISPER_COMPRESSION_RATIO_THRESHOLD: float = 2.4


def assess_whisper_segment(
    signals: WhisperSegmentSignals,
) -> Literal["accept", "no_speech", "unreliable"]:
    """Classify a transcript so text Whisper invents on silence or noise never reaches the runtime."""
    values = (signals.no_speech_prob, signals.avg_logprob, signals.compression_ratio)
    if not all(math.isfinite(value) for value in values):
        return "unreliable"
    if (
        signals.no_speech_prob > WHISPER_NO_SPEECH_THRESHOLD
        and signals.avg_logprob < WHISPER_LOGPROB_THRESHOLD
    ):
        return "no_speech"
    if (
        signals.compression_ratio > WHISPER_COMPRESSION_RATIO_THRESHOLD
        or signals.avg_logprob < WHISPER_LOGPROB_THRESHOLD
    ):
        return "unreliable"
    return "accept"


_ASR_REJECTION_REASONS: dict[str, str] = {
    "no_speech": "no speech detected",
    "unreliable": "transcript is unreliable (repetition or low log-probability)",
}


def route_voice_turn(
    *,
    session_id: str,
    locale: LocaleCode,
    recording_consent_granted: bool,
    wer_evidence: Mapping[LocaleCode, VoiceWerEvidence] = APPROVED_VOICE_WER_EVIDENCE,
    dtmf_digit: str | None = None,
    barge_in_detected: bool = False,
    utterance_confidence: float = 0.95,
    consecutive_low_confidence_turns: int = 0,
    enable_spoken_clarify_gate: bool = False,
    whisper_signals: WhisperSegmentSignals | None = None,
) -> VoiceSessionDecision:
    """Route a voice turn across ASR, spoken ClarifyGate, hybrid DTMF disambiguation, and progressive warm transfer.

    A barge-in sets ``cancel_active_reply`` on every decision. A Whisper transcript judged silent or
    unreliable is never streamed to the runtime; the caller gets the keypad menu instead.
    """
    asr_verdict = (
        assess_whisper_segment(whisper_signals) if whisper_signals is not None else "accept"
    )
    asr_rejected_reason = _ASR_REJECTION_REASONS.get(asr_verdict)
    effective_confidence = utterance_confidence if asr_verdict == "accept" else 0.0
    asr_engine = ASR_MODEL_BY_LOCALE[locale]
    tts_engine = TTS_MODEL_BY_LOCALE[locale]

    transfer_reasons = [
        reason
        for reason in (
            "caller pressed 0 for an officer" if dtmf_digit == "0" else None,
            _wer_gate_failure(locale, wer_evidence),
            f"{consecutive_low_confidence_turns} consecutive low-confidence turns"
            if consecutive_low_confidence_turns >= 2
            else None,
        )
        if reason
    ]
    if transfer_reasons:
        return VoiceSessionDecision(
            session_id=session_id,
            locale=locale,
            asr_engine=asr_engine,
            tts_engine=tts_engine,
            recording_enabled=recording_consent_granted,
            cancel_active_reply=barge_in_detected,
            asr_rejected_reason=asr_rejected_reason,
            action="WARM_TRANSFER_TO_OFFICER",
            warm_transfer_summary=(
                f"Warm transfer from IVR ({locale.value}): {'; '.join(transfer_reasons)}."
            ),
        )

    should_clarify = (
        enable_spoken_clarify_gate
        and dtmf_digit is None
        and 0.60 <= effective_confidence < MIN_UTTERANCE_ASR_CONFIDENCE
        and consecutive_low_confidence_turns <= 1
    )
    if should_clarify:
        return VoiceSessionDecision(
            session_id=session_id,
            locale=locale,
            asr_engine=asr_engine,
            tts_engine=tts_engine,
            recording_enabled=recording_consent_granted,
            cancel_active_reply=barge_in_detected,
            asr_rejected_reason=asr_rejected_reason,
            action="CLARIFY_INTENT_SPOKEN",
        )

    if dtmf_digit is not None or effective_confidence < MIN_UTTERANCE_ASR_CONFIDENCE:
        return VoiceSessionDecision(
            session_id=session_id,
            locale=locale,
            asr_engine=asr_engine,
            tts_engine=tts_engine,
            recording_enabled=recording_consent_granted,
            cancel_active_reply=barge_in_detected,
            asr_rejected_reason=asr_rejected_reason,
            action="DTMF_MENU",
        )

    return VoiceSessionDecision(
        session_id=session_id,
        locale=locale,
        asr_engine=asr_engine,
        tts_engine=tts_engine,
        recording_enabled=recording_consent_granted,
        cancel_active_reply=barge_in_detected,
        asr_rejected_reason=asr_rejected_reason,
        action="STREAM_ASR",
    )


class VoiceWebSocketConcurrencyGuard:
    """P1-9 Multi-Pool Voice/Call/Chat WebSocket Concurrency Cap & Slot Rekeying (`test_voice_ws_hardening.py`)."""

    def __init__(self, *, per_user_cap: int = 3, global_cap: int = 64) -> None:
        self.per_user_cap = max(1, per_user_cap)
        self.global_cap = max(1, global_cap)
        self._by_pool_user: dict[str, dict[str, int]] = {}
        self._total_by_pool: dict[str, int] = {}

    def active_count(self, pool: str = "voice") -> int:
        return self._total_by_pool.get(pool, 0)

    def try_acquire(self, user_key: str, *, pool: str = "voice") -> tuple[bool, int | None]:
        pool_users = self._by_pool_user.setdefault(pool, {})
        current = pool_users.get(user_key, 0)
        total = self._total_by_pool.get(pool, 0)
        if current >= self.per_user_cap or total >= self.global_cap:
            return False, 1013
        pool_users[user_key] = current + 1
        self._total_by_pool[pool] = total + 1
        return True, None

    def rekey_slot(
        self,
        old_user_key: str,
        new_user_key: str,
        *,
        pool: str = "voice",
        authenticated_per_user_cap: int | None = None,
    ) -> bool:
        """Atomically rekey an anonymous slot (`anon::ip`) to an authenticated `user_id` without changing pool total."""
        pool_users = self._by_pool_user.setdefault(pool, {})
        old_count = pool_users.get(old_user_key, 0)
        if old_count <= 0:
            return False
        if old_user_key == new_user_key:
            return True
        cap = (
            self.per_user_cap if authenticated_per_user_cap is None else authenticated_per_user_cap
        )
        new_count = pool_users.get(new_user_key, 0)
        if new_count >= cap:
            return False
        if old_count == 1:
            pool_users.pop(old_user_key, None)
        else:
            pool_users[old_user_key] = old_count - 1
        pool_users[new_user_key] = new_count + 1
        return True

    def release(self, user_key: str, *, pool: str = "voice") -> None:
        pool_users = self._by_pool_user.setdefault(pool, {})
        current = pool_users.get(user_key, 0)
        if current <= 0:
            return
        if current <= 1:
            pool_users.pop(user_key, None)
        else:
            pool_users[user_key] = current - 1
        self._total_by_pool[pool] = max(0, self._total_by_pool.get(pool, 0) - 1)


def is_ws_origin_allowed(
    origin: str | None,
    allowed_origins: set[str] | frozenset[str],
    *,
    require_origin: bool = True,
) -> bool:
    """Validate WebSocket `Origin` header (`test_voice_ws_hardening.py` & `CVE-2026-27978`)."""
    if not origin or origin.strip().lower() == "null":
        return not require_origin
    return origin.strip() in allowed_origins


@dataclass(frozen=True)
class BriefClaim:
    text: str
    turn_seqs: list[int]


@dataclass(frozen=True)
class OfficerCallBrief:
    call_id: str
    why_officer: BriefClaim
    caller_goal: BriefClaim
    ai_already_said: list[BriefClaim]
    still_open: list[BriefClaim]
    details_given: list[dict[str, Any]]
    sentiment: Literal["calm", "confused", "frustrated", "distressed"]
    suggested_opener: str
    turns_covered: int
    # The model that wrote the brief; None when it was built by the keyword rules below.
    model: str | None = None
    fallback: bool = False
    verified_artifacts: list[dict[str, Any]] = field(default_factory=list)
    recommended_officer_action: str = "Review verified e-Tax context and confirm next step"


_DISTRESS_WORDS_RE = re.compile(r"\b(?:urgent(?:ly)?|blocked|seiz(?:ed|ure)|distress(?:ed)?)\b")
_FRUSTRATION_WORDS_RE = re.compile(r"\b(?:errors?|fail(?:ed|s|ing)|frustrat(?:ed|ing)|wrong)\b")
_CONFUSION_WORDS_RE = re.compile(r"\b(?:confus(?:ed|ing)|understand)\b")


def _turn_seqs(turn: dict[str, Any] | None) -> list[int]:
    """Return a turn's sequence number as evidence, or nothing when it has no valid one."""
    seq = turn.get("seq") if turn is not None else None
    return [seq] if isinstance(seq, int) and not isinstance(seq, bool) and seq > 0 else []


def _redacted_turn_text(turn: dict[str, Any], limit: int) -> str:
    """Redact a turn before shortening it, so truncation cannot split an identifier past redaction."""
    return redact_pii(str(turn.get("text", ""))).redacted_text[:limit]


def generate_officer_call_brief(
    *,
    call_id: str,
    turns: list[dict[str, Any]],
    transfer_reason: str,
    verified_artifacts: list[dict[str, Any]] | None = None,
) -> OfficerCallBrief:
    """Build the 10-second Officer Call Brief (`CallBriefCard.tsx`) with turn-sequence evidence links.

    The brief is assembled by keyword rules, not by a model, so ``model`` is None. It states only
    what the turns support: the caller's first and latest requests, the assistant's latest replies,
    and the transfer reason it was given.
    """
    caller_turns = [
        t for t in turns if t.get("speaker") == "caller" and str(t.get("text", "")).strip()
    ]
    ai_turns = [
        t for t in turns if t.get("speaker") == "assistant" and str(t.get("text", "")).strip()
    ]
    first_caller = caller_turns[0] if caller_turns else None
    last_caller = caller_turns[-1] if caller_turns else None
    redacted_goal = (
        _redacted_turn_text(first_caller, 240)
        if first_caller is not None
        else "The caller has not stated a goal yet"
    )

    ai_claims = [
        BriefClaim(text=_redacted_turn_text(t, 140), turn_seqs=_turn_seqs(t)) for t in ai_turns[-3:]
    ]

    combined_lower = " ".join(str(t.get("text", "")).lower() for t in caller_turns)
    sentiment: Literal["calm", "confused", "frustrated", "distressed"] = "calm"
    if _DISTRESS_WORDS_RE.search(combined_lower):
        sentiment = "distressed"
    elif _FRUSTRATION_WORDS_RE.search(combined_lower):
        sentiment = "frustrated"
    elif _CONFUSION_WORDS_RE.search(combined_lower):
        sentiment = "confused"

    return OfficerCallBrief(
        call_id=call_id,
        why_officer=BriefClaim(text=transfer_reason, turn_seqs=_turn_seqs(last_caller)),
        caller_goal=BriefClaim(text=redacted_goal, turn_seqs=_turn_seqs(first_caller)),
        ai_already_said=ai_claims,
        still_open=[
            BriefClaim(
                text=f"Latest caller request: {_redacted_turn_text(last_caller, 140)}",
                turn_seqs=_turn_seqs(last_caller),
            )
        ]
        if last_caller is not None
        else [],
        details_given=[
            {
                "label": "First caller message (redacted)",
                "value": redacted_goal[:80],
                "turn_seqs": _turn_seqs(first_caller),
            }
        ]
        if first_caller is not None
        else [],
        sentiment=sentiment,
        suggested_opener=(
            "Hello, I'm an SSRA officer. I have the notes from your call with the automated "
            "assistant. Let's go through your question together."
        ),
        turns_covered=len(turns),
        fallback=len(turns) == 0,
        verified_artifacts=list(verified_artifacts or []),
        recommended_officer_action=(
            f"Priority de-escalation & verify {transfer_reason.lower()}"
            if sentiment in ("distressed", "frustrated")
            else f"Verify {transfer_reason.lower()} and guide next e-Tax step"
        ),
    )


@dataclass
class LobbyCallEntry:
    call_id: str
    status: Literal["ai", "transferring", "bridged", "ended"] = "ai"
    topic: str = "general"
    priority: str = "normal"
    language: str = "en"
    waiting_since: float | None = None
    reason: str = ""
    claimed_by: str = ""
    claimed_name: str = ""
    on_hold: bool = False
    needs_callback: bool = False
    risk_level: Literal["none", "watch", "at_risk"] = "none"
    risk_signals: list[str] = field(default_factory=list)
    dismissed: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


LOBBY_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "call.started",
        "call.transfer_requested",
        "call.priority_raised",
        "call.claimed",
        "call.officer_disconnected",
        "call.transfer_timed_out",
        "call.risk",
        "call.bridged",
        "call.on_hold",
        "call.ended",
        "call.wrapped_up",
    }
)
LOBBY_PRIORITIES: frozenset[str] = frozenset({"normal", "high", "urgent"})
MAX_ENDED_CALL_TOMBSTONES: int = 4096


def _optional_timestamp(value: Any) -> float | None:
    """Return a provided wait-start timestamp, or None when the event supplied no usable one."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    timestamp = float(value)
    return timestamp if math.isfinite(timestamp) else None


class CallLobbyManager:
    """Server/Console Call Lobby State Machine (`useCallConsoleStore.ts` pattern).

    The first officer to claim a waiting call owns it, ended calls cannot be revived by late
    events, and unknown event types are rejected. Only ``call.started`` can add a call, so a late
    event for an ended call whose tombstone has been evicted is rejected rather than reviving it.
    Each event is validated before the stored entry is changed.
    """

    def __init__(self) -> None:
        self.calls: dict[str, LobbyCallEntry] = {}
        self._ended: OrderedDict[str, None] = OrderedDict()

    def apply_event(self, event_type: str, data: dict[str, Any]) -> LobbyCallEntry:
        if event_type not in LOBBY_EVENT_TYPES:
            raise ValueError(f"Unsupported call lobby event '{event_type}'")
        call_id = str(data.get("call_id", "")).strip()
        if not call_id:
            raise ValueError("call_id is required")
        if call_id in self._ended:
            return LobbyCallEntry(call_id=call_id, status="ended")
        entry = self.calls.get(call_id)
        if entry is None:
            if event_type in {"call.ended", "call.wrapped_up"}:
                self._remember_ended(call_id)
                return LobbyCallEntry(call_id=call_id, status="ended")
            if event_type != "call.started":
                raise ValueError(
                    f"Call {call_id} is not in the lobby; only call.started can add it"
                )
            entry = LobbyCallEntry(call_id=call_id)
        if event_type == "call.started":
            entry.status = "ai"
        elif event_type == "call.transfer_requested":
            priority = _lobby_priority(data.get("priority", "normal"))
            entry.status = "transferring"
            entry.topic = str(data.get("topic", entry.topic))
            entry.priority = priority
            entry.reason = str(data.get("reason", ""))
            entry.waiting_since = _optional_timestamp(data.get("waiting_since"))
            entry.claimed_by = ""
            entry.claimed_name = ""
            entry.dismissed = False
        elif event_type == "call.priority_raised":
            # Raise priority and re-alert without clearing claimed_by or waiting_since
            entry.priority = _lobby_priority(data.get("priority", "urgent"))
            entry.reason = str(data.get("reason", entry.reason))
            entry.dismissed = False
        elif event_type == "call.claimed":
            officer_id = str(data.get("officer_id", "")).strip()
            if not officer_id:
                raise ValueError("officer_id is required to claim a call")
            if entry.status != "transferring":
                raise ValueError(f"Call {call_id} is not waiting for an officer")
            if entry.claimed_by and entry.claimed_by != officer_id:
                raise ValueError(f"Call {call_id} is already claimed by another officer")
            entry.claimed_by = officer_id
            entry.claimed_name = str(data.get("officer_name", ""))
        elif event_type == "call.officer_disconnected":
            entry.status = "transferring"
            entry.waiting_since = _optional_timestamp(data.get("waiting_since"))
            entry.reason = "officer_disconnected"
            entry.claimed_by = ""
            entry.claimed_name = ""
        elif event_type == "call.transfer_timed_out":
            entry.status = "ai"
            entry.waiting_since = None
            entry.needs_callback = True
            entry.claimed_by = ""
            entry.claimed_name = ""
        elif event_type == "call.risk":
            entry.risk_level = _lobby_risk_level(data.get("level", "none"))
            entry.risk_signals = [str(s) for s in (data.get("signals") or [])]
        elif event_type == "call.bridged":
            entry.status = "bridged"
            entry.waiting_since = None
        elif event_type == "call.on_hold":
            entry.on_hold = bool(data.get("on", False))
        elif event_type in {"call.ended", "call.wrapped_up"}:
            entry.status = "ended"
            self.calls.pop(call_id, None)
            self._remember_ended(call_id)
            return entry
        self.calls[call_id] = entry
        return entry

    def _remember_ended(self, call_id: str) -> None:
        self._ended[call_id] = None
        if len(self._ended) > MAX_ENDED_CALL_TOMBSTONES:
            self._ended.popitem(last=False)


def _lobby_risk_level(value: Any) -> Literal["none", "watch", "at_risk"]:
    """Accept only known risk levels, so an unexpected value cannot silently lower a caller's risk."""
    level = str(value).strip()
    if level == "at_risk":
        return "at_risk"
    if level == "watch":
        return "watch"
    if level == "none":
        return "none"
    raise ValueError(f"Unsupported call risk level '{value}'")


def _lobby_priority(value: Any) -> str:
    """Accept only the lobby's known priority levels."""
    priority = str(value).strip().lower()
    if priority not in LOBBY_PRIORITIES:
        raise ValueError(f"Unsupported call priority '{value}'")
    return priority


_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
MAX_CARRYOVER_CONTEXT_CHARS = 240


@dataclass(frozen=True)
class ChatToCallCarryover:
    conversation_id: str
    topic_id: str
    topic_label: str
    tax_domain: str
    context: str
    local_models_only: bool = True


def build_chat_to_call_carryover(
    *,
    conversation_id: str,
    owner_user_id: str | None,
    owner_session_id: str | None,
    caller_user_id: str | None = None,
    caller_session_id: str | None = None,
    topic_id: str = "general_tax",
    topic_label: str = "General tax inquiry",
    tax_domain: str = "domestic_tax",
) -> ChatToCallCarryover | None:
    """G122 Cross-Channel Chat-to-Call Carryover (`test_call_carryover.py`):

    1. Rejects malformed IDs (`../conversations`, spaces).
    2. A `conversation_id` alone unlocks nothing: caller must match `owner_user_id` or `owner_session_id`.
    3. Emits ONLY a coarse English task account (<= 240 chars) — never the taxpayer's verbatim words.
    4. Forces `local_models_only = True` on all voice call turns.
    """
    if not _SAFE_ID_RE.match(conversation_id):
        return None
    if caller_user_id and not _SAFE_ID_RE.match(caller_user_id):
        return None
    if caller_session_id and not _SAFE_ID_RE.match(caller_session_id):
        return None

    user_matched = bool(owner_user_id and caller_user_id and owner_user_id == caller_user_id)
    session_matched = bool(
        not owner_user_id
        and owner_session_id
        and caller_session_id
        and owner_session_id == caller_session_id
    )
    if not (user_matched or session_matched):
        return None

    coarse = f"Current task: {topic_label}. Tax domains discussed: {tax_domain}."[
        :MAX_CARRYOVER_CONTEXT_CHARS
    ]
    return ChatToCallCarryover(
        conversation_id=conversation_id,
        topic_id=topic_id,
        topic_label=topic_label,
        tax_domain=tax_domain,
        context=coarse,
        local_models_only=True,
    )


# Per-locale TTS Speaker Catalog (`test_sunbird_voice_selection.py` pattern):
# Every default speaker is first in its own locale catalog, and every tag is unique & locale-scoped.
TTS_VOICE_CATALOG: dict[str, tuple[str, ...]] = {
    "en": ("ssra_eng_0001", "ssra_eng_0002"),
    "ar": ("ssra_ara_0001", "ssra_ara_0002"),
    "pga": ("ssra_pga_0001", "ssra_pga_0002"),
    "din": ("ssra_din_0001", "ssra_din_0002"),
    "nus": ("ssra_nus_0001", "ssra_nus_0002"),
    "bfa": ("ssra_bfa_0001", "ssra_bfa_0002"),
    "zne": ("ssra_zne_0001", "ssra_zne_0002"),
    "shk": ("ssra_shk_0001", "ssra_shk_0002"),
}
TTS_DEFAULT_VOICE: dict[str, str] = {loc: tags[0] for loc, tags in TTS_VOICE_CATALOG.items()}


def resolve_tts_voice(locale: str, requested_voice: str | None = None) -> str | None:
    """Resolve a locale-scoped TTS speaker tag (`test_sunbird_voice_selection.py`):
    - Returns `None` for unknown locales (`"xx"`).
    - Replaces `None`, empty strings, foreign backend names (`en-US-AriaNeural`), or tags
      belonging to another locale with `TTS_DEFAULT_VOICE[locale]`.
    """
    loc = (locale or "").strip().lower()
    catalog = TTS_VOICE_CATALOG.get(loc)
    if not catalog:
        return None
    if requested_voice and requested_voice in catalog:
        return requested_voice
    return TTS_DEFAULT_VOICE[loc]


@dataclass(frozen=True)
class VADConfig:
    """Energy-based Voice Activity Detection thresholds (`voice_stream.py`)."""

    energy_threshold: float = 0.015
    silence_duration_ms: int = 600
    min_speech_duration_ms: int = 250
    max_utterance_s: float = 30.0
    sample_rate: int = 16_000

    @classmethod
    def from_sensitivity(cls, sensitivity: str = "medium", sample_rate: int = 16_000) -> VADConfig:
        """Construct a `VADConfig` preset from a named sensitivity level (`low`, `medium`, `high`)."""
        presets = {
            "low": cls(energy_threshold=0.025, silence_duration_ms=800, sample_rate=sample_rate),
            "medium": cls(energy_threshold=0.015, silence_duration_ms=600, sample_rate=sample_rate),
            "high": cls(energy_threshold=0.008, silence_duration_ms=400, sample_rate=sample_rate),
        }
        return presets.get(sensitivity.lower(), presets["medium"])


@dataclass(frozen=True)
class BargeInDirective:
    """What the media pipeline must do when the caller talks over the assistant.

    Stopping playback alone would leave a stale reply being generated, and cancelling generation
    alone would leave buffered audio playing, so both are always set together.
    """

    stop_playback: bool
    cancel_generation: bool
    flush_queued_audio: bool
    interrupted_at_sentence_index: int | None


class VoiceStreamSession:
    """V2 Streaming Voice Session (`voice_stream_v2.py`): sentence-chunked TTS, full-duplex barge-in & speculative prefetch."""

    def __init__(
        self, *, session_id: str, locale: LocaleCode, vad: VADConfig | None = None
    ) -> None:
        """Initialize a streaming voice session with VAD thresholds and full-duplex barge-in state."""
        self.session_id = session_id
        self.locale = locale
        self.vad = vad or VADConfig.from_sensitivity("medium")
        self.barge_in_cancelled = False
        self.interrupted_at_sentence_index: int | None = None
        self.unspoken_sentences: list[str] = []
        self.speculative_prefetches: list[str] = []

    def trigger_barge_in(
        self,
        *,
        sentence_index: int | None = None,
        speech_ms: int | None = None,
        prompt_interruptible: bool = True,
    ) -> BargeInDirective | None:
        """Handle the caller talking over the assistant.

        Speech shorter than the VAD minimum (a cough or "mm") and speech over a prompt that may not
        be interrupted, such as the AI disclosure, are ignored and return None. Otherwise playback
        stops, the reply being generated is cancelled, and queued audio is dropped. Omit
        ``speech_ms`` only when the media layer has already confirmed the interruption.
        """
        if not prompt_interruptible:
            return None
        if speech_ms is not None and speech_ms < self.vad.min_speech_duration_ms:
            return None
        if sentence_index is None:
            self.barge_in_cancelled = True
        else:
            self.interrupted_at_sentence_index = max(0, sentence_index)
        return BargeInDirective(
            stop_playback=True,
            cancel_generation=True,
            flush_queued_audio=True,
            interrupted_at_sentence_index=self.interrupted_at_sentence_index,
        )

    def reset_barge_in(self) -> None:
        """Reset per-turn barge-in interruption state before streaming the next reply."""
        self.barge_in_cancelled = False
        self.interrupted_at_sentence_index = None
        self.unspoken_sentences = []

    def record_partial_transcript(self, partial_text: str) -> str | None:
        """Record a 4-word stable partial transcript prefix for speculative retrieval prefetch."""
        words = [w for w in partial_text.strip().split() if w]
        if len(words) >= 3:
            stable_prefix = " ".join(words[:4])
            self.speculative_prefetches.append(stable_prefix)
            return stable_prefix
        return None

    def stream_tts_sentences(self, text: str, *, voice: str | None = None) -> list[dict[str, Any]]:
        """Synthesize reply sentences in order, halting on barge-in and recording unspoken sentences."""
        sentences = split_tts_sentences(text)
        chunks: list[dict[str, Any]] = []
        self.unspoken_sentences = []
        for idx, sentence in enumerate(sentences):
            if self.barge_in_cancelled or (
                self.interrupted_at_sentence_index is not None
                and idx >= self.interrupted_at_sentence_index
            ):
                self.unspoken_sentences = sentences[idx:]
                break
            env = synthesize_tts_speech_envelope(text=sentence, locale=self.locale, voice=voice)
            env["sentence_index"] = idx
            env["sentence_text"] = sentence
            chunks.append(env)
        return chunks

    def resume_after_network_drop(
        self,
        text: str,
        *,
        last_acked_sentence_index: int,
        voice: str | None = None,
    ) -> list[dict[str, Any]]:
        """Resume sentence-chunked TTS after a transient 2G WebSocket/WebRTC drop from `last_acked_sentence_index + 1`."""
        self.reset_barge_in()
        all_chunks = self.stream_tts_sentences(text, voice=voice)
        return [c for c in all_chunks if int(c["sentence_index"]) > last_acked_sentence_index]


VOICE_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "recording_start",
        "recording_end",
        "transcript_stored",
        "audio_deleted",
        "consent_checked",
        "consent_denied",
        "retention_cleanup",
        "session_start",
        "session_end",
        "barge_in",
        "call_started",
        "call_transferred",
        "officer_joined",
        "call_ended",
        "staff_viewed_call",
        "staff_viewed_brief",
        "staff_viewed_caller_history",
        "staff_listened_call",
        "officer_claimed",
        "officer_released",
        "officer_ended_call",
        "officer_hold_on",
        "officer_hold_off",
        "officer_transferred",
        "officer_wrapup_saved",
        "officer_callback_done",
    }
)


@dataclass(frozen=True)
class VoiceRetentionPolicy:
    """Voice retention periods. None means no approved period (OQ-009 item 1): keep nothing after the call."""

    raw_audio_ttl_hours: int | None = None
    transcript_ttl_days: int | None = None
    analytics_ttl_days: int | None = None
    store_raw_audio: bool = False

    def __post_init__(self) -> None:
        if self.store_raw_audio and self.raw_audio_ttl_hours is None:
            raise ValueError(
                "Raw call audio cannot be stored without an approved retention period (OQ-009)"
            )


def build_voice_consent_audit_entry(
    *,
    event_type: str,
    session_id: str,
    audio_bytes: bytes = b"",
    policy: VoiceRetentionPolicy | None = None,
) -> dict[str, Any]:
    """Record a privacy-preserving voice audit entry (`voice_consent.py`):
    Raw audio is never stored by default — only its SHA-256 hash is logged.
    """
    if event_type not in VOICE_EVENT_TYPES:
        raise ValueError(f"Unsupported voice audit event_type '{event_type}'")
    active_policy = policy or VoiceRetentionPolicy()
    return {
        "event_type": event_type,
        "session_id": session_id,
        "audio_sha256": hashlib.sha256(audio_bytes).hexdigest() if audio_bytes else None,
        "raw_audio_stored": active_policy.store_raw_audio,
        "transcript_ttl_days": active_policy.transcript_ttl_days,
        "retention_status": "approved"
        if active_policy.transcript_ttl_days is not None
        else "pending_oq_009",
    }


def looks_like_valid_audio_bytes(data: bytes) -> bool:
    """Verify binary audio container headers (`TestAudioSniff` in `test_voice_robustness.py`):
    Accepts WAV (`RIFF....WAVE`), Ogg/Opus (`OggS`), MP3 (`ID3` / `\\xff\\xfb` / `\\xff\\xf3`), or FLAC (`fLaC`) >= 32 bytes;
    rejects HTML error pages (`<html>rate limited</html>`), RIFF/WEBP images, or truncated headers (`b"RIFF"`).
    """
    if len(data) < 32:
        return False
    return (data.startswith(b"RIFF") and data[8:12] == b"WAVE") or data.startswith(
        (b"OggS", b"ID3", b"\xff\xfb", b"\xff\xf3", b"fLaC")
    )


@dataclass(frozen=True)
class TtsCachedAudio:
    audio: bytes
    backend: str
    voice: str
    language: str
    latency_ms: float
    error: str | None = None


class TtsSynthesizer(Protocol):
    def __call__(self, text: str, /, *, language: str, voice: str) -> TtsCachedAudio: ...


def _normalize_phrase(text: str) -> str:
    return " ".join(text.split())


class TtsPhraseCache:
    """Bounded LRU TTS Phrase Cache (`TestTtsPhraseCache` in `test_voice_robustness.py`):
    Serves repeated phrases with `backend='<engine>+cache'` and `latency_ms=0.0`, and never caches failures.

    The cache is shared across calls, so it stores audio only for fixed, non-personal prompts
    (``fixed_voice_prompts()`` by default). Any other text is synthesized and returned without
    being kept.
    """

    def __init__(
        self, *, max_entries: int = 256, cacheable_phrases: frozenset[str] | None = None
    ) -> None:
        self.max_entries = max(1, max_entries)
        phrases = fixed_voice_prompts() if cacheable_phrases is None else cacheable_phrases
        self._cacheable = frozenset(_normalize_phrase(p) for p in phrases)
        self._store: OrderedDict[str, TtsCachedAudio] = OrderedDict()

    @staticmethod
    def _make_key(text: str, *, language: str, voice: str) -> str:
        norm = " ".join(text.strip().lower().split())
        digest = hashlib.sha256(f"{language}:{voice}:{norm}".encode()).hexdigest()
        return f"tts:{language}:{voice}:{digest}"

    def get_or_synthesize(
        self,
        text: str,
        *,
        language: str,
        voice: str | None,
        synthesizer: TtsSynthesizer,
    ) -> TtsCachedAudio:
        resolved_voice = resolve_tts_voice(language, voice)
        if resolved_voice is None:
            return TtsCachedAudio(
                audio=b"",
                backend="error",
                voice="",
                language=language,
                latency_ms=0.0,
                error=f"Unsupported TTS locale '{language}'",
            )
        if _normalize_phrase(text) not in self._cacheable:
            return synthesizer(text, language=language, voice=resolved_voice)
        key = self._make_key(text, language=language, voice=resolved_voice)
        cached = self._store.get(key)
        if cached is not None:
            self._store.move_to_end(key)
            return TtsCachedAudio(
                audio=cached.audio,
                backend=f"{cached.backend}+cache",
                voice=cached.voice,
                language=cached.language,
                latency_ms=0.0,
            )
        fresh: TtsCachedAudio = synthesizer(text, language=language, voice=resolved_voice)
        if not fresh.error and looks_like_valid_audio_bytes(fresh.audio):
            if len(self._store) >= self.max_entries:
                self._store.popitem(last=False)
            self._store[key] = fresh
        return fresh


def resolve_mt_and_tts_turn_plan(
    *,
    source_locale: str,
    original_transcript: str,
    inbound_translated_en: str | None,
    english_reply_text: str,
    outbound_translated_text: str | None,
    requested_voice: str | None = None,
) -> dict[str, Any]:
    """Honest MT Degradation & Language-Matched Voice Selection (`TestMtDegradation` in `test_voice_robustness.py`):
    1. If inbound MT (`source_locale -> en`) fails, pass `original_transcript` labeled with `source_locale` (never mislabeled as `en`).
    2. If outbound MT (`en -> source_locale`) fails, speak `english_reply_text` using the `en` TTS voice (`ssra_eng_0001`), never mangling English with a local-language voice.
    """
    src = source_locale.strip().lower()
    mt_degraded: list[str] = []

    if src == "en":
        llm_locale = "en"
        llm_message = original_transcript
    elif inbound_translated_en and inbound_translated_en.strip():
        llm_locale = "en"
        llm_message = inbound_translated_en.strip()
    else:
        mt_degraded.append(f"{src}-en")
        llm_locale = src
        llm_message = original_transcript

    if src == "en":
        reply_language = "en"
        spoken_text = english_reply_text
    elif outbound_translated_text and outbound_translated_text.strip():
        reply_language = src
        spoken_text = outbound_translated_text.strip()
    else:
        mt_degraded.append(f"en-{src}")
        reply_language = "en"
        spoken_text = english_reply_text

    tts_voice = resolve_tts_voice(
        reply_language, requested_voice if reply_language == src else None
    )
    return {
        "llm_locale": llm_locale,
        "llm_message": llm_message,
        "reply_language": reply_language,
        "spoken_text": spoken_text,
        "tts_voice": tts_voice,
        "mt_degraded": mt_degraded,
    }


def validate_call_wrap_up(
    *,
    note: str,
    outcome: Literal["resolved", "escalated", "callback_scheduled"],
    caller_satisfaction: int | None,
    caller_satisfaction_status: Literal["answered", "not_said"],
    ai_rating: int | None = None,
) -> dict[str, Any]:
    """Validate Officer Call Wrap-Up (`WrapUpPanel.tsx` pattern)."""
    cleaned_note = note.strip()
    if not cleaned_note:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "Please provide a call wrap-up note",
            status_code=400,
        )
    if caller_satisfaction_status == "answered":
        if caller_satisfaction is None or not (1 <= caller_satisfaction <= 5):
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                "Record how satisfied the caller said they were (1..5), or mark that they didn't say",
                status_code=400,
            )
    if ai_rating is not None and not (1 <= ai_rating <= 5):
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "Optional AI pre-transfer rating must be between 1 and 5",
            status_code=400,
        )
    return {
        "note": redact_pii(cleaned_note).redacted_text,
        "outcome": outcome,
        "caller_satisfaction": None
        if caller_satisfaction_status == "not_said"
        else caller_satisfaction,
        "caller_satisfaction_status": caller_satisfaction_status,
        "ai_rating": ai_rating,
    }


@dataclass(frozen=True)
class VoiceDtmfStepUpResult:
    authorized: bool
    action: Literal[
        "BOUND_T1", "BOUND_T3", "REJECTED_SPOKEN_OTP", "OTP_REJECTED", "WARM_TRANSFER_TO_OFFICER"
    ]
    tin_masked: str | None
    recording_paused_for_dtmf: bool
    reason: str | None = None


# Checks a keypad OTP for a TIN against the approved identity provider (OQ-005). It must compare
# in constant time and enforce the provider's own expiry and single use.
OtpVerifier = Callable[[str, str], bool]
MAX_DTMF_STEP_UP_ATTEMPTS: int = 3


class StepUpAttemptStore(Protocol):
    """Per-call count of rejected keypad codes, kept for the life of the call in durable state (OQ-015)."""

    def failed_attempts(self, call_id: str) -> int: ...

    def record_failed_attempt(self, call_id: str) -> int:
        """Add one rejected code for the call and return the new total."""
        ...


def verify_voice_dtmf_step_up(
    *,
    dtmf_tin_digits: str,
    dtmf_otp_digits: str,
    input_modality: Literal["dtmf_rfc4733", "spoken_asr"] = "dtmf_rfc4733",
    requested_tier: Literal["T1", "T2", "T3", "T4"] = "T1",
    sim_swap_recent: bool = False,
    otp_verifier: OtpVerifier | None = None,
    call_id: str,
    attempt_store: StepUpAttemptStore,
) -> VoiceDtmfStepUpResult:
    """Enforce RFC 4733 DTMF-only TIN/OTP entry with recording pause and SIM-swap / T4 guards.

    Well-formed digits are not proof of identity. The OTP must be confirmed by an approved
    ``otp_verifier``; without one the call goes to an officer instead of binding a subject. Each
    rejected code is recorded in ``attempt_store`` against ``call_id``, so the three-attempt limit
    cannot be reset by the caller. If the verifier or the store fails, nothing is bound and the call
    goes to an officer.
    """
    if requested_tier == "T4" or sim_swap_recent:
        return VoiceDtmfStepUpResult(
            authorized=False,
            action="WARM_TRANSFER_TO_OFFICER",
            tin_masked=None,
            recording_paused_for_dtmf=True,
            reason="T4 action or recent SIM-swap signal requires live SSRA officer",
        )
    if input_modality != "dtmf_rfc4733":
        return VoiceDtmfStepUpResult(
            authorized=False,
            action="REJECTED_SPOKEN_OTP",
            tin_masked=None,
            recording_paused_for_dtmf=True,
            reason="Spoken TIN/OTP over ASR is prohibited; enter digits on telephone keypad (DTMF)",
        )
    clean_tin = "".join(ch for ch in dtmf_tin_digits if ch in "0123456789")
    clean_otp = "".join(ch for ch in dtmf_otp_digits if ch in "0123456789")
    if not (9 <= len(clean_tin) <= 12) or len(clean_otp) != 6:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "DTMF step-up requires 9..12 ASCII TIN digits and 6 ASCII OTP digits",
            status_code=400,
        )
    if not call_id.strip():
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "DTMF step-up requires the call_id that keypad attempts are counted against",
            status_code=400,
        )
    too_many_attempts = VoiceDtmfStepUpResult(
        authorized=False,
        action="WARM_TRANSFER_TO_OFFICER",
        tin_masked=None,
        recording_paused_for_dtmf=True,
        reason="Too many keypad verification attempts on this call",
    )
    if otp_verifier is None:
        return VoiceDtmfStepUpResult(
            authorized=False,
            action="WARM_TRANSFER_TO_OFFICER",
            tin_masked=None,
            recording_paused_for_dtmf=True,
            reason="No approved OTP verifier is configured (OQ-005); identity cannot be confirmed on this call",
        )
    try:
        if attempt_store.failed_attempts(call_id) >= MAX_DTMF_STEP_UP_ATTEMPTS:
            return too_many_attempts
        if otp_verifier(clean_tin, clean_otp):
            return VoiceDtmfStepUpResult(
                authorized=True,
                action="BOUND_T3" if requested_tier == "T3" else "BOUND_T1",
                tin_masked=f"••••{clean_tin[-4:]}",
                recording_paused_for_dtmf=True,
            )
        failures = attempt_store.record_failed_attempt(call_id)
    except Exception:
        # A provider or attempt-store failure must never bind a subject, and the caller still needs help.
        return VoiceDtmfStepUpResult(
            authorized=False,
            action="WARM_TRANSFER_TO_OFFICER",
            tin_masked=None,
            recording_paused_for_dtmf=True,
            reason="Identity verification is unavailable on this call",
        )
    if failures >= MAX_DTMF_STEP_UP_ATTEMPTS:
        return too_many_attempts
    return VoiceDtmfStepUpResult(
        authorized=False,
        action="OTP_REJECTED",
        tin_masked=None,
        recording_paused_for_dtmf=True,
        reason="The keypad code was not accepted",
    )


_SMS_SENDER_LABEL = "SSRA Assist (automated):"
_SMS_PORTAL_REFERENCE = "Ref: https://etax.nra.gov.ss/"


def build_voice_spoken_turn_and_sms_followup(
    *,
    reply_text: str,
    citation_anchor: str | None = None,
    is_estimate: bool = False,
    max_sms_chars: int = MAX_SMS_CONTINUATION_CHARS,
) -> dict[str, Any]:
    """Speak at most three whole sentences, framed as an estimate when it is one, and build the SMS follow-up.

    The SMS says it is automated, keeps the citation and portal reference, and drops whole
    sentences from the end until it fits, so a figure is never cut. The estimate framing comes
    first and is never dropped while a figure is kept. The real encoding and segment count are
    returned so the cost of a UCS-2 (Arabic) message is visible.
    """
    spoken = compose_spoken_reply(reply_text, is_estimate=is_estimate)
    citation = f"({citation_anchor})" if citation_anchor else ""
    sms = fit_text(
        spoken.text,
        fits=lambda candidate: len(candidate) <= max_sms_chars,
        prefix=_SMS_SENDER_LABEL,
        suffix=f"{citation} {_SMS_PORTAL_REFERENCE}".strip(),
    )
    return {
        "spoken_text": spoken.text,
        "sentence_count": spoken.kept_sentences,
        "is_estimate": is_estimate,
        "sms_continuation_text": sms.text,
        "sms_encoding": sms_encoding(sms.text),
        "sms_segments": count_sms_segments(sms.text),
        "sms_shortened": sms.kept_sentences < sms.total_sentences,
    }


_EN_APPROVED_TOOL_WAIT_FILLER = "One moment while I check the official SSRA records."

# Only single-script, SSRA-approved fillers are active; Tier B/C locales pending OQ-008 voice clip sign-off fall back safely to _EN_APPROVED_TOOL_WAIT_FILLER
_TOOL_WAIT_FILLERS: dict[LocaleCode, str] = {
    LocaleCode.EN: _EN_APPROVED_TOOL_WAIT_FILLER,
    LocaleCode.AR: "لحظة واحدة، أتحقق الآن من سجلات هيئة الإيرادات الرسمية.",
    LocaleCode.PGA: _EN_APPROVED_TOOL_WAIT_FILLER,
    LocaleCode.DIN: _EN_APPROVED_TOOL_WAIT_FILLER,
    LocaleCode.NUS: _EN_APPROVED_TOOL_WAIT_FILLER,
    LocaleCode.BFA: _EN_APPROVED_TOOL_WAIT_FILLER,
    LocaleCode.ZNE: _EN_APPROVED_TOOL_WAIT_FILLER,
    LocaleCode.SHK: _EN_APPROVED_TOOL_WAIT_FILLER,
}


def get_localized_tool_wait_filler(locale: LocaleCode = LocaleCode.EN) -> str:
    """Return a zero-digit, pre-cacheable filler utterance (`<250ms` TTFA) spoken while MCP tools execute."""
    return _TOOL_WAIT_FILLERS.get(locale, _TOOL_WAIT_FILLERS[LocaleCode.EN])


# Interim English wording until SSRA approves the statutory disclosure and consent text (OQ-009
# item 2). The disclosure mirrors the web disclosure (AUD-021). No reviewed translations exist, so
# every language hears English and the prompt records that.
_CALL_AI_DISCLOSURE_EN = (
    "You are speaking with SSRA Assist, an automated AI assistant. It can make mistakes. "
    "To ask for an SSRA officer at any time, press 0."
)
_CALL_RECORDING_CONSENT_EN = (
    "SSRA would like to record this call. Press 1 to allow recording, "
    "or press 2 to continue without recording."
)
# Reviewed translations of (disclosure, recording consent) by language. None exist yet (OQ-008, OQ-009).
_REVIEWED_OPENING_PROMPTS: Mapping[LocaleCode, tuple[str, str]] = MappingProxyType({})


@dataclass(frozen=True)
class VoicePrompt:
    prompt_id: Literal["ai_disclosure", "recording_consent"]
    text: str
    spoken_locale: LocaleCode
    interruptible_by_speech: bool
    wording_approved: bool


def build_call_opening_prompts(locale: LocaleCode, *, recording_offered: bool) -> list[VoicePrompt]:
    """Return what every caller hears first: the AI disclosure, then the recording request if offered.

    Speech cannot interrupt the disclosure (keypad 0 still reaches an officer). Recording starts
    only after the caller presses 1 (``resolve_recording_consent``).
    """
    reviewed = _REVIEWED_OPENING_PROMPTS.get(locale)
    disclosure, consent = reviewed or (_CALL_AI_DISCLOSURE_EN, _CALL_RECORDING_CONSENT_EN)
    spoken_locale = locale if reviewed else LocaleCode.EN
    prompts = [
        VoicePrompt(
            prompt_id="ai_disclosure",
            text=disclosure,
            spoken_locale=spoken_locale,
            interruptible_by_speech=False,
            wording_approved=False,
        )
    ]
    if recording_offered:
        prompts.append(
            VoicePrompt(
                prompt_id="recording_consent",
                text=consent,
                spoken_locale=spoken_locale,
                interruptible_by_speech=True,
                wording_approved=False,
            )
        )
    return prompts


def resolve_recording_consent(dtmf_digit: str | None) -> bool:
    """Recording needs an explicit keypad 1; any other key, or no answer, means no recording."""
    return dtmf_digit == "1"


def fixed_voice_prompts() -> frozenset[str]:
    """Return the fixed, non-personal prompts whose audio may be cached and reused across calls."""
    return frozenset(
        {*_TOOL_WAIT_FILLERS.values(), _CALL_AI_DISCLOSURE_EN, _CALL_RECORDING_CONSENT_EN}
    )


# Post-TTS room/handset acoustic tail cooldown (MARIA OS / Speko 2026 turn-taking standard).
POST_TTS_ECHO_COOLDOWN_MS: int = 450

_BACKCHANNEL_PHRASES: frozenset[str] = frozenset(
    {
        "mm",
        "mmm",
        "mm hm",
        "mm-hm",
        "mmhm",
        "uh huh",
        "uh-huh",
        "okay",
        "ok",
        "i see",
        "right",
        "got it",
        "نعم",
        "تمام",
        "ايوه",
        "أيوة",
    }
)
_SPEECH_TOKEN_RE = re.compile(r"[\w\u0600-\u06ff]+", flags=re.UNICODE)


def _speech_tokens(text: str) -> list[str]:
    return [tok.lower() for tok in _SPEECH_TOKEN_RE.findall(text) if tok.strip()]


def is_backchannel_utterance(text: str) -> bool:
    """Return True when a short listener acknowledgement should not interrupt the assistant's reply."""
    tokens = _speech_tokens(text)
    if not tokens or len(tokens) > 2:
        return False
    normalized = " ".join(tokens)
    return normalized in _BACKCHANNEL_PHRASES


def is_likely_tts_echo(
    transcript: str,
    last_assistant_spoken_text: str,
    *,
    elapsed_since_tts_end_ms: int | float | None = None,
) -> bool:
    """Detect when a microphone transcript is acoustic echo of the assistant's own TTS output.

    Within ``POST_TTS_ECHO_COOLDOWN_MS`` (450 ms) after TTS playback ends—or while TTS is still
    playing (`elapsed_since_tts_end_ms <= 0`)—room reverberation and speaker coupling can feed the
    assistant's words back into the recognizer. Outside the cooldown window, only long high-overlap
    repeats (>= 4 words, >= 85% token overlap) count as self-echo.
    """
    caller_tokens = _speech_tokens(transcript)
    assistant_tokens = _speech_tokens(last_assistant_spoken_text)
    if not caller_tokens or not assistant_tokens:
        return False
    caller_joined = " ".join(caller_tokens)
    assistant_joined = " ".join(assistant_tokens)
    caller_padded = f" {caller_joined} "
    assistant_padded = f" {assistant_joined} "
    assistant_set = set(assistant_tokens)
    overlap = sum(1 for tok in caller_tokens if tok in assistant_set) / len(caller_tokens)

    in_echo_tail = (
        elapsed_since_tts_end_ms is not None
        and math.isfinite(elapsed_since_tts_end_ms)
        and elapsed_since_tts_end_ms <= POST_TTS_ECHO_COOLDOWN_MS
    )
    if in_echo_tail:
        if caller_padded in assistant_padded:
            return True
        if len(caller_tokens) >= 2 and overlap >= 0.75:
            return True
    if len(caller_tokens) >= 4 and (caller_padded in assistant_padded or overlap >= 0.85):
        return True
    return False


_HUMAN_REQUEST_RE = re.compile(
    r"\b(?:(?:speak|talk)\s+(?:to|with)|(?:connect|transfer|put)\s+(?:me\s+)?(?:through\s+)?to|get\s+me|contact|call)"
    r"\s+(?:(?:a|an|the)\s+)?(?:human|person|officer|agent|representative|someone|somebody|operator|real\s+person)\b|"
    r"\b(?:i\s+want|can\s+i|need\s+to)\s+(?:talk\s+to|speak\s+(?:to|with)|see)\s+(?:an?\s+)?officer\b|"
    r"(?:أريد|عايز|تحدث\s+مع|حولني\s+إلى)\s+(?:موظف|شخص)",
    re.IGNORECASE,
)
_HUMAN_WORD_RE = re.compile(
    r"^[\s,!.?]*(?:(?:yes|yeah|ok|okay|please|نعم|أيوة)[\s,!.?]+)?"
    r"(?:(?:i\s+(?:want|need)|give\s+me|can\s+i\s+(?:have|get))\s+)?"
    r"(?:(?:a|an|the)\s+)?(?:real\s+)?"
    r"(?:officer|agent|human|person|representative|operator|customer\s+(?:care|service)|موظف)"
    r"(?:[\s,!.?]+(?:please|now|من\s+فضلك|لو\s+سمحت))?[\s,!.?]*$",
    re.IGNORECASE,
)
_TAX_DISPUTE_RE = re.compile(
    r"\b(?:dispute|object(?:ion)?|appeal|tribunal|tat|court|lawyer|advocate|illegal|fraud|اعتراض|طعن|محكمة)\b",
    re.IGNORECASE,
)
_OFFER_ACCEPT_RE = re.compile(
    r"^[\s,!.?]*(?:yes|yeah|yep|sure|ok|okay|alright|please|go\s+ahead|connect\s+me|please\s+do|confirm|نعم|أيوة|طيب|موافق)"
    r"(?:[\s,!.?]+(?:please\s+connect\s+me|connect\s+me|go\s+ahead|thank\s+you|please|sure|thanks|confirm|شكرا|من\s+فضلك))?[\s,!.?]*$",
    re.IGNORECASE,
)
_OFFER_DECLINE_RE = re.compile(
    r"^[\s,!.?]*(?:no|nope|not\s+now|i'?m\s+(?:fine|okay|ok)|that'?s\s+(?:all|enough|it)|لا|لأ|مش\s+هسا)"
    r"(?:[\s,!.?]+(?:i'?m\s+(?:fine|okay|ok)\s+thanks|i'?m\s+(?:fine|okay|ok)|thank\s+you|thanks|not\s+now|شكرا))?[\s,!.?]*$",
    re.IGNORECASE,
)
_MORE_ACCEPT_RE = re.compile(
    r"^[\s,!.?]*(?:(?:yes|yeah|sure|ok|okay|please|نعم|أيوة)[\s,!.?]+)?"
    r"(?:tell\s+me\s+more|go\s+on|carry\s+on|continue|more\s+detail|more|تفاصيل\s+أكثر|استمر)"
    r"(?:[\s,!.?]+please)?[\s,!.?]*$",
    re.IGNORECASE,
)
_CONTROL_MAX_WORDS: int = 8
_REPEAT_PATTERNS = re.compile(
    r"\b(?:repeat\s+that|say\s+that\s+again|could\s+you\s+repeat|pardon\s+me|what\s+did\s+you\s+say|أعد\s+ذلك|ممكن\s+تعيد)\b",
    re.IGNORECASE,
)
_SPEED_SLOW_PATTERNS = re.compile(
    r"\b(?:speak\s+slower|more\s+slowly|talk\s+slower|slow\s+down|تحدث\s+ببطء|تكلم\s+ببطء)\b",
    re.IGNORECASE,
)
_SPEED_NORMAL_PATTERNS = re.compile(
    r"\b(?:speak\s+(?:normally|faster)|normal\s+(?:speed|pace)|regular\s+(?:speed|pace)|talk\s+faster|سرعة\s+عادية)\b",
    re.IGNORECASE,
)
_CALLBACK_RE = re.compile(
    r"\b(?:(?:call|ring|phone)\s+me\s+(?:back|later)|call[\s-]?back|اتصل\s+بي\s+لاحقا)\b",
    re.IGNORECASE,
)
_HANGUP_VOICE_PATTERNS = re.compile(
    r"\b(?:hang\s+up|end\s+(?:the\s+)?call|disconnect|good[\s-]?bye|مع\s+السلامة|أنهي\s+المكالمة)\b",
    re.IGNORECASE,
)
_DONE_RE = re.compile(
    r"^[\s,!.?]*(?:(?:ok|okay|thanks|thank\s+you|alright|great|no)[\s,!.?]+)?"
    r"(?:that'?s\s+all|that\s+is\s+all|good[\s-]?bye|bye\s+bye|bye|i'?m\s+done)"
    r"(?:[\s,!.?]+(?:for\s+(?:now|today)|thank\s+you|thanks|bye))?[\s,!.?]*$",
    re.IGNORECASE,
)
_REVIEW_DECLINE_RE = re.compile(
    r"\b(?:no,?\s+thank(?:s|\s+you)|not\s+sure|(?:i\s+)?(?:don'?t|do\s+not)\s+know|لا\s+أعرف)\b",
    re.IGNORECASE,
)
_REVIEW_NEUTRAL_NEGATED_RE = re.compile(
    r"\b(?:not\s+(?:too\s+|that\s+|so\s+)?bad|ليس\s+سيئا)\b",
    re.IGNORECASE,
)
_REVIEW_NEGATIVE_RE = re.compile(
    r"\b(?:not\s+(?:really|much|at\s+all)|"
    r"not\s+(?:very\s+|really\s+|that\s+|so\s+|too\s+)?(?:helpful|useful|good|clear|great)|"
    r"(?:was|is|were)(?:n'?t|\s+not)\s+(?:very\s+|really\s+|that\s+)?(?:helpful|useful|good|clear)|"
    r"(?:did|does)(?:n'?t|\s+not)\s+(?:really\s+)?(?:help|answer|work)|"
    r"no\s+help|unhelpful|useless|waste\s+of\s+(?:my\s+)?time|terrible|awful|bad|poor|confusing|disappointed|غير\s+مفيد|سيء)\b",
    re.IGNORECASE,
)
_REVIEW_NEUTRAL_RE = re.compile(
    r"\b(?:so[\s-]so|a\s+(?:bit|little)|partly|partially|kind\s+of|sort\s+of|somewhat|more\s+or\s+less|half|قليلا)\b",
    re.IGNORECASE,
)
_REVIEW_POSITIVE_RE = re.compile(
    r"\b(?:helpful|useful|(?:very\s+)?good|great|excellent|perfect|wonderful|helped|thank(?:s|\s+you)|appreciate(?:d)?|satisfied|happy|clear|مفيد|ممتاز|شكرا)\b",
    re.IGNORECASE,
)
_REVIEW_WEAK_NEUTRAL_RE = re.compile(
    r"\b(?:ok(?:ay)?|fine|alright|all\s+right|average|fair|عادي)\b",
    re.IGNORECASE,
)
_TRAILING_LIST_NUMBER_RE = re.compile(r"(?:^|\s)(\d{1,2})\.$")
_TRAILING_ABBREVIATION_RE = re.compile(
    r"(?:^|\s)(?:e\.g|i\.e|etc|No|Sec|Art|Cap|Mr|Mrs|Ms|Dr|St|vs)\.$", re.IGNORECASE
)


def is_spoken_officer_request(text: str) -> bool:
    """Return True when *text* asks to speak with a human officer (`brain.py` `is_human_request`)."""
    return bool(_HUMAN_REQUEST_RE.search(text) or _HUMAN_WORD_RE.search(text))


def is_tax_dispute(text: str, reason: str = "") -> bool:
    """Return True when the question or transfer reason involves a tax dispute or legal objection (`brain.py`)."""
    return bool(_TAX_DISPUTE_RE.search(text) or _TAX_DISPUTE_RE.search(reason))


def _is_short_control_request(pattern: re.Pattern[str], text: str) -> bool:
    return len(text.split()) <= _CONTROL_MAX_WORDS and pattern.search(text) is not None


def is_repeat_request(text: str) -> bool:
    """Return True when the caller asks to repeat the last answer (`brain.py`)."""
    return _is_short_control_request(_REPEAT_PATTERNS, text)


def is_slower_pace_request(text: str) -> bool:
    """Return True when the caller asks the receptionist to speak more slowly (`brain.py`)."""
    return _is_short_control_request(_SPEED_SLOW_PATTERNS, text)


def is_normal_pace_request(text: str) -> bool:
    """Return True when the caller asks to restore normal speaking speed (`brain.py`)."""
    return _is_short_control_request(_SPEED_NORMAL_PATTERNS, text)


def is_callback_request(text: str) -> bool:
    """Return True when a waiting caller asks for a callback instead (`brain.py`)."""
    return bool(_CALLBACK_RE.search(text))


def is_goodbye_request(text: str) -> bool:
    """Return True when the caller is signing off (`brain.py` `_is_goodbye`)."""
    return (
        _is_short_control_request(_HANGUP_VOICE_PATTERNS, text) or _DONE_RE.search(text) is not None
    )


def classify_pending_offer_reply(
    text: str,
    pending_offer: str,
) -> Literal["accept", "decline", "none"]:
    """Classify a whole-turn reply to a pending receptionist offer (`brain.py` lines 222-244)."""
    if not pending_offer or not text.strip():
        return "none"
    if _OFFER_DECLINE_RE.search(text):
        return "decline"
    if _OFFER_ACCEPT_RE.search(text):
        return "accept"
    if pending_offer == "more" and _MORE_ACCEPT_RE.search(text):
        return "accept"
    return "none"


def classify_spoken_call_review(
    text: str,
) -> Literal["positive", "neutral", "negative", "unclear"]:
    """Deterministically classify a caller's spoken answer to 'Was this call helpful?' (`review.py`)."""
    clean = (text or "").strip()
    if not clean or _REVIEW_DECLINE_RE.search(clean):
        return "unclear"
    if _REVIEW_NEUTRAL_NEGATED_RE.search(clean):
        return "neutral"
    if _REVIEW_NEGATIVE_RE.search(clean):
        return "negative"
    if _REVIEW_NEUTRAL_RE.search(clean):
        return "neutral"
    if _REVIEW_POSITIVE_RE.search(clean):
        return "positive"
    if _OFFER_ACCEPT_RE.search(clean):
        return "positive"
    if _OFFER_DECLINE_RE.search(clean):
        return "negative"
    if _REVIEW_WEAK_NEUTRAL_RE.search(clean):
        return "neutral"
    return "unclear"


def _ends_mid_procedure_sentence(sentence: str) -> bool:
    if _TRAILING_ABBREVIATION_RE.search(sentence):
        return True
    match = _TRAILING_LIST_NUMBER_RE.search(sentence)
    if match is None:
        return False
    number = int(match.group(1))
    before = sentence[: match.start()].rstrip()
    if not before:
        return True
    if number == 1:
        return before.endswith(":")
    return re.search(rf"(?:^|\s){number - 1}\.\s", sentence) is not None


def split_receptionist_spoken_sentences(text: str) -> list[str]:
    """Split text into sentences while keeping numbered procedures and abbreviations attached (`brain.py`)."""
    sentences: list[str] = []
    for piece in re.split(r"(?<=[.!?؟])\s+", text.strip()):
        piece = piece.strip()
        if not piece:
            continue
        if sentences and _ends_mid_procedure_sentence(sentences[-1]):
            sentences[-1] = f"{sentences[-1]} {piece}"
        else:
            sentences.append(piece)
    return sentences


@dataclass(frozen=True)
class VoiceTurnOutcome:
    """Outcome of one turn in a stateful multi-turn `VoiceCallSession`."""

    session_id: str
    phase: Literal["opening_disclosure", "recording_consent", "active_ai", "transferred", "ended"]
    turn_index: int
    decision: VoiceSessionDecision | None
    ignored_as_echo: bool = False
    ignored_as_backchannel: bool = False
    consecutive_low_confidence_turns: int = 0
    heard_assistant_context: str = ""
    control_action_applied: str | None = None
    spoken_response_text: str | None = None
    speech_rate_slow: bool = False
    pending_offer: str = ""


class VoiceCallSession:
    """Stateful multi-turn voice call controller (`ADR-027` & `FinalYearProject` `brain.py`/`state.py`).

    Connects opening disclosure, opt-in recording consent, post-TTS echo suppression, backchannel
    filtering, barge-in context trimming, in-call receptionist controls (`repeat`, `slower`,
    `normal_speed`, `more_detail`, `accept_offer`, `decline_offer`, `request_callback`), pending
    offer interruption protection (`offer_interrupted`), transfer wait epochs, and multi-turn
    recovery across turns.
    """

    def __init__(
        self,
        *,
        session_id: str,
        locale: LocaleCode,
        recording_offered: bool = True,
        wer_evidence: Mapping[LocaleCode, VoiceWerEvidence] = APPROVED_VOICE_WER_EVIDENCE,
        enable_spoken_clarify_gate: bool = True,
    ) -> None:
        self.session_id = session_id
        self.locale = locale
        self.recording_offered = recording_offered
        self.wer_evidence = wer_evidence
        self.enable_spoken_clarify_gate = enable_spoken_clarify_gate
        self.phase: Literal[
            "opening_disclosure", "recording_consent", "active_ai", "transferred", "ended"
        ] = "opening_disclosure"
        self.disclosure_playing: bool = False
        self.recording_consent_granted: bool = False
        self.turn_index: int = 0
        self.consecutive_low_confidence_turns: int = 0
        self.last_assistant_spoken_text: str = ""
        self.last_interrupted_unspoken_text: str = ""
        self.history: list[dict[str, Any]] = []
        self.speech_rate_slow: bool = False
        self.pending_offer: str = ""
        self.pending_offer_reason: str = ""
        self.more_detail_text: str = ""
        self.last_more_detail_text: str = ""
        self.offer_interrupted: bool = False
        self.offer_at_risk: bool = False
        self.risk_offer_made: bool = False
        self.queue_epoch: int = 0
        self.needs_callback: bool = False
        self.spoken_review_rating: Literal["positive", "neutral", "negative", "unclear", ""] = ""
        self._total_history_seq: int = 0

    def _append_history_entry(
        self,
        speaker: Literal["caller", "assistant"],
        text: str,
        *,
        interrupted: bool = False,
    ) -> None:
        self._total_history_seq += 1
        redacted = redact_pii(text).redacted_text
        entry: dict[str, Any] = {
            "speaker": speaker,
            "text": redacted,
            "seq": self._total_history_seq,
        }
        if speaker == "assistant":
            entry["interrupted"] = interrupted
        self.history.append(entry)
        if len(self.history) > 100:
            self.history.pop(0)

    def set_pending_offer(
        self,
        offer: Literal["", "officer", "more", "confirm", "review"],
        *,
        reason: str = "",
        more_detail: str = "",
        at_risk: bool = False,
    ) -> None:
        """Open a pending yes/no or more-detail offer at the end of an assistant turn (`brain.py`)."""
        self.pending_offer = offer
        self.pending_offer_reason = reason
        self.more_detail_text = more_detail
        if more_detail:
            self.last_more_detail_text = more_detail
        self.offer_interrupted = False
        self.offer_at_risk = at_risk
        if at_risk:
            self.risk_offer_made = True

    def _take_pending_offer(self) -> tuple[str, str, str, bool]:
        offer = self.pending_offer
        reason = self.pending_offer_reason
        more = self.more_detail_text
        at_risk = self.offer_at_risk
        self.pending_offer = ""
        self.pending_offer_reason = ""
        self.more_detail_text = ""
        self.offer_interrupted = False
        self.offer_at_risk = False
        return offer, reason, more, at_risk

    def begin_transfer_wait(self) -> int:
        """Enter `transferred` wait mode and bump `queue_epoch` so stale timers become no-ops (`transfer.py`)."""
        self.phase = "transferred"
        self.queue_epoch += 1
        return self.queue_epoch

    def end_transfer_wait(self, *, timed_out: bool = False) -> int:
        """Leave `transferred` wait mode and bump `queue_epoch`; record `needs_callback` on timeout (`transfer.py`)."""
        self.queue_epoch += 1
        if timed_out:
            self.needs_callback = True
            self.phase = "active_ai"
        return self.queue_epoch

    def build_call_state_frame(
        self,
        *,
        turn_phase: Literal["listening", "thinking", "speaking"] = "listening",
    ) -> dict[str, Any]:
        """Build the `call_state` frame broadcast to the caller's screen (`brain.py` `_publish_call_state`)."""
        has_more = bool(self.more_detail_text or self.last_more_detail_text)
        return {
            "type": "call_state",
            "phase": turn_phase,
            "pending_offer": self.pending_offer,
            "speech_rate_slow": self.speech_rate_slow,
            "has_more_detail": has_more,
            "has_last_answer": bool(self.last_assistant_spoken_text),
        }

    def handle_call_control(
        self,
        action: Literal[
            "repeat",
            "slower",
            "normal_speed",
            "more_detail",
            "accept_offer",
            "decline_offer",
            "request_callback",
        ],
    ) -> VoiceTurnOutcome:
        """Execute an explicit on-screen CallControlFrame / RequestCallbackFrame action (`brain.py`)."""
        if self.phase == "ended":
            return VoiceTurnOutcome(
                session_id=self.session_id,
                phase=self.phase,
                turn_index=self.turn_index,
                decision=None,
                consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
                heard_assistant_context=self.last_assistant_spoken_text,
                speech_rate_slow=self.speech_rate_slow,
                pending_offer=self.pending_offer,
            )
        self.offer_interrupted = False
        if action == "request_callback":
            if self.phase == "transferred":
                self.end_transfer_wait(timed_out=True)
            else:
                self.needs_callback = True
            return VoiceTurnOutcome(
                session_id=self.session_id,
                phase=self.phase,
                turn_index=self.turn_index,
                decision=None,
                consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
                heard_assistant_context=self.last_assistant_spoken_text,
                control_action_applied="callback_requested",
                spoken_response_text="Understood. An SSRA officer will call you back.",
                speech_rate_slow=self.speech_rate_slow,
                pending_offer=self.pending_offer,
            )
        if action == "repeat":
            return self.process_caller_turn(transcript="repeat that")
        if action in ("slower", "normal_speed"):
            self.turn_index += 1
            self.speech_rate_slow = action == "slower"
            ack = (
                "Okay, I will speak more slowly."
                if self.speech_rate_slow
                else "Okay, I will speak at a normal pace."
            )
            return VoiceTurnOutcome(
                session_id=self.session_id,
                phase=self.phase,
                turn_index=self.turn_index,
                decision=None,
                consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
                heard_assistant_context=self.last_assistant_spoken_text,
                control_action_applied=action,
                spoken_response_text=ack,
                speech_rate_slow=self.speech_rate_slow,
                pending_offer=self.pending_offer,
            )
        if action == "more_detail":
            more_txt = self.more_detail_text or self.last_more_detail_text
            self._take_pending_offer()
            self.last_more_detail_text = ""
            if more_txt:
                self.turn_index += 1
                self.record_assistant_reply(more_txt)
            return VoiceTurnOutcome(
                session_id=self.session_id,
                phase=self.phase,
                turn_index=self.turn_index,
                decision=None,
                consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
                heard_assistant_context=self.last_assistant_spoken_text,
                control_action_applied="more_detail",
                spoken_response_text=more_txt or None,
                speech_rate_slow=self.speech_rate_slow,
                pending_offer=self.pending_offer,
            )
        if action == "accept_offer":
            return self.process_caller_turn(transcript="yes")
        return self.process_caller_turn(transcript="no")

    def start_call(self) -> list[VoicePrompt]:
        """Play the opening AI disclosure and, if offered, request opt-in recording consent."""
        prompts = build_call_opening_prompts(self.locale, recording_offered=self.recording_offered)
        self.last_assistant_spoken_text = " ".join(p.text for p in prompts)
        self.disclosure_playing = True
        self.phase = "opening_disclosure"
        return prompts

    def mark_disclosure_finished(self) -> None:
        """Mark the non-interruptible AI disclosure as finished and advance to consent or active AI."""
        self.disclosure_playing = False
        if self.phase == "opening_disclosure":
            self.phase = "recording_consent" if self.recording_offered else "active_ai"

    def submit_recording_consent(self, dtmf_digit: str | None) -> VoiceTurnOutcome:
        """Record keypad 1 consent (or continue unrecorded on 2/None); keypad 0 transfers to an officer."""
        self.disclosure_playing = False
        if dtmf_digit == "0":
            decision = route_voice_turn(
                session_id=self.session_id,
                locale=self.locale,
                recording_consent_granted=False,
                wer_evidence=self.wer_evidence,
                dtmf_digit="0",
            )
            self.begin_transfer_wait()
            return VoiceTurnOutcome(
                session_id=self.session_id,
                phase=self.phase,
                turn_index=self.turn_index,
                decision=decision,
                consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
                heard_assistant_context=self.last_assistant_spoken_text,
                speech_rate_slow=self.speech_rate_slow,
                pending_offer=self.pending_offer,
            )
        self.recording_consent_granted = resolve_recording_consent(dtmf_digit)
        self.phase = "active_ai"
        return VoiceTurnOutcome(
            session_id=self.session_id,
            phase=self.phase,
            turn_index=self.turn_index,
            decision=None,
            consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
            heard_assistant_context=self.last_assistant_spoken_text,
            speech_rate_slow=self.speech_rate_slow,
            pending_offer=self.pending_offer,
        )

    def prepare_spoken_answer(
        self,
        reply_text: str,
        *,
        offer_officer: bool = False,
        at_risk: bool = False,
        max_sentences: int = MAX_SPOKEN_SENTENCES,
    ) -> str:
        """Structure an assistant reply for the Call Receptionist (`brain.py` `_spoken_answer` parity).

        1. Strips visual chat footers (`You might also want to know...`).
        2. Splits by procedure-safe sentences (`split_receptionist_spoken_sentences`).
        3. Keeps up to *max_sentences* and stores any overflow in `more_detail_text`.
        4. Appends at most one yes/no question (`officer` offer wins over `more` detail).
        5. Normalizes contact info, USSD codes, `.gov.ss` domains, and numbered steps via `clean_text_for_speech`.
        """
        cleaned_reply = _SPEECH_VISUAL_FOOTER_RE.sub("", reply_text or "").strip() or (
            reply_text or ""
        )
        sentences = split_receptionist_spoken_sentences(cleaned_reply)
        rest = sentences[max_sentences:]
        spoken_core = " ".join(sentences[:max_sentences]) if rest else cleaned_reply
        rest_joined = " ".join(rest).strip()
        if offer_officer:
            self.last_more_detail_text = ""
            self.set_pending_offer("officer", reason="offer_accepted", at_risk=at_risk)
            offer_q = _RECEPTIONIST_OFFICER_OFFER_BY_LOCALE.get(
                self.locale, _RECEPTIONIST_OFFICER_OFFER_BY_LOCALE[LocaleCode.EN]
            )
            combined = f"{spoken_core} {offer_q}".strip()
        elif rest_joined:
            self.set_pending_offer("more", more_detail=rest_joined)
            offer_q = _RECEPTIONIST_MORE_OFFER_BY_LOCALE.get(
                self.locale, _RECEPTIONIST_MORE_OFFER_BY_LOCALE[LocaleCode.EN]
            )
            combined = f"{spoken_core} {offer_q}".strip()
        else:
            combined = spoken_core
        spoken_clean = clean_text_for_speech(combined, locale=self.locale)
        self.record_assistant_reply(spoken_clean)
        return spoken_clean

    def record_assistant_reply(
        self,
        reply_text: str,
        *,
        interrupted_at_sentence: int | None = None,
    ) -> str:
        """Record what the assistant actually spoke, trimming unspoken sentences on barge-in."""
        sentences = split_receptionist_spoken_sentences(reply_text)
        was_interrupted = (
            interrupted_at_sentence is not None and 0 <= interrupted_at_sentence < len(sentences)
        )
        if was_interrupted and interrupted_at_sentence is not None:
            heard = " ".join(sentences[:interrupted_at_sentence]).strip()
            unspoken = " ".join(sentences[interrupted_at_sentence:]).strip()
            if self.pending_offer:
                self.offer_interrupted = True
        else:
            heard = " ".join(sentences).strip()
            unspoken = ""
        self.last_assistant_spoken_text = heard
        self.last_interrupted_unspoken_text = unspoken
        if heard:
            self._append_history_entry("assistant", heard, interrupted=bool(unspoken))
        return heard

    def _build_officer_transfer_decision(
        self, reason: str, *, barge_in: bool = False
    ) -> VoiceSessionDecision:
        return VoiceSessionDecision(
            session_id=self.session_id,
            locale=self.locale,
            asr_engine=ASR_MODEL_BY_LOCALE[self.locale],
            tts_engine=TTS_MODEL_BY_LOCALE[self.locale],
            recording_enabled=self.recording_consent_granted,
            cancel_active_reply=barge_in,
            asr_rejected_reason=None,
            action="WARM_TRANSFER_TO_OFFICER",
            warm_transfer_summary=f"Warm transfer from IVR ({self.locale.value}): {reason}.",
        )

    def process_caller_turn(
        self,
        *,
        transcript: str = "",
        dtmf_digit: str | None = None,
        assistant_speaking: bool = False,
        elapsed_since_tts_end_ms: int | float | None = None,
        utterance_confidence: float = 0.95,
        whisper_signals: WhisperSegmentSignals | None = None,
    ) -> VoiceTurnOutcome:
        """Process one caller turn while preserving multi-turn continuity, echo suppression, and recovery."""
        if self.phase == "ended":
            return VoiceTurnOutcome(
                session_id=self.session_id,
                phase=self.phase,
                turn_index=self.turn_index,
                decision=None,
                consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
                heard_assistant_context=self.last_assistant_spoken_text,
                speech_rate_slow=self.speech_rate_slow,
                pending_offer=self.pending_offer,
            )
        if dtmf_digit == "0":
            self.disclosure_playing = False
        if self.disclosure_playing and dtmf_digit is None:
            return VoiceTurnOutcome(
                session_id=self.session_id,
                phase=self.phase,
                turn_index=self.turn_index,
                decision=None,
                consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
                heard_assistant_context=self.last_assistant_spoken_text,
                speech_rate_slow=self.speech_rate_slow,
                pending_offer=self.pending_offer,
            )
        if self.phase in ("opening_disclosure", "recording_consent") and dtmf_digit in ("1", "2"):
            return self.submit_recording_consent(dtmf_digit)
        if self.phase in ("opening_disclosure", "recording_consent"):
            self.disclosure_playing = False
            self.phase = "active_ai"

        clean_tx = transcript.strip()
        if dtmf_digit is None and clean_tx:
            effective_elapsed = 0.0 if assistant_speaking else elapsed_since_tts_end_ms
            if is_likely_tts_echo(
                clean_tx,
                self.last_assistant_spoken_text,
                elapsed_since_tts_end_ms=effective_elapsed,
            ):
                return VoiceTurnOutcome(
                    session_id=self.session_id,
                    phase=self.phase,
                    turn_index=self.turn_index,
                    decision=None,
                    ignored_as_echo=True,
                    consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
                    heard_assistant_context=self.last_assistant_spoken_text,
                    speech_rate_slow=self.speech_rate_slow,
                    pending_offer=self.pending_offer,
                )
            if assistant_speaking and is_backchannel_utterance(clean_tx):
                return VoiceTurnOutcome(
                    session_id=self.session_id,
                    phase=self.phase,
                    turn_index=self.turn_index,
                    decision=None,
                    ignored_as_backchannel=True,
                    consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
                    heard_assistant_context=self.last_assistant_spoken_text,
                    speech_rate_slow=self.speech_rate_slow,
                    pending_offer=self.pending_offer,
                )

        if self.phase == "transferred" and dtmf_digit is None:
            if is_callback_request(clean_tx):
                return self.handle_call_control("request_callback")
            if is_goodbye_request(clean_tx):
                self.turn_index += 1
                self.phase = "ended"
                return VoiceTurnOutcome(
                    session_id=self.session_id,
                    phase=self.phase,
                    turn_index=self.turn_index,
                    decision=None,
                    consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
                    heard_assistant_context=self.last_assistant_spoken_text,
                    control_action_applied="caller_voice_hangup",
                    spoken_response_text="Thank you for calling SSRA Assist. Goodbye.",
                    speech_rate_slow=self.speech_rate_slow,
                    pending_offer=self.pending_offer,
                )
            self.turn_index += 1
            return VoiceTurnOutcome(
                session_id=self.session_id,
                phase=self.phase,
                turn_index=self.turn_index,
                decision=None,
                consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
                heard_assistant_context=self.last_assistant_spoken_text,
                control_action_applied="waiting_for_officer",
                spoken_response_text="Please hold while we connect you to an SSRA officer, or say call me back.",
                speech_rate_slow=self.speech_rate_slow,
                pending_offer=self.pending_offer,
            )

        # Resolve pending offer replies and spoken in-call receptionist controls (`brain.py` lines 783-895)
        if dtmf_digit is None and clean_tx:
            unheard = self.offer_interrupted
            offer, offer_reason, more_txt, offer_at_risk = self._take_pending_offer()
            if offer == "review" and not unheard:
                self.spoken_review_rating = classify_spoken_call_review(clean_tx)
                self.turn_index += 1
                return VoiceTurnOutcome(
                    session_id=self.session_id,
                    phase=self.phase,
                    turn_index=self.turn_index,
                    decision=None,
                    consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
                    heard_assistant_context=self.last_assistant_spoken_text,
                    control_action_applied="review_recorded",
                    spoken_response_text="Thank you for your feedback.",
                    speech_rate_slow=self.speech_rate_slow,
                    pending_offer=self.pending_offer,
                )
            offer_reply = classify_pending_offer_reply(clean_tx, offer)
            if offer and offer_reply != "none" and unheard:
                self.set_pending_offer(
                    offer,  # type: ignore[arg-type]
                    reason=offer_reason,
                    more_detail=more_txt,
                    at_risk=offer_at_risk,
                )
                reask = (
                    "Would you like more detail?"
                    if offer == "more"
                    else "Would you like to speak with an SSRA officer?"
                )
                self.turn_index += 1
                return VoiceTurnOutcome(
                    session_id=self.session_id,
                    phase=self.phase,
                    turn_index=self.turn_index,
                    decision=None,
                    consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
                    heard_assistant_context=self.last_assistant_spoken_text,
                    control_action_applied="reask_unheard_offer",
                    spoken_response_text=reask,
                    speech_rate_slow=self.speech_rate_slow,
                    pending_offer=self.pending_offer,
                )
            if offer and offer_reply == "decline":
                if offer == "more":
                    self.last_more_detail_text = ""
                self.turn_index += 1
                return VoiceTurnOutcome(
                    session_id=self.session_id,
                    phase=self.phase,
                    turn_index=self.turn_index,
                    decision=None,
                    consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
                    heard_assistant_context=self.last_assistant_spoken_text,
                    control_action_applied="offer_declined",
                    spoken_response_text="Alright. Let me know if you have another question.",
                    speech_rate_slow=self.speech_rate_slow,
                    pending_offer=self.pending_offer,
                )
            if offer == "officer" and offer_reply == "accept":
                self.turn_index += 1
                self.begin_transfer_wait()
                decision = self._build_officer_transfer_decision(
                    offer_reason or "offer_accepted", barge_in=assistant_speaking
                )
                return VoiceTurnOutcome(
                    session_id=self.session_id,
                    phase=self.phase,
                    turn_index=self.turn_index,
                    decision=decision,
                    consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
                    heard_assistant_context=self.last_assistant_spoken_text,
                    control_action_applied="offer_accepted_officer",
                    speech_rate_slow=self.speech_rate_slow,
                    pending_offer=self.pending_offer,
                )
            if offer == "more" and offer_reply == "accept":
                self.turn_index += 1
                self.last_more_detail_text = ""
                if more_txt:
                    self.record_assistant_reply(more_txt)
                return VoiceTurnOutcome(
                    session_id=self.session_id,
                    phase=self.phase,
                    turn_index=self.turn_index,
                    decision=None,
                    consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
                    heard_assistant_context=self.last_assistant_spoken_text,
                    control_action_applied="offer_accepted_more",
                    spoken_response_text=more_txt or None,
                    speech_rate_slow=self.speech_rate_slow,
                    pending_offer=self.pending_offer,
                )
            if offer_at_risk and unheard:
                self.risk_offer_made = False

            if is_spoken_officer_request(clean_tx) or is_tax_dispute(clean_tx):
                is_dispute = is_tax_dispute(clean_tx) and not is_spoken_officer_request(clean_tx)
                self.turn_index += 1
                self._append_history_entry("caller", clean_tx)
                self.begin_transfer_wait()
                decision = self._build_officer_transfer_decision(
                    "tax_dispute_escalation" if is_dispute else "caller_requested",
                    barge_in=assistant_speaking,
                )
                return VoiceTurnOutcome(
                    session_id=self.session_id,
                    phase=self.phase,
                    turn_index=self.turn_index,
                    decision=decision,
                    consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
                    heard_assistant_context=self.last_assistant_spoken_text,
                    control_action_applied=(
                        "tax_dispute_escalation" if is_dispute else "spoken_officer_request"
                    ),
                    speech_rate_slow=self.speech_rate_slow,
                    pending_offer=self.pending_offer,
                )

            if is_repeat_request(clean_tx) and self.last_assistant_spoken_text:
                if offer:
                    self.set_pending_offer(
                        offer,  # type: ignore[arg-type]
                        reason=offer_reason,
                        more_detail=more_txt,
                        at_risk=offer_at_risk,
                    )
                self.turn_index += 1
                repeated = f"Sure, let me repeat that: {self.last_assistant_spoken_text}"
                return VoiceTurnOutcome(
                    session_id=self.session_id,
                    phase=self.phase,
                    turn_index=self.turn_index,
                    decision=None,
                    consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
                    heard_assistant_context=self.last_assistant_spoken_text,
                    control_action_applied="repeat",
                    spoken_response_text=repeated,
                    speech_rate_slow=self.speech_rate_slow,
                    pending_offer=self.pending_offer,
                )

            if is_slower_pace_request(clean_tx):
                if offer:
                    self.set_pending_offer(
                        offer,  # type: ignore[arg-type]
                        reason=offer_reason,
                        more_detail=more_txt,
                        at_risk=offer_at_risk,
                    )
                return self.handle_call_control("slower")

            if is_normal_pace_request(clean_tx):
                if offer:
                    self.set_pending_offer(
                        offer,  # type: ignore[arg-type]
                        reason=offer_reason,
                        more_detail=more_txt,
                        at_risk=offer_at_risk,
                    )
                return self.handle_call_control("normal_speed")

            if not offer and _MORE_ACCEPT_RE.search(clean_tx) and self.last_more_detail_text:
                return self.handle_call_control("more_detail")

            if is_goodbye_request(clean_tx):
                self.turn_index += 1
                self.phase = "ended"
                return VoiceTurnOutcome(
                    session_id=self.session_id,
                    phase=self.phase,
                    turn_index=self.turn_index,
                    decision=None,
                    consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
                    heard_assistant_context=self.last_assistant_spoken_text,
                    control_action_applied="caller_voice_hangup",
                    spoken_response_text="Thank you for calling SSRA Assist. Goodbye.",
                    speech_rate_slow=self.speech_rate_slow,
                    pending_offer=self.pending_offer,
                )

        asr_verdict = (
            assess_whisper_segment(whisper_signals) if whisper_signals is not None else "accept"
        )
        is_low_conf_spoken_turn = dtmf_digit is None and (
            asr_verdict != "accept" or utterance_confidence < MIN_UTTERANCE_ASR_CONFIDENCE
        )
        next_low_conf_count = (
            self.consecutive_low_confidence_turns + 1 if is_low_conf_spoken_turn else 0
        )

        decision = route_voice_turn(
            session_id=self.session_id,
            locale=self.locale,
            recording_consent_granted=self.recording_consent_granted,
            wer_evidence=self.wer_evidence,
            dtmf_digit=dtmf_digit,
            barge_in_detected=assistant_speaking,
            utterance_confidence=utterance_confidence,
            consecutive_low_confidence_turns=next_low_conf_count,
            enable_spoken_clarify_gate=self.enable_spoken_clarify_gate,
            whisper_signals=whisper_signals,
        )
        self.turn_index += 1
        self.consecutive_low_confidence_turns = next_low_conf_count
        if clean_tx and asr_verdict == "accept":
            self._append_history_entry("caller", clean_tx)
        if decision.action == "WARM_TRANSFER_TO_OFFICER":
            self.begin_transfer_wait()
        return VoiceTurnOutcome(
            session_id=self.session_id,
            phase=self.phase,
            turn_index=self.turn_index,
            decision=decision,
            consecutive_low_confidence_turns=self.consecutive_low_confidence_turns,
            heard_assistant_context=self.last_assistant_spoken_text,
            speech_rate_slow=self.speech_rate_slow,
            pending_offer=self.pending_offer,
        )


@dataclass(frozen=True)
class HybridVoiceRouteDecision:
    """Decision from the October 2026 Hybrid Speech Router."""

    mode: Literal["S2S_FAST_ACK_CACHED", "CASCADED_GOVERNED_STT_LLM_TTS"]
    emit_tool_wait_filler: bool
    filler_text: str | None
    target_ttfa_ms: int
    requires_numeric_provenance: bool


def select_hybrid_voice_execution_mode(
    *,
    locale: LocaleCode = LocaleCode.EN,
    requires_tool_call: bool = True,
    contains_statutory_figures: bool = True,
    is_pure_greeting_or_backchannel: bool = False,
) -> HybridVoiceRouteDecision:
    """Select between `S2S_FAST_ACK_CACHED` (<250ms TTFA) and `CASCADED_GOVERNED_STT_LLM_TTS`.

    Invariant: Any turn involving MCP tools, OPA policies, or statutory figures MUST use
    `CASCADED_GOVERNED_STT_LLM_TTS` (optionally preceded by a pre-cached tool-wait filler).
    """
    is_fast_ack = (
        is_pure_greeting_or_backchannel
        and not requires_tool_call
        and not contains_statutory_figures
    )
    if is_fast_ack:
        return HybridVoiceRouteDecision(
            mode="S2S_FAST_ACK_CACHED",
            emit_tool_wait_filler=False,
            filler_text=None,
            target_ttfa_ms=220,
            requires_numeric_provenance=False,
        )
    filler = get_localized_tool_wait_filler(locale) if requires_tool_call else None
    return HybridVoiceRouteDecision(
        mode="CASCADED_GOVERNED_STT_LLM_TTS",
        emit_tool_wait_filler=requires_tool_call,
        filler_text=filler,
        target_ttfa_ms=240 if requires_tool_call else 380,
        requires_numeric_provenance=True,
    )


_MASKED_TIN_SPEECH_RE = re.compile(
    r"(?:(?:\bTIN|\bT\.I\.N\.)\s+)?(?:••••|\*{4,8})(\d{4})\b",
    flags=re.IGNORECASE,
)
_EXPLICIT_TIN_HYPHEN_SPEECH_RE = re.compile(
    r"\b(?:T-?I-?N|T\.I\.N\.)(?::|\s+is|\s+number|\s+no\.?)?\s*(\d{3})-(\d{3})-(\d{4})\b",
    flags=re.IGNORECASE,
)
_SEC_ANCHOR_SPEECH_RE = re.compile(r"\bPart-([IVX]+)-Sec-(\d+)\b", flags=re.IGNORECASE)
_SPOOFED_USERINFO_URL_SPEECH_RE = re.compile(
    r"\bhttps?://[^\s/@]{1,128}@[^\s.,;:!?)]{1,256}",
    flags=re.IGNORECASE,
)
_ALLOWED_GOV_SS_HOSTS_PATTERN = (
    r"(?:(?:www\.)?(?:etax\.nra|ecustoms\.nra|cms\.nra|nra|etax\.ssra|assist\.ssra|ssra|"
    r"business\.eservices|customs\.eservices|trade\.eservices|eservices|mofp|boss|mojca)\.gov\.ss)"
)
_OFFICIAL_GOV_SS_URL_SPEECH_RE = re.compile(
    rf"(?<![A-Za-z0-9@.-])(?:https?://)?({_ALLOWED_GOV_SS_HOSTS_PATTERN})(?:/(?![^\s]*@)[^\s.,;:!?)]*)?(?=$|\s|[,;:!?)](?=$|\s)|\.+(?=$|\s))",
    flags=re.IGNORECASE,
)
_EMAIL_SPEECH_RE = re.compile(
    r"(?<![:/A-Za-z0-9._%+-])\b([A-Za-z0-9._%+-]{1,64})@([A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){1,4})\b(?![/])",
    flags=re.IGNORECASE,
)
_USSD_CODE_SPEECH_RE = re.compile(r"(?<!\w)\*(\d{2,4}(?:\*\d{1,4}){0,5})#(?!\w)")
_SS_INTL_PHONE_SPEECH_RE = re.compile(
    r"(?<!\w)\+211[ \t-]?(?:\(0\)[ \t-]?)?\(?0?([19]\d{2})\)?[ \t-]?(\d{3})[ \t-]?(\d{3})\b"
)
_SS_LOCAL_PHONE_SPEECH_RE = re.compile(r"(?<![\w+])\(?(0[19]\d{2})\)?[ \t-](\d{3})[ \t-](\d{3})\b")
_TOLLFREE_PHONE_SPEECH_RE = re.compile(r"\b0800[ \t-]*(\d{3})[ \t-]*(\d{3})\b")
_PO_BOX_SPEECH_RE = re.compile(
    r"\bP\.?[ \t]?O\.?[ \t]?Box[ \t]{1,4}(\d{1,6})\b", flags=re.IGNORECASE
)

_DOMAIN_LABEL_SPEECH_EN: dict[str, str] = {
    "etax": "e-tax",
    "ecustoms": "e-customs",
    "eservices": "e-services",
    "nra": "n r a",
    "ssra": "s s r a",
    "mofp": "m o f p",
    "boss": "b o s s",
    "mojca": "m o j c a",
    "cms": "c m s",
    "gov": "gov",
    "ss": "s s",
}
_DOMAIN_LABEL_SPEECH_AR: dict[str, str] = {
    "etax": "إي تاكس",
    "ecustoms": "إي كاستمز",
    "eservices": "إي سيرفيسز",
    "nra": "إن آر إيه",
    "ssra": "إس إس آر إيه",
    "mofp": "إم أو إف بي",
    "boss": "بي أو إس إس",
    "mojca": "إم أو جيه سي إيه",
    "cms": "سي إم إس",
    "gov": "جوف",
    "ss": "إس إس",
}


def _format_domain_for_speech(domain: str, locale: LocaleCode = LocaleCode.EN) -> str:
    """Pronounce a domain name naturally (`etax.nra.gov.ss` -> `e-tax dot n r a dot gov dot s s`)."""
    host = domain.strip().lower().removeprefix("www.")
    labels = [lbl for lbl in host.split(".") if lbl]
    label_map = _DOMAIN_LABEL_SPEECH_AR if locale == LocaleCode.AR else _DOMAIN_LABEL_SPEECH_EN
    dot_word = " دوت " if locale == LocaleCode.AR else " dot "
    spoken_labels = [label_map.get(lbl, lbl) for lbl in labels]
    return dot_word.join(spoken_labels)


def _format_email_local_for_speech(user: str, locale: LocaleCode = LocaleCode.EN) -> str:
    """Format an email local-part so dots, underscores, hyphens, pluses, and digits are spoken naturally."""
    dot_word = " دوت " if locale == LocaleCode.AR else " dot "
    out = (
        user.replace(".", dot_word)
        .replace("_", " underscore ")
        .replace("-", " dash ")
        .replace("+", " plus ")
    )
    out = re.sub(r"\betax\b", "e-tax", out, flags=re.IGNORECASE)
    out = re.sub(r"\becustoms\b", "e-customs", out, flags=re.IGNORECASE)
    out = re.sub(r"\d", lambda d: f" {d.group(0)} ", out)
    return re.sub(r"[ \t]+", " ", out).strip()


def _format_ussd_for_speech(code_body: str, locale: LocaleCode = LocaleCode.EN) -> str:
    """Pronounce USSD shortcodes such as `*311#` naturally across `en`, `ar`, `pga`, and Nilotic/Zande locales."""
    star_word = "نجمة" if locale == LocaleCode.AR else "star"
    hash_word = (
        "شباك" if locale == LocaleCode.AR else ("shibak" if locale == LocaleCode.PGA else "hash")
    )
    segments = [" ".join(seg) for seg in code_body.split("*")]
    return f"{star_word} {f' {star_word} '.join(segments)} {hash_word}"


def normalize_statutory_text_for_speech(text: str, locale: LocaleCode = LocaleCode.EN) -> str:
    """Expand statutory anchors, masked TINs, contact details, and verified official portal URLs for natural TTS pronunciation."""
    is_ar = locale == LocaleCode.AR
    tin_end_prefix = "الرقم الضريبي المنتهي بـ" if is_ar else "T I N ending in"
    at_word = "آت" if is_ar else "at"
    plus_word = "زائد" if is_ar else "plus"
    web_link_word = "رابط إلكتروني" if is_ar else "web link"

    out = _SPOOFED_USERINFO_URL_SPEECH_RE.sub(web_link_word, text)
    out = _USSD_CODE_SPEECH_RE.sub(
        lambda m: _format_ussd_for_speech(m.group(1), locale),
        out,
    )
    out = _MASKED_TIN_SPEECH_RE.sub(
        lambda m: f"{tin_end_prefix} {' '.join(m.group(1))}",
        out,
    )
    out = _EXPLICIT_TIN_HYPHEN_SPEECH_RE.sub(
        lambda m: f"T I N {' '.join(m.group(1))}, {' '.join(m.group(2))}, {' '.join(m.group(3))}",
        out,
    )
    out = _SEC_ANCHOR_SPEECH_RE.sub(
        lambda m: f"Part {m.group(1)}, Section {m.group(2)}",
        out,
    )
    out = _EMAIL_SPEECH_RE.sub(
        lambda m: (
            f"{_format_email_local_for_speech(m.group(1), locale)} {at_word} "
            f"{_format_domain_for_speech(m.group(2), locale)}"
        ),
        out,
    )
    out = _OFFICIAL_GOV_SS_URL_SPEECH_RE.sub(
        lambda m: _format_domain_for_speech(m.group(1), locale),
        out,
    )
    out = _SS_INTL_PHONE_SPEECH_RE.sub(
        lambda m: (
            f"{plus_word} 2 1 1, {' '.join(m.group(1))}, "
            f"{' '.join(m.group(2))}, {' '.join(m.group(3))}"
        ),
        out,
    )
    out = _SS_LOCAL_PHONE_SPEECH_RE.sub(
        lambda m: f"{' '.join(m.group(1))}, {' '.join(m.group(2))}, {' '.join(m.group(3))}",
        out,
    )
    out = _TOLLFREE_PHONE_SPEECH_RE.sub(
        lambda m: f"0 800, {' '.join(m.group(1))}, {' '.join(m.group(2))}",
        out,
    )
    out = _PO_BOX_SPEECH_RE.sub(
        lambda m: f"P O Box {' '.join(m.group(1))}",
        out,
    )
    return out


_NUMERIC_TOKEN_RE = re.compile(r"(?<![\d.])\d+(?:\.\d+)?(?![\d.])")
_THOUSANDS_COMMA_RE = re.compile(r"(?<=\d),(?=\d{3})")
_WORD_TOKEN_RE = re.compile(r"[a-z]+|[^\sa-z]+")
_NUMBER_WORDS: dict[str, int] = {
    word: value
    for value, word in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
        "fifteen sixteen seventeen eighteen nineteen".split()
    )
} | {
    word: (index + 2) * 10
    for index, word in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())
}
_SCALE_WORDS: dict[str, int] = {
    "hundred": 100,
    "thousand": 1_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
}
# A lone "one" is a figure only before one of these ("one month"), not in "one of the forms".
_QUANTITY_NOUNS: frozenset[str] = frozenset(
    "day days week weeks month months year years hour hours minute minutes percent pound pounds "
    "dollar dollars ssp usd time times".split()
)


def _ascii_digits(text: str) -> str:
    """Map Arabic-Indic and other Unicode decimal digits to ASCII, with the Arabic separators."""
    mapped: list[str] = []
    for ch in text:
        if ch.isdecimal() and not ch.isascii():
            mapped.append(str(unicodedata.decimal(ch)))
        elif ch == "\u066b":
            mapped.append(".")
        elif ch == "\u066c":
            mapped.append(",")
        else:
            mapped.append(ch)
    return "".join(mapped)


def _continues_number(previous: str, word: str) -> bool:
    if previous in _SCALE_WORDS:
        return True
    return 20 <= _NUMBER_WORDS.get(previous, 0) <= 90 and 1 <= _NUMBER_WORDS[word] <= 9


def _number_phrase_value(phrase: list[str]) -> int:
    total = 0
    current = 0
    for word in phrase:
        if word in _NUMBER_WORDS:
            current += _NUMBER_WORDS[word]
        elif word == "hundred":
            current = (current or 1) * 100
        else:
            total += (current or 1) * _SCALE_WORDS[word]
            current = 0
    return total + current


def _spelled_number_values(text: str) -> set[str]:
    """Return the values of English number words, such as "twenty five thousand" or "one month"."""
    words = _WORD_TOKEN_RE.findall(text.lower().replace("-", " "))
    values: set[str] = set()
    phrase: list[str] = []

    def flush(next_word: str | None) -> None:
        if phrase and not (phrase == ["one"] and next_word not in _QUANTITY_NOUNS):
            values.add(str(_number_phrase_value(phrase)))
        phrase.clear()

    for index, word in enumerate(words):
        following = words[index + 1] if index + 1 < len(words) else None
        if word in _NUMBER_WORDS:
            if phrase and not _continues_number(phrase[-1], word):
                flush(word)
            phrase.append(word)
        elif word in _SCALE_WORDS:
            phrase.append(word)
        elif word == "a" and not phrase and following in _SCALE_WORDS:
            phrase.append("one")
        elif word == "and" and phrase and following in _NUMBER_WORDS:
            continue
        else:
            flush(word)
    flush(None)
    return values


def _spoken_numeric_values(text: str) -> set[str]:
    """Return every figure in text: digits in any script, and spelled-out English numbers."""
    normalized = _THOUSANDS_COMMA_RE.sub("", _ascii_digits(text))
    return set(_NUMERIC_TOKEN_RE.findall(normalized)) | _spelled_number_values(normalized)


def _clean_figure(value: str) -> str:
    return _ascii_digits(str(value)).replace(",", "").strip()


def verify_spoken_figure_fidelity(
    spoken_text: str,
    expected_numeric_values: list[str] | tuple[str, ...],
    *,
    strict_no_extra_numbers: bool = False,
    allowed_context_numbers: list[str] | tuple[str, ...] = (),
) -> bool:
    """Verify that every required `NumericClaim` value is spoken, and in strict mode that nothing else is.

    Figures are read in any digit script and as spelled-out English numbers, so "twelve (3) months"
    carries both 12 and 3. Number words in other languages are not yet read (AUD-041).
    """
    spoken_tokens = _spoken_numeric_values(spoken_text)
    expected_clean = {_clean_figure(val) for val in expected_numeric_values if str(val).strip()}
    for clean_val in expected_clean:
        if clean_val not in spoken_tokens:
            return False
    if strict_no_extra_numbers:
        allowed_all = expected_clean | {
            _clean_figure(c) for c in allowed_context_numbers if str(c).strip()
        }
        if not spoken_tokens.issubset(allowed_all):
            return False
    return True


@dataclass(frozen=True)
class EdgeFieldApplianceProfile:
    """Offline/intermittent Edge Field-Office Appliance Profile for SSRA border posts (`NIMULE_CUSTOMS`, `WAU_BRANCH`, `MALAKAL_BRANCH`)."""

    office_code: str
    backhaul_online: bool
    llm_model: str
    asr_backend: str
    tts_backend: str
    opus_bitrate_kbps: int
    allowed_tiers: tuple[str, ...]
    store_and_forward_outbox_enabled: bool


def resolve_edge_appliance_profile(
    *,
    office_code: str = "NIMULE_CUSTOMS",
    backhaul_online: bool = False,
) -> EdgeFieldApplianceProfile:
    """Select the quantized on-premises edge voice/LLM profile when NCA backhaul is offline or constrained."""
    if backhaul_online:
        return EdgeFieldApplianceProfile(
            office_code=office_code,
            backhaul_online=True,
            llm_model="ssra-sovereign/sunflower-qwen3.5-9b",
            asr_backend="vllm-audio-transcriptions",
            tts_backend="orpheus-3b-tts-multilingual",
            opus_bitrate_kbps=24,
            allowed_tiers=("T0", "T1", "T2", "T3"),
            store_and_forward_outbox_enabled=False,
        )
    return EdgeFieldApplianceProfile(
        office_code=office_code,
        backhaul_online=False,
        llm_model="ssra-sovereign/qwen2.5-3b-cpu-gguf",
        asr_backend="hf-mms-offline-int8",
        tts_backend="hf-mms-tts-offline-int8",
        opus_bitrate_kbps=12,
        allowed_tiers=("T0",),
        store_and_forward_outbox_enabled=True,
    )


@dataclass(frozen=True)
class SpokenNumberVerbalization:
    """Dual-representation envelope holding canonical digit transcript and TTS-friendly verbalized text."""

    canonical_transcript: str
    phonetic_tts_text: str
    figures_verified: bool
    locale: LocaleCode


_CURRENCY_SPEECH_MAP: dict[LocaleCode, tuple[str, str]] = {
    LocaleCode.EN: ("South Sudanese Pounds", "U S Dollars"),
    LocaleCode.AR: ("جنيه جنوب سوداني", "دولار أمريكي"),
    LocaleCode.PGA: ("South Sudanese Pounds", "U S Dollars"),
    LocaleCode.DIN: ("South Sudanese Pounds", "U S Dollars"),
    LocaleCode.NUS: ("South Sudanese Pounds", "U S Dollars"),
    LocaleCode.BFA: ("South Sudanese Pounds", "U S Dollars"),
    LocaleCode.ZNE: ("South Sudanese Pounds", "U S Dollars"),
    LocaleCode.SHK: ("South Sudanese Pounds", "U S Dollars"),
}


def verbalize_statutory_figures_for_tts(
    text: str,
    *,
    locale: LocaleCode = LocaleCode.EN,
    expected_numeric_values: list[str] | tuple[str, ...] = (),
    allowed_context_numbers: list[str] | tuple[str, ...] = (),
) -> SpokenNumberVerbalization:
    """Enforce `FLAG_SPOKEN_FIGURE_GUARD` (`strict_no_extra_numbers=True`) and produce dual canonical-digit + phonetic-currency TTS text."""
    verified = verify_spoken_figure_fidelity(
        text,
        expected_numeric_values,
        strict_no_extra_numbers=True,
        allowed_context_numbers=allowed_context_numbers,
    )
    if not verified:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "FLAG_SPOKEN_FIGURE_GUARD blocked TTS synthesis: spoken figure mismatch with verified NumericClaims",
            status_code=422,
        )
    phonetic = normalize_statutory_text_for_speech(text, locale=locale)
    ssp_word, usd_word = _CURRENCY_SPEECH_MAP.get(locale, _CURRENCY_SPEECH_MAP[LocaleCode.EN])
    phonetic = re.sub(r"\bSSP\b", ssp_word, phonetic)
    phonetic = re.sub(r"\bUSD\b", usd_word, phonetic)
    return SpokenNumberVerbalization(
        canonical_transcript=text,
        phonetic_tts_text=phonetic,
        figures_verified=True,
        locale=locale,
    )


def sync_affective_state_to_call_lobby(
    lobby: CallLobbyManager,
    *,
    call_id: str,
    primary_emotion: str,
    intensity: float,
    frustration_velocity: float,
    signals: list[str] | tuple[str, ...] = (),
) -> LobbyCallEntry:
    """Push real-time acoustic/text emotion spikes into `CallLobbyManager` (`at_risk` / `watch` + priority raise)."""
    if primary_emotion == "distressed" or intensity >= 0.80 or frustration_velocity >= 0.45:
        previous = lobby.calls.get(call_id)
        was_at_risk = previous is not None and previous.risk_level == "at_risk"
        entry = lobby.apply_event(
            "call.risk",
            {"call_id": call_id, "level": "at_risk", "signals": list(signals)},
        )
        if was_at_risk:
            return entry
        return lobby.apply_event(
            "call.priority_raised",
            {"call_id": call_id, "priority": "urgent", "reason": f"eq_{primary_emotion}"},
        )
    if primary_emotion in ("frustrated", "anxious") or intensity >= 0.50:
        return lobby.apply_event(
            "call.risk",
            {"call_id": call_id, "level": "watch", "signals": list(signals)},
        )
    return lobby.apply_event(
        "call.risk",
        {"call_id": call_id, "level": "none", "signals": []},
    )


@dataclass(frozen=True)
class CallToWebCarryover:
    """Symmetric Voice-to-Web carryover descriptor (`VR-G3`) with HMAC-SHA256 integrity signature (`SEC-G5`)."""

    call_id: str
    conversation_id: str
    active_goal_id: str
    resume_step_index: int
    pending_action: str
    local_models_only: bool = True
    issued_at: int = 0
    carryover_hmac: str = ""


CARRYOVER_TTL_SECONDS: int = 900
CARRYOVER_CLOCK_SKEW_SECONDS: int = 60
MIN_CARRYOVER_KEY_BYTES: int = 32


def _carryover_signing_key(signing_salt: str | None) -> bytes:
    """Return the configured carryover key, failing closed when none of adequate length is set."""
    key = signing_salt or os.environ.get("SSRA_VOICE_CARRYOVER_HMAC_KEY") or ""
    key_bytes = key.encode("utf-8")
    if len(key_bytes) < MIN_CARRYOVER_KEY_BYTES:
        raise SSRAError(
            McpErrorCode.UPSTREAM_UNAVAILABLE,
            "Call carryover signing key is not configured (SSRA_VOICE_CARRYOVER_HMAC_KEY, at least 32 bytes)",
            status_code=503,
        )
    return key_bytes


def _compute_carryover_hmac(
    *,
    call_id: str,
    conversation_id: str,
    owner_user_id: str,
    active_goal_id: str,
    resume_step_index: int,
    pending_action: str,
    local_models_only: bool,
    issued_at: int,
    signing_salt: str | None = None,
) -> str:
    """Compute an HMAC-SHA256 signature binding all CallToWebCarryover fields and issue time to the owner."""
    msg = json.dumps(
        [
            call_id,
            conversation_id,
            owner_user_id,
            active_goal_id,
            resume_step_index,
            pending_action,
            local_models_only,
            issued_at,
        ],
        separators=(",", ":"),
    )
    return hmac.new(
        _carryover_signing_key(signing_salt), msg.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def build_call_to_web_carryover(
    *,
    call_id: str,
    conversation_id: str,
    owner_user_id: str,
    caller_user_id: str,
    active_goal_id: str = "goal_guided_tcc",
    resume_step_index: int = 2,
    pending_action: str = "upload_supporting_receipt",
    signing_salt: str | None = None,
    now: float | None = None,
) -> CallToWebCarryover | None:
    """Build a session-bound, HMAC-signed Voice-to-Web carryover token when caller and owner identities match."""
    is_valid = (
        bool(_SAFE_ID_RE.match(call_id))
        and bool(_SAFE_ID_RE.match(conversation_id))
        and bool(_SAFE_ID_RE.match(owner_user_id))
        and bool(_SAFE_ID_RE.match(active_goal_id))
        and owner_user_id == caller_user_id
    )
    if not is_valid:
        return None
    step_idx = max(1, resume_step_index)
    bounded_action = pending_action[:120]
    issued_at = int(time.time() if now is None else now)
    sig = _compute_carryover_hmac(
        call_id=call_id,
        conversation_id=conversation_id,
        owner_user_id=owner_user_id,
        active_goal_id=active_goal_id,
        resume_step_index=step_idx,
        pending_action=bounded_action,
        local_models_only=True,
        issued_at=issued_at,
        signing_salt=signing_salt,
    )
    return CallToWebCarryover(
        call_id=call_id,
        conversation_id=conversation_id,
        active_goal_id=active_goal_id,
        resume_step_index=step_idx,
        pending_action=bounded_action,
        local_models_only=True,
        issued_at=issued_at,
        carryover_hmac=sig,
    )


def verify_call_to_web_carryover(
    carryover: CallToWebCarryover,
    *,
    caller_user_id: str,
    signing_salt: str | None = None,
    now: float | None = None,
) -> bool:
    """Verify the HMAC signature (`hmac.compare_digest`), caller ownership, and freshness of a carryover token (`SEC-G5`)."""
    current = time.time() if now is None else now
    age = current - carryover.issued_at
    if age > CARRYOVER_TTL_SECONDS or age < -CARRYOVER_CLOCK_SKEW_SECONDS:
        return False
    expected = _compute_carryover_hmac(
        call_id=carryover.call_id,
        conversation_id=carryover.conversation_id,
        owner_user_id=caller_user_id,
        active_goal_id=carryover.active_goal_id,
        resume_step_index=carryover.resume_step_index,
        pending_action=carryover.pending_action[:120],
        local_models_only=carryover.local_models_only,
        issued_at=carryover.issued_at,
        signing_salt=signing_salt,
    )
    return hmac.compare_digest(carryover.carryover_hmac, expected)


REPLY_FRAME_KINDS: frozenset[str] = frozenset(
    {
        "output_audio",
        "tts_text",
        "llm_response_start",
        "llm_response_end",
        "tts_started",
        "tts_stopped",
    }
)


def should_drop_ai_frame_when_bridged(
    *,
    call_mode: str,
    frame_kind: str,
    direction: str = "downstream",
) -> bool:
    """Keep the AI silent once an officer has bridged onto the call (`hold_gate.py` `OfficerOutputGate`)."""
    return direction == "downstream" and call_mode == "bridged" and frame_kind in REPLY_FRAME_KINDS


_PRIORITY_QUEUE_RANK: dict[str, int] = {"urgent": 0, "high": 1, "normal": 2}


def format_case_reference(ticket_id: str | None, *, fallback_call_id: str = "") -> str:
    """Format a caller/officer case reference (`transfer.py` `case_reference`)."""
    clean_ticket = str(ticket_id or "").strip()
    if clean_ticket:
        if clean_ticket.upper().startswith(("SSRA-", "CASE-", "CALL-")):
            return clean_ticket.upper()
        return f"SSRA-{clean_ticket[:8].upper()}"
    clean_call = str(fallback_call_id or "").strip()
    return f"CALL-{clean_call[:8].upper()}" if clean_call else "CALL-UNKNOWN"


def compute_transfer_queue_position(
    target_entry: LobbyCallEntry,
    all_entries: list[LobbyCallEntry] | tuple[LobbyCallEntry, ...],
) -> int:
    """Return 1-based queue position among unclaimed `transferring` calls (`transfer.py` `queue_position`)."""
    my_rank = (
        _PRIORITY_QUEUE_RANK.get(target_entry.priority, 2),
        target_entry.waiting_since if target_entry.waiting_since is not None else float("inf"),
        target_entry.call_id,
    )
    ahead = 0
    for other in all_entries:
        skip = (
            other.call_id == target_entry.call_id
            or other.status != "transferring"
            or bool(other.claimed_by)
        )
        if skip:
            continue
        other_rank = (
            _PRIORITY_QUEUE_RANK.get(other.priority, 2),
            other.waiting_since if other.waiting_since is not None else float("inf"),
            other.call_id,
        )
        if other_rank < my_rank:
            ahead += 1
    return ahead + 1


@dataclass(frozen=True)
class CallRiskEvaluation:
    """Live call risk evaluation (`risk.py` `evaluate_call_risk`)."""

    level: Literal["none", "watch", "at_risk"]
    signals: tuple[str, ...]
    should_offer_officer: bool


def _normalized_turn_similarity(a: str, b: str) -> float:
    norm_a = " ".join((a or "").lower().split())
    norm_b = " ".join((b or "").lower().split())
    if not norm_a or not norm_b:
        return 0.0
    return difflib.SequenceMatcher(None, norm_a, norm_b).ratio()


def evaluate_live_call_risk(
    *,
    turns: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    clarifications_asked: int = 0,
    abstentions_count: int = 0,
    duration_seconds: float = 0.0,
    caller_affect: str = "calm",
    risk_offer_already_made: bool = False,
) -> CallRiskEvaluation:
    """Evaluate a live call for the 6 `risk.py` queue risk signals (`none` | `watch` | `at_risk`)."""
    signals: list[str] = []
    if clarifications_asked >= 2:
        signals.append(f"clarifications:{clarifications_asked}")

    caller_utterances = [
        t
        for t in turns
        if t.get("speaker") == "caller"
        and t.get("kind", "utterance") != "review"
        and str(t.get("text", "")).strip()
    ]
    if len(caller_utterances) >= 2:
        latest_text = str(caller_utterances[-1].get("text", ""))
        repeated = any(
            _normalized_turn_similarity(latest_text, str(prev.get("text", ""))) >= 0.80
            for prev in caller_utterances[:-1]
        )
        if repeated:
            signals.append("repeated_question")

    distress_in_text = bool(
        caller_utterances
        and _DISTRESS_WORDS_RE.search(str(caller_utterances[-1].get("text", "")).lower())
    )
    if distress_in_text or caller_affect in ("distressed", "urgent_distress"):
        signals.append("distress")

    low_prob_turns = sum(
        1
        for t in caller_utterances
        if isinstance(t.get("mean_word_prob"), (int, float))
        and not isinstance(t.get("mean_word_prob"), bool)
        and float(t["mean_word_prob"]) < 0.50
    )
    if low_prob_turns >= 2:
        signals.append("low_word_confidence")

    if abstentions_count >= 1:
        signals.append("abstention")

    if duration_seconds > 360.0:
        signals.append("long_call")

    level: Literal["none", "watch", "at_risk"] = "none"
    if "distress" in signals or len(signals) >= 2:
        level = "at_risk"
    elif len(signals) == 1:
        level = "watch"

    should_offer = level == "at_risk" and not risk_offer_already_made
    return CallRiskEvaluation(
        level=level,
        signals=tuple(signals),
        should_offer_officer=should_offer,
    )


@dataclass(frozen=True)
class LowBandwidthVoiceProfile:
    """Negotiated transport adaptation for a constrained 2G/3G mobile voice connection (`low_bandwidth.py`)."""

    enabled: bool = False
    codec: Literal["pcm16_16k", "mulaw_8k", "opus_12k"] = "pcm16_16k"
    sample_rate: int = 16000
    caption_only: bool = False
    bitrate_kbps: int = 256


def negotiate_low_bandwidth_voice_profile(
    telemetry: Mapping[str, Any] | None = None,
) -> LowBandwidthVoiceProfile:
    """Negotiate low-bandwidth voice codec and caption-first degradation from client network telemetry (`low_bandwidth.py`)."""
    cfg = telemetry or {}
    eff_type = str(cfg.get("effective_type") or "").strip().lower()
    save_data = bool(cfg.get("save_data") or cfg.get("low_bandwidth"))
    raw_rtt = cfg.get("rtt_ms")
    rtt_candidate = (
        float(raw_rtt)
        if isinstance(raw_rtt, (int, float)) and not isinstance(raw_rtt, bool)
        else 0.0
    )
    rtt_ms = max(0.0, rtt_candidate) if math.isfinite(rtt_candidate) else 0.0

    is_constrained = save_data or eff_type in ("slow-2g", "2g", "3g") or rtt_ms >= 600.0
    if not is_constrained:
        return LowBandwidthVoiceProfile()

    caption_only = bool(cfg.get("caption_only")) or eff_type == "slow-2g" or rtt_ms > 1500.0
    preferred_raw = str(cfg.get("audio_codec") or "mulaw_8k").strip().lower()
    codec: Literal["mulaw_8k", "opus_12k"] = (
        "opus_12k" if preferred_raw == "opus_12k" else "mulaw_8k"
    )
    bitrate = 0 if caption_only else (12 if codec == "opus_12k" else 64)
    return LowBandwidthVoiceProfile(
        enabled=True,
        codec=codec,
        sample_rate=8000 if codec == "mulaw_8k" else 16000,
        caption_only=caption_only,
        bitrate_kbps=bitrate,
    )


_MULAW_MU: float = 255.0
_LOG1P_MU: float = math.log1p(_MULAW_MU)
_MULAW_DECODE_LUT: tuple[float, ...] = tuple(
    (
        (
            -1.0
            if ((b / _MULAW_MU) * 2.0 - 1.0) < 0.0
            else (1.0 if ((b / _MULAW_MU) * 2.0 - 1.0) > 0.0 else 0.0)
        )
        * (1.0 / _MULAW_MU)
        * (math.pow(1.0 + _MULAW_MU, abs((b / _MULAW_MU) * 2.0 - 1.0)) - 1.0)
    )
    for b in range(256)
)


def pcm16_16k_to_mulaw_8k(pcm16_bytes: bytes) -> bytes:
    """Downsample 16 kHz mono PCM16 to 8 kHz and encode as 8-bit ITU-T G.711 mu-law (`low_bandwidth.py`, 4x smaller)."""
    if len(pcm16_bytes) > MAX_DECODED_PCM_BYTES:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            f"PCM16 input ({len(pcm16_bytes)} bytes) exceeds MAX_DECODED_PCM_BYTES ({MAX_DECODED_PCM_BYTES})",
            status_code=413,
        )
    if len(pcm16_bytes) < 4:
        return b""
    usable = len(pcm16_bytes) - (len(pcm16_bytes) % 2)
    sample_count = usable // 2
    samples = struct.unpack(f"<{sample_count}h", pcm16_bytes[:usable])
    out = bytearray()
    for idx in range(0, sample_count, 2):
        norm = max(-1.0, min(1.0, samples[idx] / 32768.0))
        sign = -1.0 if norm < 0.0 else (1.0 if norm > 0.0 else 0.0)
        compressed = sign * math.log1p(_MULAW_MU * abs(norm)) / _LOG1P_MU
        quantized = int(min(255, max(0, (compressed + 1.0) * 0.5 * _MULAW_MU + 0.5)))
        out.append(quantized)
    return bytes(out)


def mulaw_8k_to_pcm16_16k(mulaw_bytes: bytes) -> bytes:
    """Decode 8-bit 8 kHz G.711 mu-law via 256-entry LUT and linearly upsample to 16 kHz mono PCM16 (`low_bandwidth.py`)."""
    if not mulaw_bytes:
        return b""
    validate_audio_pcm_expansion_budget(
        compressed_bytes=len(mulaw_bytes),
        duration_seconds=max(0.001, len(mulaw_bytes) / 8000.0),
    )
    decoded_8k = [_MULAW_DECODE_LUT[b] for b in mulaw_bytes]

    upsampled: list[int] = []
    n = len(decoded_8k)
    if n == 1:
        val = int(max(-32768, min(32767, round(decoded_8k[0] * 32767.0))))
        upsampled.extend((val, val))
    else:
        for i in range(n - 1):
            cur_s = decoded_8k[i]
            mid_s = 0.5 * (cur_s + decoded_8k[i + 1])
            upsampled.append(int(max(-32768, min(32767, round(cur_s * 32767.0)))))
            upsampled.append(int(max(-32768, min(32767, round(mid_s * 32767.0)))))
        last_val = int(max(-32768, min(32767, round(decoded_8k[-1] * 32767.0))))
        upsampled.extend((last_val, last_val))
    return struct.pack(f"<{len(upsampled)}h", *upsampled)


CALLER_RECONNECT_GRACE_SECONDS: int = 45
_CONSUMED_CALL_RESUME_NONCES: OrderedDict[str, float] = OrderedDict()
_MAX_CONSUMED_CALL_RESUME_NONCES: int = 2048


def mint_call_resume_ticket(
    call_id: str,
    conversation_id: str,
    *,
    user_id: str = "",
    ttl_seconds: int = CALLER_RECONNECT_GRACE_SECONDS,
    signing_salt: str | None = None,
    now: float | None = None,
) -> str:
    """Mint a fail-closed HMAC-SHA256 single-use caller resume ticket for dropped mobile voice sockets (`low_bandwidth.py`)."""
    ids_ok = (
        bool(_SAFE_ID_RE.match(call_id))
        and bool(_SAFE_ID_RE.match(conversation_id))
        and (not user_id or bool(_SAFE_ID_RE.match(user_id)))
    )
    if not ids_ok:
        raise ValueError("call_id, conversation_id, and user_id must match _SAFE_ID_RE")
    key = _carryover_signing_key(signing_salt)
    current = time.time() if now is None else now
    payload = {
        "cid": call_id,
        "conv": conversation_id,
        "uid": user_id,
        "nonce": uuid.uuid4().hex[:16],
        "exp": round(current + max(5, ttl_seconds), 2),
    }
    raw_body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    sig = hmac.new(key, raw_body.encode("ascii"), hashlib.sha256).hexdigest()[:32]
    return f"{raw_body}.{sig}"


def verify_call_resume_ticket(
    resume_ticket: str,
    *,
    expected_call_id: str = "",
    expected_conversation_id: str = "",
    expected_user_id: str = "",
    signing_salt: str | None = None,
    now: float | None = None,
) -> dict[str, Any] | None:
    """Verify and consume a single-use caller resume ticket in constant time; returns claims or None (`low_bandwidth.py`)."""
    if not resume_ticket or "." not in resume_ticket or not resume_ticket.isascii():
        return None
    key = _carryover_signing_key(signing_salt)
    raw_body, sig = resume_ticket.rsplit(".", 1)
    expected_sig = hmac.new(key, raw_body.encode("ascii"), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig.encode("ascii"), expected_sig.encode("ascii")):
        return None
    payload = json.loads(base64.urlsafe_b64decode(raw_body.encode("ascii")).decode("utf-8"))
    current = time.time() if now is None else now
    exp_ts = float(payload.get("exp") or 0.0)
    if not math.isfinite(exp_ts) or exp_ts <= current:
        return None
    if expected_call_id and payload.get("cid") != expected_call_id:
        return None
    if expected_conversation_id and payload.get("conv") != expected_conversation_id:
        return None
    if expected_user_id and payload.get("uid") != expected_user_id:
        return None
    nonce = str(payload.get("nonce") or "")
    for old_nonce, old_exp in list(_CONSUMED_CALL_RESUME_NONCES.items()):
        if old_exp <= current:
            _CONSUMED_CALL_RESUME_NONCES.pop(old_nonce, None)
    if len(nonce) < 8 or nonce in _CONSUMED_CALL_RESUME_NONCES:
        return None
    if len(_CONSUMED_CALL_RESUME_NONCES) >= _MAX_CONSUMED_CALL_RESUME_NONCES:
        _CONSUMED_CALL_RESUME_NONCES.popitem(last=False)
    _CONSUMED_CALL_RESUME_NONCES[nonce] = exp_ts
    return payload


_SPEECH_CITATION_BRACKET_RE = re.compile(r"\s*\[\d+(?:\s*[,;]\s*\d+)*\](?!\()")
_SPEECH_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^\)]+\)")
_SPEECH_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_SPEECH_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_SPEECH_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*|__([^_]+)__")
_SPEECH_HEADER_BULLET_RE = re.compile(r"^\s*(?:#{1,6}|[-*+])\s+", re.MULTILINE)
_SPEECH_NUMBERED_LINE_RE = re.compile(r"^[ \t]*(\d{1,2})[.)][ \t]+", re.MULTILINE)
_SPEECH_NUMBERED_INLINE_RE = re.compile(
    r"(?<=[:.!?؟])[ \t]+(\d{1,2})\.[ \t]+(?=[A-Z\u0600-\u06FF])"
)
_SPEECH_VISUAL_FOOTER_RE = re.compile(
    r"(?:^|\n)[ \t]*(?:\*\*)?(?:You might also want to know|Related questions)\b.*",
    flags=re.IGNORECASE | re.DOTALL,
)
_STEP_WORD_BY_LOCALE: dict[LocaleCode, str] = {
    LocaleCode.EN: "Step",
    LocaleCode.AR: "الخطوة",
    LocaleCode.PGA: "Khatwa",
    LocaleCode.DIN: "Dhöl",
    LocaleCode.NUS: "Dia",
    LocaleCode.BFA: "Daket",
    LocaleCode.ZNE: "Di",
    LocaleCode.SHK: "Yoo",
}
_RECEPTIONIST_MORE_OFFER_BY_LOCALE: dict[LocaleCode, str] = {
    LocaleCode.EN: "Would you like me to read the remaining details?",
    LocaleCode.AR: "هل ترغب في سماع باقي التفاصيل؟",
    LocaleCode.PGA: "Inta aayiz tasma baagi al-tafasil?",
    LocaleCode.DIN: "Yïn nhiar ba käk döŋ kueen?",
    LocaleCode.NUS: "I nhök ba käk döŋ kueen?",
    LocaleCode.BFA: "Do nyar kulya naaran?",
    LocaleCode.ZNE: "Mo kpinyemu mi geda yangaapai?",
    LocaleCode.SHK: "Yi dwata akwena gin odong?",
}
_RECEPTIONIST_OFFICER_OFFER_BY_LOCALE: dict[LocaleCode, str] = {
    LocaleCode.EN: "Would you like me to connect you with an SSRA officer?",
    LocaleCode.AR: "هل ترغب في التحدث إلى موظف هيئة الإيرادات؟",
    LocaleCode.PGA: "Inta aayiz tatkalam ma'a muwazzaf SSRA?",
    LocaleCode.DIN: "Yïn nhiar ba yïn mat kekë raan luɔi de SSRA?",
    LocaleCode.NUS: "I nhök ba ji mat kɛ raan luɔi SSRA?",
    LocaleCode.BFA: "Do nyar kulya ko ngutu lo SSRA?",
    LocaleCode.ZNE: "Mo kpinyemu mi banda ro ku boro SSRA?",
    LocaleCode.SHK: "Yi dwata aribi yi ki جال SSRA?",
}
_SPEECH_SEC_SHORTHAND_RE = re.compile(r"\bSec\.\s*(\d+[A-Za-z]?)\b")
_SPEECH_ART_SHORTHAND_RE = re.compile(r"\bArt\.\s*(\d+[A-Za-z]?)\b")
_REDACTED_SPEECH_MAP: tuple[tuple[str, str], ...] = (
    ("<TIN_REDACTED>", "redacted T I N"),
    ("[REDACTED_TIN]", "redacted T I N"),
    ("<PHONE_REDACTED>", "redacted phone number"),
    ("[REDACTED_PHONE]", "redacted phone number"),
    ("<EMAIL_REDACTED>", "redacted email address"),
    ("[REDACTED_EMAIL]", "redacted email address"),
)


def clean_text_for_speech(text: str, locale: LocaleCode = LocaleCode.EN) -> str:
    """Prepare markdown and statutory reply text for natural TTS synthesis (`speech_normalization.py` parity)."""
    web_link_word = "رابط إلكتروني" if locale == LocaleCode.AR else "web link"
    step_word = _STEP_WORD_BY_LOCALE.get(locale, "Step")
    out = _SPEECH_VISUAL_FOOTER_RE.sub("", text or "")
    out = _SPEECH_CODE_BLOCK_RE.sub(" ", out)
    out = _USSD_CODE_SPEECH_RE.sub(
        lambda m: _format_ussd_for_speech(m.group(1), locale),
        out,
    )
    out = _SPEECH_CITATION_BRACKET_RE.sub("", out)
    out = _SPEECH_MD_LINK_RE.sub(r"\1", out)
    out = _SPEECH_INLINE_CODE_RE.sub(r"\1", out)
    out = _SPEECH_BOLD_RE.sub(lambda m: m.group(1) or m.group(2) or "", out)
    out = _SPEECH_HEADER_BULLET_RE.sub("", out)
    out = _SPEECH_NUMBERED_LINE_RE.sub(rf"{step_word} \1: ", out)
    out = _SPEECH_NUMBERED_INLINE_RE.sub(rf" {step_word} \1: ", out)
    for marker, spoken_label in _REDACTED_SPEECH_MAP:
        out = out.replace(marker, spoken_label)
    out = _SPEECH_SEC_SHORTHAND_RE.sub(r"Section \1", out)
    out = _SPEECH_ART_SHORTHAND_RE.sub(r"Article \1", out)
    out = normalize_statutory_text_for_speech(out, locale=locale)
    out = re.sub(r"\bhttps?://\S+", web_link_word, out, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", out).strip()


_SSRA_ASR_SURE_MISHEARS: dict[str, str] = {
    "ttiimu": "TIN",
    "tiimu": "TIN",
    "ttimu": "TIN",
    "timu": "TIN",
    "ttini": "TIN",
    "tiisiisii": "TCC",
    "tisi": "TCC",
    "piieewai": "PAYE",
    "payi": "PAYE",
    "etaksi": "e-Tax",
    "itax": "e-Tax",
    "nira": "NRA",
    "inara": "NRA",
    "esara": "SSRA",
}
_SSRA_ASR_CONTEXT_MISHEARS: dict[tuple[str, str], str] = {
    ("from", "era"): "SSRA",
    ("with", "era"): "SSRA",
    ("at", "era"): "SSRA",
    ("from", "ora"): "SSRA",
}
_CLARIFY_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "do",
        "does",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "it",
        "me",
        "my",
        "of",
        "on",
        "or",
        "the",
        "to",
        "what",
        "when",
        "where",
        "who",
        "why",
        "with",
        "you",
        "your",
        "um",
        "uh",
        "okay",
        "ok",
        "please",
    }
)


def detect_ssra_entity_mishear(token: str, previous: str | None = None) -> str | None:
    """Return canonical SSRA tax acronym for a known Whisper/ASR phonetic mishear (`clarify.py` `entity_mishear`)."""
    tok = token.lower().strip(",.?!;:\"'()")
    prev = (previous or "").lower().strip(",.?!;:\"'()")
    ctx_hit = _SSRA_ASR_CONTEXT_MISHEARS.get((prev, tok))
    if ctx_hit is not None:
        return ctx_hit
    return _SSRA_ASR_SURE_MISHEARS.get(tok)


def repair_ssra_asr_entities(text: str) -> str:
    """Repair known phonetic mishears of SSRA tax entities in an ASR transcript (`clarify.py` `repair_asr_entities`)."""
    tokens = text.split()
    if not tokens:
        return ""
    repaired: list[str] = []
    for idx, tok in enumerate(tokens):
        prev = tokens[idx - 1] if idx > 0 else None
        canonical = detect_ssra_entity_mishear(tok, prev)
        if canonical is not None:
            stripped_right = tok.rstrip(",.?!;:\"'()")
            suffix = tok[len(stripped_right) :]
            repaired.append(f"{canonical}{suffix}")
        else:
            repaired.append(tok)
    return " ".join(repaired)


@dataclass(frozen=True)
class SpokenClarifyDecision:
    """Outcome of spoken `ClarifyGate` evaluation (`clarify.py` `ClarifyAction`)."""

    action: Literal["none", "ask_term", "ask_repeat"]
    candidate: str | None = None
    target_word: str | None = None
    prompt: str | None = None


def assess_spoken_clarification(
    text: str,
    *,
    words: list[dict[str, Any]] | None = None,
    threshold: float = 0.65,
    locale: LocaleCode = LocaleCode.EN,
) -> SpokenClarifyDecision:
    """Assess a caller utterance for misheard tax acronyms or low-confidence content words (`clarify.py`)."""
    _ = locale
    tokens = [w.strip(",.?!;:\"'()") for w in text.split() if w.strip(",.?!;:\"'()")]
    for idx, tok in enumerate(tokens):
        prev = tokens[idx - 1] if idx > 0 else None
        misheard = detect_ssra_entity_mishear(tok, prev)
        if misheard is not None:
            return SpokenClarifyDecision(
                action="ask_term",
                candidate=misheard,
                target_word=tok,
                prompt=f"Excuse me, did you mean {misheard}?",
            )

    if not words:
        return SpokenClarifyDecision(action="none")

    low_content: list[tuple[float, str]] = []
    probs_all: list[float] = []
    for item in words:
        w_str = str(item.get("word") or "").strip(",.?!;:\"'()")
        raw_prob = item.get("prob", 1.0)
        prob = (
            float(raw_prob)
            if isinstance(raw_prob, (int, float)) and not isinstance(raw_prob, bool)
            else 1.0
        )
        probs_all.append(prob)
        if not w_str or w_str.lower() in _CLARIFY_STOP_WORDS or not any(c.isalpha() for c in w_str):
            continue
        if prob < threshold:
            low_content.append((prob, w_str))

    if not low_content:
        return SpokenClarifyDecision(action="none")

    low_content.sort(key=lambda pair: pair[0])
    lowest_word = low_content[0][1]
    mean_prob = sum(probs_all) / len(probs_all)
    if mean_prob < threshold + 0.10:
        return SpokenClarifyDecision(
            action="ask_repeat",
            target_word=lowest_word,
            prompt="Pardon me, could you repeat that part clearly?",
        )
    return SpokenClarifyDecision(action="none")


@dataclass(frozen=True)
class LanguageVote:
    """Per-utterance acoustic + lexical language identification vote (`language.py`)."""

    probs: Mapping[str, float]
    top: str
    speech_s: float
    text: str = ""

    @property
    def confidence(self) -> float:
        return float(self.probs.get(self.top, 0.0))


@dataclass(frozen=True)
class LanguageSwitchDecision:
    """Decision from `CallLanguagePolicy.observe` (`language.py` `Decision`)."""

    action: Literal["none", "switch", "lock"]
    target: str
    reason: str
    confidence: float = 0.0
    source: Literal["auto", "explicit", "override"] = "auto"


_EXPLICIT_LANG_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "pga",
        re.compile(
            r"\b(?:(?:speak|talk)\s+(?:in\s+)?juba\s+arabic|switch\s+to\s+juba\s+arabic|عربي\s+جوبا)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "ar",
        re.compile(
            r"\b(?:(?:speak|talk)\s+(?:in\s+)?arabic|switch\s+to\s+arabic|تكلم\s+عربي|تحدث\s+بالعربية)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "en",
        re.compile(
            r"\b(?:(?:speak|talk)\s+(?:in\s+)?english|switch\s+to\s+english|تكلم\s+إنجليزي)\b",
            re.IGNORECASE,
        ),
    ),
)
_LANG_NEGATION_PREFIX_RE = re.compile(
    r"(?:\b(?:not|no|don'?t|do\s+not|never)|(?:لا|مش))[\s,;:—-]*$",
    re.IGNORECASE,
)


def detect_explicit_language_request(text: str) -> str | None:
    """Return the locale code explicitly requested in *text*, or None (`language.py` `detect_explicit_request`)."""
    clean = (text or "").strip()
    if not clean:
        return None
    best_end = -1
    best_lang: str | None = None
    for lang_code, pattern in _EXPLICIT_LANG_PATTERNS:
        for match in pattern.finditer(clean):
            prefix = clean[max(0, match.start() - 24) : match.start()]
            if _LANG_NEGATION_PREFIX_RE.search(prefix):
                continue
            if match.end() > best_end:
                best_end = match.end()
                best_lang = lang_code
    return best_lang


class CallLanguagePolicy:
    """Hysteresis state machine over a call's active language (`language.py` `LanguagePolicy`)."""

    def __init__(
        self,
        *,
        active: str = "en",
        supported_languages: tuple[str, ...] = ("en", "ar", "pga"),
        min_speech_s: float = 1.5,
        switch_confidence: float = 0.90,
        hysteresis_confidence: float = 0.70,
        support_confidence: float = 0.50,
        hysteresis_turns: int = 2,
        hysteresis_window: int = 3,
    ) -> None:
        self.active = active
        self.supported_languages = supported_languages
        self.min_speech_s = min_speech_s
        self.switch_confidence = switch_confidence
        self.hysteresis_confidence = hysteresis_confidence
        self.support_confidence = support_confidence
        self.hysteresis_turns = hysteresis_turns
        self.hysteresis_window = hysteresis_window
        self.locked: bool = False
        self.override: str | None = None
        self.pending: list[LanguageVote] = []
        self.switch_count: int = 0

    def _move(
        self,
        target: str,
        reason: str,
        confidence: float,
        source: Literal["auto", "explicit", "override"],
    ) -> LanguageSwitchDecision:
        changed = target != self.active
        self.active = target
        self.locked = True
        if changed:
            self.switch_count += 1
            return LanguageSwitchDecision("switch", target, reason, confidence, source)
        return LanguageSwitchDecision("lock", target, reason, confidence, source)

    def set_override(self, language: str) -> LanguageSwitchDecision:
        """Lock the caller's on-screen language choice (`language.py` `set_override`)."""
        if language not in self.supported_languages:
            return LanguageSwitchDecision(
                "none", self.active, "unsupported_language", source="override"
            )
        self.override = language
        self.pending.clear()
        return self._move(language, "ui_override", 1.0, "override")

    def observe(self, vote: LanguageVote) -> LanguageSwitchDecision:
        """Observe one utterance vote and return a hysteresis-governed language decision (`language.py`)."""
        requested = detect_explicit_language_request(vote.text)
        if requested is not None and requested in self.supported_languages:
            if self.override is not None:
                self.override = requested
            self.pending.clear()
            return self._move(requested, "explicit_request", 1.0, "explicit")
        if self.override is not None:
            return LanguageSwitchDecision("none", self.active, "override_locked", source="override")
        if vote.speech_s < self.min_speech_s or not vote.top:
            return LanguageSwitchDecision("none", self.active, "too_short")
        if vote.top not in self.supported_languages:
            return LanguageSwitchDecision("none", self.active, "unsupported_language")

        conf = vote.confidence
        # Code-switched tax loanword guard (EACL 2026 & language.py lines 314-337):
        # When locked in Arabic ('ar' or 'pga'), an English acoustic vote caused by tax loanwords
        # ("TIN", "PAYE", "TCC") while the transcript still contains Arabic script stays in the active locale.
        has_arabic_script = bool(re.search(r"[\u0600-\u06FF]", vote.text))
        is_code_switched_loanword = (
            self.locked and self.active in ("ar", "pga") and vote.top == "en" and has_arabic_script
        )
        if is_code_switched_loanword:
            self.pending.clear()
            return LanguageSwitchDecision("none", self.active, "code_switched_loanword_guard", conf)

        if not self.locked:
            if conf >= self.hysteresis_confidence:
                return self._move(vote.top, "first_content", conf, "auto")
            return LanguageSwitchDecision("none", self.active, "weak_first_vote", conf)

        if vote.top == self.active:
            self.pending.clear()
            return LanguageSwitchDecision("none", self.active, "same_language", conf)

        if conf >= self.switch_confidence:
            self.pending.clear()
            return self._move(vote.top, "high_confidence", conf, "auto")

        self.pending.append(vote)
        if len(self.pending) > self.hysteresis_window:
            self.pending.pop(0)
        supporting = [
            v for v in self.pending if v.top == vote.top and v.confidence >= self.support_confidence
        ]
        if len(supporting) >= self.hysteresis_turns:
            avg_conf = round(sum(v.confidence for v in supporting) / len(supporting), 3)
            self.pending.clear()
            return self._move(vote.top, "hysteresis", avg_conf, "auto")
        return LanguageSwitchDecision("none", self.active, "accumulating_hysteresis", conf)


__all__ = [
    "APPROVED_VOICE_WER_EVIDENCE",
    "ASR_MODEL_BY_LOCALE",
    "CALLER_RECONNECT_GRACE_SECONDS",
    "CARRYOVER_TTL_SECONDS",
    "LOBBY_EVENT_TYPES",
    "MAX_CARRYOVER_CONTEXT_CHARS",
    "MAX_COMPRESSED_AUDIO_BYTES",
    "MAX_DECODED_PCM_BYTES",
    "MAX_DTMF_STEP_UP_ATTEMPTS",
    "MAX_SMS_CONTINUATION_CHARS",
    "MAX_VOICE_WER_GATE",
    "POST_TTS_ECHO_COOLDOWN_MS",
    "REPLY_FRAME_KINDS",
    "TTS_DEFAULT_VOICE",
    "TTS_MODEL_BY_LOCALE",
    "TTS_VOICE_CATALOG",
    "VOICE_EVENT_TYPES",
    "WHISPER_COMPRESSION_RATIO_THRESHOLD",
    "WHISPER_LOGPROB_THRESHOLD",
    "WHISPER_NO_SPEECH_THRESHOLD",
    "BargeInDirective",
    "BriefClaim",
    "CallLanguagePolicy",
    "CallLobbyManager",
    "CallRiskEvaluation",
    "CallToWebCarryover",
    "ChatToCallCarryover",
    "EdgeFieldApplianceProfile",
    "HfVoiceModelDescriptor",
    "HybridVoiceRouteDecision",
    "LanguageSwitchDecision",
    "LanguageVote",
    "LobbyCallEntry",
    "LowBandwidthVoiceProfile",
    "OfficerCallBrief",
    "OtpVerifier",
    "SpokenClarifyDecision",
    "SpokenNumberVerbalization",
    "StepUpAttemptStore",
    "TtsCachedAudio",
    "TtsPhraseCache",
    "TtsSynthesizer",
    "VADConfig",
    "VoiceCallSession",
    "VoicePrompt",
    "VoiceRetentionPolicy",
    "VoiceSessionDecision",
    "VoiceStreamSession",
    "VoiceTurnOutcome",
    "VoiceWebSocketConcurrencyGuard",
    "VoiceWerEvidence",
    "WhisperSegmentSignals",
    "assess_spoken_clarification",
    "assess_whisper_segment",
    "build_call_opening_prompts",
    "build_call_to_web_carryover",
    "build_chat_to_call_carryover",
    "build_voice_consent_audit_entry",
    "build_voice_prosody_eq_metadata",
    "build_voice_spoken_turn_and_sms_followup",
    "classify_pending_offer_reply",
    "classify_spoken_call_review",
    "clean_text_for_speech",
    "compute_transfer_queue_position",
    "detect_explicit_language_request",
    "detect_ssra_entity_mishear",
    "evaluate_live_call_risk",
    "fixed_voice_prompts",
    "format_case_reference",
    "generate_officer_call_brief",
    "get_localized_tool_wait_filler",
    "is_backchannel_utterance",
    "is_callback_request",
    "is_goodbye_request",
    "is_likely_tts_echo",
    "is_normal_pace_request",
    "is_repeat_request",
    "is_slower_pace_request",
    "is_spoken_officer_request",
    "is_tax_dispute",
    "is_voice_language_approved",
    "is_ws_origin_allowed",
    "looks_like_valid_audio_bytes",
    "mint_call_resume_ticket",
    "mulaw_8k_to_pcm16_16k",
    "negotiate_low_bandwidth_voice_profile",
    "normalize_statutory_text_for_speech",
    "pcm16_16k_to_mulaw_8k",
    "repair_ssra_asr_entities",
    "resolve_edge_appliance_profile",
    "resolve_hf_voice_model_cache",
    "resolve_mt_and_tts_turn_plan",
    "resolve_recording_consent",
    "resolve_tts_voice",
    "route_voice_turn",
    "select_hybrid_voice_execution_mode",
    "should_drop_ai_frame_when_bridged",
    "split_receptionist_spoken_sentences",
    "split_tts_sentences",
    "sync_affective_state_to_call_lobby",
    "synthesize_tts_speech_envelope",
    "validate_audio_pcm_expansion_budget",
    "validate_call_wrap_up",
    "verbalize_statutory_figures_for_tts",
    "verify_call_resume_ticket",
    "verify_call_to_web_carryover",
    "verify_spoken_figure_fidelity",
    "verify_voice_dtmf_step_up",
]
