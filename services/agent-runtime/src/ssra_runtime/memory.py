"""Long-Term Consented Preferences Memory Store (Section 6.5).

Invariants:
1. Stores ONLY consented preferences (`preferred_locale`, `preferred_channel`, `low_data_mode`, `high_contrast_a11y`, `voice_first_a11y`).
2. Strictly forbids free-text financial facts (`extra="forbid"`, enum/boolean fields only).
3. Supports immediate per-subject deletion (Right to Erasure / GDPR-grade & AU Malabo principles).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict
from ssra_core import ChannelName, LocaleCode, utc_now


class ConsentedUserPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_ref: str
    preferred_locale: LocaleCode = LocaleCode.EN
    preferred_channel: ChannelName = ChannelName.WEB
    low_data_mode: bool = False
    high_contrast_a11y: bool = False
    voice_first_a11y: bool = False
    updated_at: datetime


class SubjectPreferenceMemoryStore:
    """Typed long-term preference store with zero free-text fields and per-subject erasure."""

    def __init__(self) -> None:
        self._prefs: dict[str, ConsentedUserPreferences] = {}

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
        return self._prefs.get(subject_ref)

    def delete_subject_preferences(self, subject_ref: str) -> bool:
        """Per-subject deletion of all long-term preferences (Section 6.5)."""
        return self._prefs.pop(subject_ref, None) is not None
