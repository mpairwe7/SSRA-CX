"""4-Tier Cognitive Memory & Consented Preferences Store (Section 6.5 & October 2026 Agentic CX).

Implements the Consent-Gated 4-Tier Cognitive Architecture:
- Tier 1 (Working Memory): Active turn state, English-Router envelope, and `workflow_stack` in checkpointer.
- Tier 2 (Episodic Memory): Cross-session, cross-channel interaction summaries (`EpisodicMemoryRecord`, 90-day TTL).
- Tier 3 (Semantic & Preference Memory): Typed `ConsentedUserPreferences` (`extra="forbid"`, enum/boolean fields only).
- Tier 4 (Procedural / Long-Horizon Goal Memory): Multi-session goal state (`ActiveGoalRecord`, 14-day TTL) for
  cross-channel resumption and Temporal post-interaction continuation.

Non-Negotiable Invariants:
1. NEVER stores raw financial figures, tax balances, or unredacted PII in long-term memory (`strip_financial_figures_for_memory`).
2. Episodic (Tier 2) and Procedural (Tier 4) persistence require explicit `memory_continuity_opt_in=True` consent.
3. Supports immediate single-call Right-to-Erasure across all tiers (`delete_subject_preferences` & `delete_all_subject_memory`).
"""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from datetime import datetime, timedelta
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field
from ssra_core import ChannelName, IntentName, LocaleCode, new_id, utc_now
from ssra_security import redact_pii

QDRANT_EPISODIC_COLLECTION: str = "ssra_episodic_memory_v1"


def deterministic_16d_vector(text: str) -> list[float]:
    """Compute a normalized deterministic 16-dimensional embedding vector from redacted text."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    raw = [((digest[i] / 127.5) - 1.0) for i in range(16)]
    norm = sum(v * v for v in raw) ** 0.5 or 1.0
    return [round(v / norm, 6) for v in raw]


_CURRENCY_OR_LONG_DIGIT_RE = re.compile(
    r"(?:(?:SSP|USD)\s*)?[\d\u0660-\u0669\u06F0-\u06F9]+(?:[.,][\d\u0660-\u0669\u06F0-\u06F9]+)*(?:\s*(?:SSP|USD|%))?",
    flags=re.IGNORECASE,
)
_MEMORY_DELIMITER_SCRUB_RE = re.compile(
    r"<\|[^|>]*\|>|<\s*/?\s*untrusted_[^>]*>",
    flags=re.IGNORECASE,
)

MAX_EPISODES_PER_SUBJECT: int = 20
MAX_TRACKED_SUBJECTS: int = 4096
EPISODIC_TTL_DAYS: int = 90
PROCEDURAL_GOAL_TTL_DAYS: int = 14


def strip_financial_figures_for_memory(text: str) -> str:
    """Scrub PII, special tokens/delimiters (`ASI06`), and all ASCII/Arabic-Indic currency figures so balances never enter memory."""
    redacted = redact_pii(text).redacted_text
    delimit_scrubbed = _MEMORY_DELIMITER_SCRUB_RE.sub("[REDACTED_DELIMITER]", redacted)
    return _CURRENCY_OR_LONG_DIGIT_RE.sub("[REDACTED_FIGURE]", delimit_scrubbed).strip()


class ConsentedUserPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_ref: str
    preferred_locale: LocaleCode = LocaleCode.EN
    preferred_channel: ChannelName = ChannelName.WEB
    low_data_mode: bool = False
    high_contrast_a11y: bool = False
    voice_first_a11y: bool = False
    updated_at: datetime


class EpisodicMemoryRecord(BaseModel):
    """Tier 2 Episodic Memory: Redacted, figure-free summary of a past interaction episode."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    episode_id: str
    subject_ref: str
    channel: ChannelName
    locale: LocaleCode
    intent: IntentName
    outcome_status: Literal["RESOLVED", "PENDING_ASYNC", "ESCALATED"]
    redacted_summary: str = Field(max_length=280)
    unresolved_blocker_code: str | None = None
    created_at: datetime
    expires_at: datetime


