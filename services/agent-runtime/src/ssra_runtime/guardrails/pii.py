"""PII and cross-subject leakage guardrail (Section 6.1, 12.3, 14.2)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ssra_security import mask_tin, redact_pii

_ARABIC_INDIC_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_UNMASKED_TIN_RE = re.compile(r"\b\d{9,12}\b")
_UNMASKED_PASSPORT_RE = re.compile(r"\b[RP]\d{7,8}\b")


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
    normalised = text.translate(_ARABIC_INDIC_MAP)
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
    masked_matches = re.findall(r"••••\d{4}", normalised)
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
