"""PII and cross-subject leakage guardrail (Section 6.1, 12.3, 14.2)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from ssra_security import mask_tin, redact_pii

_UNMASKED_TIN_RE = re.compile(r"\b[0-9]{9,12}\b")
_UNMASKED_PASSPORT_RE = re.compile(
    r"(?<![A-Za-z0-9_])[RP][0-9]{7,8}(?![A-Za-z0-9_])",
    flags=re.IGNORECASE,
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
    """Verify model output contains zero unmasked TINs, National IDs, or cross-subject masked TINs."""
    normalised = _normalise_unicode_digits(text)
    if _UNMASKED_TIN_RE.search(normalised):
        return PiiGuardResult(
            passed=False,
            reason="Output contains an unmasked 9-12 digit TIN identifier",
        )
    if _UNMASKED_PASSPORT_RE.search(normalised):
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
