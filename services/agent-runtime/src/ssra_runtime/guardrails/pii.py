"""PII and cross-subject leakage guardrail (Section 6.1, 12.3, 14.2)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from ssra_security import mask_tin, redact_pii

_UNMASKED_TIN_RE = re.compile(r"\b(?:[0-9]{9,12}|[0-9]{3}[-\s][0-9]{3}[-\s]?[0-9]{4})\b")
_UNMASKED_PASSPORT_RE = re.compile(
    r"(?<![A-Za-z0-9_])[RP][0-9]{7,8}(?![A-Za-z0-9_])",
    flags=re.IGNORECASE,
)
_OFFICIAL_HELPDESK_NUMBERS_RE = re.compile(
    r"\+211[\s-]*(?:918[\s-]*806[\s-]*493|912[\s-]*388[\s-]*318|919[\s-]*382[\s-]*390|917[\s-]*803[\s-]*637|921[\s-]*058[\s-]*043)\b"
)
_UNMASKED_PHONE_SS_RE = re.compile(
    r"(?:\+211[\s-]?(?:9[0-9](?:[\s-]?[0-9]){7})\b|\b09[12578](?:[\s-]?[0-9]){7}\b)"
)
_LEAKED_SECRET_RE = re.compile(
    r"(?:\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b|"
    r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b|"
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,})\b)"
)


def _normalise_unicode_digits(text: str) -> str:
    """Convert any Unicode decimal digit character (Arabic-Indic, fullwidth, Devanagari, etc.) to ASCII 0-9."""
    chars: list[str] = []
    for ch in unicodedata.normalize("NFKC", text):
        if unicodedata.category(ch) == "Nd":
            chars.append(str(unicodedata.decimal(ch)))
        else:
            chars.append(ch)
    return "".join(chars)


@dataclass(frozen=True)
class PiiGuardResult:
    passed: bool
    reason: str | None = None


def verify_no_cross_subject_or_unmasked_pii(
    text: str,
    *,
    allowed_masked_tin: str | None = None,
) -> PiiGuardResult:
    """Verify model output contains zero unmasked TINs, National IDs, personal +211 phones, secrets, or cross-subject masked TINs."""
    normalised = _normalise_unicode_digits(text)
    scrubbed_helpdesk = _OFFICIAL_HELPDESK_NUMBERS_RE.sub("", normalised)
    if _LEAKED_SECRET_RE.search(scrubbed_helpdesk):
        return PiiGuardResult(
            passed=False,
            reason="Output contains a leaked Bearer/JWT token or API secret (MCP01:2025)",
        )
    if _UNMASKED_PHONE_SS_RE.search(scrubbed_helpdesk):
        return PiiGuardResult(
            passed=False,
            reason="Output contains an unmasked personal +211 South Sudan phone number",
        )
    if _UNMASKED_TIN_RE.search(scrubbed_helpdesk):
        return PiiGuardResult(
            passed=False,
            reason="Output contains an unmasked 9-12 digit TIN identifier",
        )
    if _UNMASKED_PASSPORT_RE.search(scrubbed_helpdesk):
        return PiiGuardResult(
            passed=False,
            reason="Output contains an unmasked South Sudan National ID or Passport number",
        )
    # Check if a different masked TIN (••••XXXX) appears than the bound subject's masked TIN
    masked_matches = re.findall(r"••••[0-9]{4}", normalised)
    if allowed_masked_tin:
        for m in masked_matches:
            if m != allowed_masked_tin:
                return PiiGuardResult(
                    passed=False,
                    reason=f"Cross-subject TIN leakage detected: '{m}' != '{allowed_masked_tin}'",
                )
    elif masked_matches:
        return PiiGuardResult(
            passed=False,
            reason="Masked personal TIN appeared in an anonymous T0 response",
        )
    return PiiGuardResult(passed=True)


__all__ = ["PiiGuardResult", "mask_tin", "redact_pii", "verify_no_cross_subject_or_unmasked_pii"]
