"""PII detection and masking for South Sudan TINs, +211 phone numbers, National IDs, and OTPs."""

from __future__ import annotations

import re
from dataclasses import dataclass

# South Sudan TIN: 9 to 12 digits (optionally prefixed by TIN- or NRA-/SSRA-)
_TIN_RE = re.compile(r"\b(?:(?:TIN|NRA|SSRA)[-\s]?)?(\d{5,8})(\d{4})\b", flags=re.IGNORECASE)

# South Sudan phone numbers: +2119XXXXXXXX or 09[12578]XXXXXXX
_PHONE_SS_RE = re.compile(
    r"(?:\+211[\s-]?(?:9\d)[\s-]?\d{3}[\s-]?\d{2}(\d{2})|\b09[12578][\s-]?\d{3}[\s-]?\d{2}(\d{2})\b)"
)

# 6-digit OTP codes when preceded by OTP keywords
_OTP_RE = re.compile(r"\b(otp|code|pin)\s*(?:is|:)?\s*(\d{6})\b", flags=re.IGNORECASE)


@dataclass(frozen=True)
class RedactionResult:
    redacted_text: str
    pii_tags: list[str]


def mask_tin(raw_tin: str) -> str:
    """Mask a TIN to last 4 digits (e.g. 'TIN ••••1234') per Section 12.3."""
    digits = "".join(ch for ch in raw_tin if ch.isdigit())
    if len(digits) < 4:
        return "••••"
    return f"••••{digits[-4:]}"


def redact_pii(text: str) -> RedactionResult:
    """Redact South Sudan TINs, +211 phone numbers, and OTPs before logging or external egress."""
    tags: list[str] = []
    out = text

    def _replace_otp(match: re.Match[str]) -> str:
        tags.append("OTP_SECRET")
        return f"{match.group(1)} [REDACTED_OTP]"

    out = _OTP_RE.sub(_replace_otp, out)

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