class ActiveGoalRecord(BaseModel):
    """Tier 4 Procedural / Long-Horizon Goal Memory: Durable multi-session workflow checkpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    goal_id: str
    subject_ref: str
    goal_type: IntentName
    current_step_index: int = Field(ge=1, default=1)
    total_steps: int = Field(ge=1, default=2)
    completed_steps: list[str] = Field(default_factory=list)
    pending_dependency: (
        Literal[
            "ETAX_TCC_APPROVAL",
            "CUSTOMS_ASSESSMENT",
            "DOCUMENT_HUMAN_REVIEW",
            "OFFICER_CALLBACK_READY",
        ]
        | None
    ) = None
    resume_channel: ChannelName = ChannelName.WEB
    status: Literal["IN_PROGRESS", "WAITING_ASYNC", "COMPLETED", "CANCELLED"] = "IN_PROGRESS"
    updated_at: datetime
    expires_at: datetime


class HydratedCognitiveContext(BaseModel):
    """Hydrated 4-Tier memory snapshot injected at Stage 4 (`understand_node`)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_ref: str
    memory_continuity_consented: bool
    preferences: ConsentedUserPreferences | None = None
    recent_episodes: list[EpisodicMemoryRecord] = Field(default_factory=list)
    active_goals: list[ActiveGoalRecord] = Field(default_factory=list)


