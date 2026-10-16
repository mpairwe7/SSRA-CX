"""API router for consent & long-term preferences (with per-subject deletion — Section 6.5)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from ssra_api.consent.application import (
    delete_subject_preferences_use_case,
    record_consent_use_case,
    upsert_subject_preferences_use_case,
)

router = APIRouter(prefix="/v1/consent", tags=["consent"])


class UpdateConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_ref: str
    channel: str
    purpose: str
    revoked: bool = False


class ConsentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_ref: str
    channel: str
    purpose: str
    active: bool


class UpsertPreferencesRequest(BaseModel):
    """Strictly typed preferences only — no free-text financial facts permitted (Section 6.5)."""

    model_config = ConfigDict(extra="forbid")

    preferred_locale: Literal["en", "pga", "ar", "din", "nus", "bfa", "zne", "shk"] = "en"
    preferred_channel: Literal["web", "whatsapp", "sms", "ussd", "voice"] = "web"
    low_data_mode: bool = False
    voice_first_a11y: bool = False


class PreferencesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_ref: str
    preferred_locale: str
    preferred_channel: str
    low_data_mode: bool
    voice_first_a11y: bool


class DeletePreferencesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_ref: str
    deleted: bool


@router.post("", response_model=ConsentResponse)
async def update_consent(body: UpdateConsentRequest) -> ConsentResponse:
    rec = record_consent_use_case(
        subject_ref=body.subject_ref,
        channel=body.channel,
        purpose=body.purpose,
        revoked=body.revoked,
    )
    return ConsentResponse(
        subject_ref=rec.subject_ref,
        channel=rec.channel,
        purpose=rec.purpose,
        active=rec.revoked_at is None,
    )


@router.put("/preferences/{subject_ref}", response_model=PreferencesResponse)
async def upsert_preferences(
    subject_ref: str, body: UpsertPreferencesRequest
) -> PreferencesResponse:
    pref = upsert_subject_preferences_use_case(
        subject_ref=subject_ref,
        preferred_locale=body.preferred_locale,
        preferred_channel=body.preferred_channel,
        low_data_mode=body.low_data_mode,
        voice_first_a11y=body.voice_first_a11y,
    )
    return PreferencesResponse(
        subject_ref=pref.subject_ref,
        preferred_locale=pref.preferred_locale,
        preferred_channel=pref.preferred_channel,
        low_data_mode=pref.low_data_mode,
        voice_first_a11y=pref.voice_first_a11y,
    )


@router.delete("/preferences/{subject_ref}", response_model=DeletePreferencesResponse)
async def delete_preferences(subject_ref: str) -> DeletePreferencesResponse:
    deleted = delete_subject_preferences_use_case(subject_ref)
    return DeletePreferencesResponse(subject_ref=subject_ref, deleted=deleted)
