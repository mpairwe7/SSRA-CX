"""Explicit Language-State Machine & Canonical English-Router Form (SSRA Assist October 2026).

Enforces:
1. Hysteretic Language-State Machine (`LOCKED`, `CODE_SWITCHING`, `CANDIDATE_SHIFT`, `FALLBACK_EN`)
   requiring 2 consecutive turns to shift primary session locale unless the taxpayer explicitly requests a switch.
2. Multilingual vernacular detection across all 8 South Sudan BCP-47 languages
   (`en`, `pga`, `ar`, `din`, `nus`, `bfa`, `zne`, `shk`).
3. Canonical English-Router normalization (`EnglishRouterEnvelope`) preserving all statutory tokens
   (TINs, SSP/USD amounts, section anchors, form codes) untouched.
"""

from __future__ import annotations

import re
from typing import Literal

from ssra_core import EnglishRouterEnvelope, LocaleCode

LanguageStateLiteral = Literal["LOCKED", "CODE_SWITCHING", "CANDIDATE_SHIFT", "FALLBACK_EN"]

# Statutory tokens that must NEVER be altered by translation or normalization
_STATUTORY_TOKEN_RE = re.compile(
    r"\b(?:TIN[-:\s]*\d{6,12}|ETAX-[A-Z0-9-]+|Part-[IVX]+-Sec-\d+[A-Za-z0-9-]*|"
    r"Sec-\d+[A-Za-z0-9-]*|\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{4,12})\b",
    flags=re.IGNORECASE,
)

# South Sudan vernacular (`pga`, `ar`, `din`, `nus`, `bfa`, `zne`, `shk`) -> canonical English routing concept map
_VERNACULAR_TO_CANONICAL_EN: tuple[tuple[tuple[str, ...], str, str], ...] = (
    # Juba Arabic (`pga`)
    (("dariba ta mahiya", "gurush ta mahiya"), "pga", "calculate paye salary tax"),
    (("shahada ta imtisal", "imtisal"), "pga", "tax compliance certificate tcc"),
    (("tasjil", "ragam daribi"), "pga", "register tin taxpayer identification number"),
    (("gamarik", "bidaa"), "pga", "customs duties tariff declaration"),
    (("hisab", "gurush kam", "medyun"), "pga", "check my tax balance"),
    # Arabic (`ar`)
    (("ضريبة الدخل", "ضريبة المرتبات"), "ar", "calculate paye salary tax"),
    (("شهادة الامتثال",), "ar", "tax compliance certificate tcc"),
    (("الرقم الضريبي", "تسجيل"), "ar", "register tin taxpayer identification number"),
    (("الجمارك", "التعريفة"), "ar", "customs duties tariff declaration"),
    # Dinka (`din`)
    (("ajul", "wëu", "bɛ̈ŋic"), "din", "south sudan tax procedures and official e-tax bank payment"),
    # Nuer (`nus`)
    (
        ("yiööth", "juäärä", "cuɔl"),
        "nus",
        "south sudan tax procedures and official e-tax bank payment",
    ),
    # Bari (`bfa`)
    (
        ("kaser", "lɔŋɔt", "banki lo"),
        "bfa",
        "south sudan tax procedures and official e-tax bank payment",
    ),
    # Zande (`zne`)
    (
        ("marã", "tumosi", "rogo ssra"),
        "zne",
        "south sudan tax procedures and official e-tax bank payment",
    ),
    # Shilluk (`shk`)
    (
        ("cøøri", "ocul jami", "bëëne"),
        "shk",
        "south sudan tax procedures and official e-tax bank payment",
    ),
)

_EXPLICIT_SWITCH_RE = re.compile(
    r"\b(?:speak|switch\s+to|respond\s+in|in)\s+(english|arabic|juba\s+arabic|dinka|nuer|bari|zande|shilluk)\b",
    flags=re.IGNORECASE,
)

_LANGUAGE_NAME_TO_LOCALE: dict[str, LocaleCode] = {
    "english": LocaleCode.EN,
    "arabic": LocaleCode.AR,
    "juba arabic": LocaleCode.PGA,
    "dinka": LocaleCode.DIN,
    "nuer": LocaleCode.NUS,
    "bari": LocaleCode.BFA,
    "zande": LocaleCode.ZNE,
    "shilluk": LocaleCode.SHK,
}


def extract_preserved_statutory_tokens(text: str) -> list[str]:
    """Extract TINs, section anchors, form codes, and numeric amounts that must never be modified."""
    matches = _STATUTORY_TOKEN_RE.findall(text)
    return list(dict.fromkeys(m.strip() for m in matches if m.strip()))


def evaluate_language_state_transition(
    *,
    previous_locale: LocaleCode,
    detected_locale: LocaleCode,
    previous_candidate: LocaleCode | None = None,
    raw_text: str = "",
) -> tuple[LocaleCode, LanguageStateLiteral, LocaleCode | None]:
    """Apply 2-turn hysteresis to prevent mid-session language thrashing on short/code-switched utterances.

    Returns `(effective_locale, language_state, next_candidate_locale)`.
    """
    explicit_match = _EXPLICIT_SWITCH_RE.search(raw_text)
    if explicit_match:
        lang_name = explicit_match.group(1).strip().lower()
        target = _LANGUAGE_NAME_TO_LOCALE.get(lang_name, detected_locale)
        return target, "LOCKED", None

    if detected_locale == previous_locale:
        return previous_locale, "LOCKED", None

    # Check if the utterance mixes English and South Sudanese vernacular terms (code-switching)
    lower = raw_text.lower()
    has_en_tax_word = any(
        w in lower
        for w in ("tin", "tcc", "paye", "tax", "balance", "return", "etax", "ssra", "nra")
    )
    if has_en_tax_word and detected_locale != LocaleCode.EN and previous_locale == LocaleCode.EN:
        return previous_locale, "CODE_SWITCHING", detected_locale

    if previous_candidate == detected_locale:
        return detected_locale, "LOCKED", None

    return previous_locale, "CANDIDATE_SHIFT", detected_locale


def build_english_router_envelope(
    raw_text: str,
    *,
    source_locale: LocaleCode,
    language_state: LanguageStateLiteral = "LOCKED",
    extracted_slots: dict[str, str | int | float | bool] | None = None,
) -> EnglishRouterEnvelope:
    """Normalize South Sudanese vernacular or code-switched input into a canonical English-Router Envelope."""
    cleaned = raw_text.strip() or "general tax inquiry"
    lower = cleaned.lower()
    preserved = extract_preserved_statutory_tokens(cleaned)

    detected_vernacular = source_locale.value
    expansions: list[str] = []

    for markers, vern_code, en_concept in _VERNACULAR_TO_CANONICAL_EN:
        if any(m in lower for m in markers):
            detected_vernacular = vern_code
            if en_concept not in expansions:
                expansions.append(en_concept)

    if expansions:
        token_suffix = f" [{' '.join(preserved)}]" if preserved else ""
        canonical_en = f"{cleaned} — {' ; '.join(expansions)}{token_suffix}"
    else:
        canonical_en = cleaned

    return EnglishRouterEnvelope(
        source_locale=source_locale,
        detected_vernacular=detected_vernacular,
        language_state=language_state,
        canonical_en_query=canonical_en[:500],
        extracted_slots=dict(extracted_slots or {}),
        preserved_statutory_tokens=preserved,
    )