class SubjectPreferenceMemoryStore:
    """Typed long-term preference store (Tier 3) + 4-Tier Cognitive Memory Manager with Right-to-Erasure."""

    def __init__(self) -> None:
        """Initialize the in-memory 4-tier cognitive memory and preference store."""
        self._prefs: dict[str, ConsentedUserPreferences] = {}
        self._continuity_consent: dict[str, bool] = {}
        self._episodes: dict[str, list[EpisodicMemoryRecord]] = {}
        self._goals: dict[str, dict[str, ActiveGoalRecord]] = {}
        self._qdrant_collection_ready: bool = False

    def _qdrant_base_url(self) -> str:
        """Return the configured Qdrant HTTP URL or empty string if in-memory only."""
        return os.environ.get("SSRA_QDRANT_URL", "").strip().rstrip("/")

    def _ensure_qdrant_collection(self, base_url: str) -> bool:
        """Ensure the `ssra_episodic_memory_v1` collection exists in Qdrant."""
        if self._qdrant_collection_ready:
            return True
        try:
            r = httpx.get(f"{base_url}/collections/{QDRANT_EPISODIC_COLLECTION}", timeout=3.0)
            if r.status_code != 200:
                r = httpx.put(
                    f"{base_url}/collections/{QDRANT_EPISODIC_COLLECTION}",
                    json={"vectors": {"size": 16, "distance": "Cosine"}},
                    timeout=3.0,
                )
            self._qdrant_collection_ready = r.status_code in (200, 201)
            return self._qdrant_collection_ready
        except httpx.HTTPError:
            return False

    def _sync_episode_to_qdrant(self, rec: EpisodicMemoryRecord) -> None:
        """Upsert a PII-redacted and figure-stripped episodic memory point into Qdrant if configured."""
        base_url = self._qdrant_base_url()
        if not base_url or not self._ensure_qdrant_collection(base_url):
            return
        point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, rec.episode_id))
        try:
            httpx.put(
                f"{base_url}/collections/{QDRANT_EPISODIC_COLLECTION}/points?wait=true",
                json={
                    "points": [
                        {
                            "id": point_uuid,
                            "vector": deterministic_16d_vector(rec.redacted_summary),
                            "payload": {
                                "episode_id": rec.episode_id,
                                "subject_ref": rec.subject_ref,
                                "intent": rec.intent.value,
                                "outcome_status": rec.outcome_status,
                                "redacted_summary": rec.redacted_summary,
                                "locale": rec.locale.value,
                                "channel": rec.channel.value,
                                "expires_at": rec.expires_at.isoformat(),
                            },
                        }
                    ]
                },
                timeout=3.0,
            )
        except httpx.HTTPError:
            return

    def _delete_episodes_from_qdrant(self, episode_ids: list[str]) -> None:
        """Delete trimmed or expired episodic point UUIDs from Qdrant when configured."""
        base_url = self._qdrant_base_url()
        if not episode_ids or not base_url or not self._ensure_qdrant_collection(base_url):
            return
        point_uuids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, eid)) for eid in episode_ids]
        try:
            httpx.post(
                f"{base_url}/collections/{QDRANT_EPISODIC_COLLECTION}/points/delete?wait=true",
                json={"points": point_uuids},
                timeout=3.0,
            )
        except httpx.HTTPError:
            return

    def _delete_subject_from_qdrant(self, subject_ref: str) -> bool:
        """Delete all Qdrant episodic points belonging to `subject_ref` for Right-to-Erasure."""
        base_url = self._qdrant_base_url()
        if not base_url:
            return True
        if not self._ensure_qdrant_collection(base_url):
            return False
        try:
            r = httpx.post(
                f"{base_url}/collections/{QDRANT_EPISODIC_COLLECTION}/points/delete?wait=true",
                json={
                    "filter": {
                        "must": [
                            {"key": "subject_ref", "match": {"value": subject_ref}},
                        ]
                    }
                },
                timeout=3.0,
            )
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def qdrant_episodic_points_count(
        self,
        subject_ref: str | None = None,
        *,
        force_probe: bool = False,
    ) -> int | None:
        """Return the number of episodic memory points stored in Qdrant, or `None` if Qdrant is unreachable."""
        base_url = self._qdrant_base_url()
        if not base_url:
            return 0
        if force_probe:
            self._qdrant_collection_ready = False
        if not self._ensure_qdrant_collection(base_url):
            return None
        body: dict[str, object] = {"exact": True}
        if subject_ref is not None:
            body["filter"] = {
                "must": [{"key": "subject_ref", "match": {"value": subject_ref}}],
            }
        try:
            r = httpx.post(
                f"{base_url}/collections/{QDRANT_EPISODIC_COLLECTION}/points/count",
                json=body,
                timeout=3.0,
            )
            return int(r.json().get("result", {}).get("count", 0)) if r.status_code == 200 else None
        except (httpx.HTTPError, ValueError, TypeError):
            return None

    def upsert_preferences(
        self,
        *,
        subject_ref: str,
        preferred_locale: LocaleCode = LocaleCode.EN,
        preferred_channel: ChannelName = ChannelName.WEB,
        low_data_mode: bool = False,
        high_contrast_a11y: bool = False,
        voice_first_a11y: bool = False,
    ) -> ConsentedUserPreferences:
        """Upsert typed Tier 3 accessibility and channel preferences for `subject_ref`."""
        pref = ConsentedUserPreferences(
            subject_ref=subject_ref,
            preferred_locale=preferred_locale,
            preferred_channel=preferred_channel,
            low_data_mode=low_data_mode,
            high_contrast_a11y=high_contrast_a11y,
            voice_first_a11y=voice_first_a11y,
            updated_at=utc_now(),
        )
        self._prefs[subject_ref] = pref
        return pref

    def get_preferences(self, subject_ref: str) -> ConsentedUserPreferences | None:
        """Retrieve stored Tier 3 preferences for `subject_ref`, or `None` if absent."""
        return self._prefs.get(subject_ref)

    def set_memory_continuity_consent(self, subject_ref: str, *, consented: bool) -> None:
        """Enable or revoke consent for Tier 2 (Episodic) and Tier 4 (Procedural Goal) continuity."""
        self._continuity_consent[subject_ref] = bool(consented)
        if not consented:
            self._episodes.pop(subject_ref, None)
            self._goals.pop(subject_ref, None)
            self._delete_subject_from_qdrant(subject_ref)

    def has_memory_continuity_consent(self, subject_ref: str) -> bool:
        """Return True if `subject_ref` has active opt-in consent for Tier 2/4 memory continuity."""
        return self._continuity_consent.get(subject_ref, False)

    def record_episode(
        self,
        *,
        subject_ref: str,
        channel: ChannelName,
        locale: LocaleCode,
        intent: IntentName,
        outcome_status: Literal["RESOLVED", "PENDING_ASYNC", "ESCALATED"],
        raw_summary: str,
        unresolved_blocker_code: str | None = None,
    ) -> EpisodicMemoryRecord | None:
        """Record a PII-redacted and figure-stripped Tier 2 episode if consent is granted."""
        if not self.has_memory_continuity_consent(subject_ref):
            return None
        now = utc_now()
        safe_summary = strip_financial_figures_for_memory(raw_summary)[:280]
        rec = EpisodicMemoryRecord(
            episode_id=new_id("ep"),
            subject_ref=subject_ref,
            channel=channel,
            locale=locale,
            intent=intent,
            outcome_status=outcome_status,
            redacted_summary=safe_summary,
            unresolved_blocker_code=unresolved_blocker_code,
            created_at=now,
            expires_at=now + timedelta(days=EPISODIC_TTL_DAYS),
        )
        bucket = self._episodes.setdefault(subject_ref, [])
        bucket.append(rec)
        if len(bucket) > MAX_EPISODES_PER_SUBJECT:
            trimmed = [ep.episode_id for ep in bucket[:-MAX_EPISODES_PER_SUBJECT]]
            del bucket[:-MAX_EPISODES_PER_SUBJECT]
            self._delete_episodes_from_qdrant(trimmed)
        self._sync_episode_to_qdrant(rec)
        return rec

    def list_episodes(self, subject_ref: str) -> list[EpisodicMemoryRecord]:
        """List non-expired Tier 2 episodic records for `subject_ref`."""
        now = utc_now()
        items = self._episodes.get(subject_ref, [])
        expired = [ep.episode_id for ep in items if ep.expires_at <= now]
        if expired:
            self._delete_episodes_from_qdrant(expired)
        valid = [ep for ep in items if ep.expires_at > now]
        self._episodes[subject_ref] = valid
        return list(valid)

    def upsert_active_goal(
        self,
        *,
        subject_ref: str,
        goal_type: IntentName,
        current_step_index: int = 1,
        total_steps: int = 2,
        completed_steps: list[str] | None = None,
        pending_dependency: (
            Literal[
                "ETAX_TCC_APPROVAL",
                "CUSTOMS_ASSESSMENT",
                "DOCUMENT_HUMAN_REVIEW",
                "OFFICER_CALLBACK_READY",
            ]
            | None
        ) = None,
        resume_channel: ChannelName = ChannelName.WEB,
        status: Literal["IN_PROGRESS", "WAITING_ASYNC", "COMPLETED", "CANCELLED"] = "IN_PROGRESS",
        goal_id: str | None = None,
    ) -> ActiveGoalRecord | None:
        """Upsert a Tier 4 Procedural Goal record for cross-channel continuation if consented."""
        if not self.has_memory_continuity_consent(subject_ref):
            return None
        now = utc_now()
        gid = goal_id or f"goal_{goal_type.value}"
        rec = ActiveGoalRecord(
            goal_id=gid,
            subject_ref=subject_ref,
            goal_type=goal_type,
            current_step_index=max(1, current_step_index),
            total_steps=max(1, total_steps),
            completed_steps=list(completed_steps or []),
            pending_dependency=pending_dependency,
            resume_channel=resume_channel,
            status=status,
            updated_at=now,
            expires_at=now + timedelta(days=PROCEDURAL_GOAL_TTL_DAYS),
        )
        subj_goals = self._goals.setdefault(subject_ref, {})
        if status in ("COMPLETED", "CANCELLED"):
            subj_goals.pop(gid, None)
        else:
            subj_goals[gid] = rec
        return rec

    def list_active_goals(self, subject_ref: str) -> list[ActiveGoalRecord]:
        """List non-expired, in-progress or async-waiting Tier 4 goals for `subject_ref`."""
        now = utc_now()
        subj_goals = self._goals.get(subject_ref, {})
        valid = {
            gid: g
            for gid, g in subj_goals.items()
            if g.expires_at > now and g.status in ("IN_PROGRESS", "WAITING_ASYNC")
        }
        self._goals[subject_ref] = valid
        return list(valid.values())

    def hydrate_subject_context(self, subject_ref: str) -> HydratedCognitiveContext:
        """Hydrate Tiers 2, 3, and 4 for an authenticated `subject_ref`."""
        consented = self.has_memory_continuity_consent(subject_ref)
        return HydratedCognitiveContext(
            subject_ref=subject_ref,
            memory_continuity_consented=consented,
            preferences=self.get_preferences(subject_ref),
            recent_episodes=self.list_episodes(subject_ref) if consented else [],
            active_goals=self.list_active_goals(subject_ref) if consented else [],
        )

    def delete_subject_preferences(self, subject_ref: str) -> bool:
        """Per-subject deletion of all long-term preferences and cognitive memory tiers (Section 6.5)."""
        had_prefs = self._prefs.pop(subject_ref, None) is not None
        had_ep = self._episodes.pop(subject_ref, None) is not None
        had_goals = self._goals.pop(subject_ref, None) is not None
        self._continuity_consent.pop(subject_ref, None)
        qdrant_ok = self._delete_subject_from_qdrant(subject_ref)
        return (had_prefs or had_ep or had_goals or bool(self._qdrant_base_url())) and qdrant_ok
