"""Multilingual PII detection & masking for South Sudan TINs, +211 phones, Emails, Passports, and OTPs."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Translate Eastern Arabic (U+0660..U+0669) and Extended Arabic-Indic (U+06F0..U+06F9) digits to ASCII 0-9
_ARABIC_INDIC_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# Strip Unicode Bidirectional Override characters (U+202A..U+202E, U+2066..U+2069) and Zero-Width chars
_BIDI_AND_ZW_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\u2066-\u2069\ufeff]")

# South Sudan TIN: 9 to 12 digits (optionally prefixed by TIN- or NRA-/SSRA-)
_TIN_RE = re.compile(r"\b(?:(?:TIN|NRA|SSRA)[-\s]?)?(\d{5,8})(\d{4})\b", flags=re.IGNORECASE)

# South Sudan phone numbers: +2119XXXXXXXX or 09[12578]XXXXXXX
_PHONE_SS_RE = re.compile(
    r"(?:\+211[\s-]?(?:9\d)[\s-]?\d{3}[\s-]?\d{2}(\d{2})|\b09[12578][\s-]?\d{3}[\s-]?\d{2}(\d{2})\b)"
)

# 6-digit OTP codes when preceded by OTP keywords
_OTP_RE = re.compile(r"\b(otp|code|pin)\s*(?:is|:)?\s*(\d{6})\b", flags=re.IGNORECASE)

# Personal email addresses (excluding official published support@nra.gov.ss)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# South Sudan Passport number (R or P followed by 7-8 digits)
_PASSPORT_SS_RE = re.compile(r"\b[RP]\d{7,8}\b")

# OAuth Bearer tokens, raw JWTs, and API secret keys (MCP01:2025 & OWASP ASVS 5.0 V16.2.5)
_SECRET_TOKEN_RE = re.compile(
    r"(?:\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b|"
    r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b|"
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,})\b)"
)


@dataclass(frozen=True)
class RedactionResult:
    redacted_text: str
    pii_tags: list[str]


def mask_tin(raw_tin: str) -> str:
    """Mask a TIN to last 4 digits (e.g. '••••1234') per Section 12.3, normalizing Arabic-Indic digits."""
    normalised = raw_tin.translate(_ARABIC_INDIC_MAP)
    digits = "".join(ch for ch in normalised if ch.isdigit())
    if len(digits) < 4:
        return "••••"
    return f"••••{digits[-4:]}"


def redact_pii(text: str) -> RedactionResult:
    """Redact South Sudan TINs, +211 phones, OTPs, personal emails, and passports across ASCII & Arabic digits."""
    tags: list[str] = []
    if _BIDI_AND_ZW_RE.search(text):
        tags.append("UNICODE_BIDI_OR_ZW_STRIPPED")
    out = _BIDI_AND_ZW_RE.sub("", unicodedata.normalize("NFKC", text)).translate(_ARABIC_INDIC_MAP)

    def _replace_otp(match: re.Match[str]) -> str:
        """Mask 6-digit OTP codes preceded by OTP/code/PIN keywords."""
        tags.append("OTP_SECRET")
        return f"{match.group(1)} [REDACTED_OTP]"

    out = _OTP_RE.sub(_replace_otp, out)

    def _replace_secret_token(_match: re.Match[str]) -> str:
        """Mask leaked Bearer tokens, JWTs, and API keys (MCP01:2025 / ASVS V16.2.5)."""
        tags.append("SECRET_OR_BEARER_TOKEN")
        return "[REDACTED_SECRET_TOKEN]"

    out = _SECRET_TOKEN_RE.sub(_replace_secret_token, out)

    def _replace_email(match: re.Match[str]) -> str:
        """Mask personal email addresses while preserving official support@nra.gov.ss."""
        candidate = match.group(0)
        if candidate.lower() == "support@nra.gov.ss":
            return candidate
        tags.append("EMAIL_ADDRESS")
        return "[REDACTED_EMAIL]"

    out = _EMAIL_RE.sub(_replace_email, out)

    def _replace_passport(match: re.Match[str]) -> str:
        tags.append("PASSPORT_SS")
        return f"•••{match.group(0)[-3:]}"

    out = _PASSPORT_SS_RE.sub(_replace_passport, out)

    def _replace_phone(match: re.Match[str]) -> str:
        tags.append("PHONE_SS_211")
        last2 = match.group(1) or match.group(2) or "••"
        return f"+211•••••••{last2}"

    out = _PHONE_SS_RE.sub(_replace_phone, out)

    def _replace_tin(match: re.Match[str]) -> str:
        tags.append("SSRA_TIN")
        return f"••••{match.group(2)}"

    out = _TIN_RE.sub(_replace_tin, out)

    return RedactionResult(redacted_text=out, pii_tags=sorted(set(tags)))
