"""Application layer for consent & per-subject preference deletion bounded context (Section 6.5)."""

from __future__ import annotations

from ssra_core import utc_now

from ssra_api.consent.domain import ConsentRecord, SubjectPreferenceEntity
from ssra_api.outbox import get_outbox_store

_pref_store: dict[str, SubjectPreferenceEntity] = {}


def record_consent_use_case(
    *, subject_ref: str, channel: str, purpose: str, revoked: bool = False
) -> ConsentRecord:
    now = utc_now()
    rec = ConsentRecord(
        subject_ref=subject_ref,
        channel=channel,
        purpose=purpose,
        granted_at=now,
        revoked_at=now if revoked else None,
    )
    get_outbox_store().stage_domain_event(
        context_name="consent",
        event_type="ssra.consent.revoked.v1" if revoked else "ssra.consent.granted.v1",
        subject=subject_ref,
        data={"channel": channel, "purpose": purpose, "revoked": revoked},
    )
    return rec


def upsert_subject_preferences_use_case(
    *,
    subject_ref: str,
    preferred_locale: str,
    preferred_channel: str,
    low_data_mode: bool = False,
    voice_first_a11y: bool = False,
) -> SubjectPreferenceEntity:
    entity = SubjectPreferenceEntity(
        subject_ref=subject_ref,
        preferred_locale=preferred_locale,
        preferred_channel=preferred_channel,
        low_data_mode=low_data_mode,
        voice_first_a11y=voice_first_a11y,
        updated_at=utc_now(),
    )
    _pref_store[subject_ref] = entity
    return entity


def delete_subject_preferences_use_case(subject_ref: str) -> bool:
    return _pref_store.pop(subject_ref, None) is not None
