"""Explicit Language-State Machine & Canonical English-Router Form (SSRA Assist October 2026).

Enforces:
1. Hysteretic Language-State Machine (`LOCKED`, `CODE_SWITCHING`, `CANDIDATE_SHIFT`, `FALLBACK_EN`)
   requiring 2 consecutive turns to shift primary session locale unless the taxpayer explicitly requests a switch.
2. Multilingual vernacular & termbase detection across all 8 South Sudan BCP-47 languages
   (`en`, `pga`, `ar`, `din`, `nus`, `bfa`, `zne`, `shk`), dynamically loading `ai/termbase/glossary.yaml`.
3. Canonical English-Router normalization (`EnglishRouterEnvelope`) preserving all statutory tokens
   (TINs, SSP/USD amounts, section anchors, form codes) untouched.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Literal

import yaml
from ssra_core import EnglishRouterEnvelope, LocaleCode

LanguageStateLiteral = Literal["LOCKED", "CODE_SWITCHING", "CANDIDATE_SHIFT", "FALLBACK_EN"]

_GLOSSARY_FILE = Path(__file__).resolve().parents[5] / "ai" / "termbase" / "glossary.yaml"

_ORTHOGRAPHY_FOLD_MAP: dict[str, str] = {
    "ë": "e",
    "ɛ": "e",
    "ɔ": "o",
    "ŋ": "ng",
    "ö": "o",
    "ä": "a",
    "ï": "i",
    "ü": "u",
    "ã": "a",
    "ø": "o",
    "\u0331": "",
    "\u0308": "",
    "\u0303": "",
}


def fold_south_sudan_orthography(text: str) -> str:
    """Normalize Unicode NFC and fold South Sudanese IPA/diacritics to mobile-keyboard ASCII."""
    nfc = unicodedata.normalize("NFC", text or "").lower()
    out: list[str] = []
    for ch in nfc:
        out.append(_ORTHOGRAPHY_FOLD_MAP.get(ch, ch))
    return "".join(out)


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
    (
        ("tasjil", "ragam daribi", "namba ta dariba"),
        "pga",
        "register tin taxpayer identification number",
    ),
    (("gamarik", "bidaa"), "pga", "customs duties tariff declaration"),
    (("hisab", "gurush kam", "medyun"), "pga", "check my tax balance"),
    # Arabic (`ar`)
    (("ضريبة الدخل", "ضريبة المرتبات"), "ar", "calculate paye salary tax"),
    (("شهادة الامتثال",), "ar", "tax compliance certificate tcc"),
    (
        ("الرقم الضريبي", "الرقم التعريفي الضريبي", "تسجيل"),
        "ar",
        "register tin taxpayer identification number",
    ),
    (("الجمارك", "التعريفة"), "ar", "customs duties tariff declaration"),
    # Dinka (`din`)
    (("namba de ajul wëu",), "din", "register tin taxpayer identification number"),
    (("waraga de cuɔk de wëu",), "din", "tax compliance certificate tcc"),
    (("ajul de ariöp de luɔi",), "din", "calculate paye salary tax"),
    (("ajul de rïöök de ɣɔɔc",), "din", "business profit tax bpt"),
    (("ajul määc në cök",), "din", "withholding tax wht"),
    (("ajul", "wëu", "bɛ̈ŋic"), "din", "south sudan tax procedures and official e-tax bank payment"),
    # Nuer (`nus`)
    (("namba juäärä yiööth",), "nus", "register tin taxpayer identification number"),
    (("waraga cuɔk yiööth",), "nus", "tax compliance certificate tcc"),
    (("yiööth luɔi",), "nus", "calculate paye salary tax"),
    (
        ("yiööth", "juäärä", "cuɔl"),
        "nus",
        "south sudan tax procedures and official e-tax bank payment",
    ),
    # Bari (`bfa`)
    (("namba lo kaser",), "bfa", "register tin taxpayer identification number"),
    (("waraga lo kaser",), "bfa", "tax compliance certificate tcc"),
    (
        ("kaser", "lɔŋɔt", "banki lo"),
        "bfa",
        "south sudan tax procedures and official e-tax bank payment",
    ),
    # Zande (`zne`)
    (("namba marã",), "zne", "register tin taxpayer identification number"),
    (("waraga marã",), "zne", "tax compliance certificate tcc"),
    (
        ("marã", "tumosi", "rogo ssra"),
        "zne",
        "south sudan tax procedures and official e-tax bank payment",
    ),
    # Shilluk (`shk`)
    (("namba ocul jami",), "shk", "register tin taxpayer identification number"),
    (("waraga ocul jami",), "shk", "tax compliance certificate tcc"),
    (
        ("cøøri", "ocul jami", "bëëne"),
        "shk",
        "south sudan tax procedures and official e-tax bank payment",
    ),
)


_PREFOLDED_VERNACULAR_TO_CANONICAL_EN: tuple[tuple[tuple[tuple[str, str], ...], str, str], ...] = (
    tuple(
        (
            tuple((m, fold_south_sudan_orthography(m)) for m in markers),
            vern_code,
            en_concept,
        )
        for markers, vern_code, en_concept in _VERNACULAR_TO_CANONICAL_EN
    )
)


def _load_termbase_glossary_expansions() -> tuple[tuple[str, str, str], ...]:
    """Load multilingual term mappings from `ai/termbase/glossary.yaml` into `(marker_lower, locale_code, canonical_en)`."""
    raw = yaml.safe_load(_GLOSSARY_FILE.read_text(encoding="utf-8")) or {}
    entries: list[tuple[str, str, str]] = []
    for item in raw.get("terms", []):
        en_canonical = str(item.get("en", "")).strip().lower()
        for loc_key in ("ar", "pga", "din", "nus", "bfa", "zne", "shk"):
            loc_phrase = str(item.get(loc_key, "")).strip()
            clean_phrase = (
                unicodedata.normalize("NFC", re.sub(r"\s*\([^)]*\)\s*$", "", loc_phrase))
                .strip()
                .lower()
            )
            if len(clean_phrase) >= 4:
                entries.append((clean_phrase, loc_key, en_canonical))
                folded = fold_south_sudan_orthography(clean_phrase)
                if folded != clean_phrase and len(folded) >= 4:
                    entries.append((folded, loc_key, en_canonical))
    return tuple(entries)


_GLOSSARY_EXPANSIONS: tuple[tuple[str, str, str], ...] = _load_termbase_glossary_expansions()

_SWITCH_NEGATION_PREFIX_RE = re.compile(
    r"(?:\b(?:not|no|don'?t|do\s+not|never)|(?:لا|مش))[\s,;:—-]*$",
    flags=re.IGNORECASE,
)
_EXPLICIT_LOCALE_PATTERNS: tuple[tuple[LocaleCode, re.Pattern[str]], ...] = (
    (
        LocaleCode.PGA,
        re.compile(
            r"\b(?:(?:speak|talk|switch\s+to|respond\s+in|reply\s+in|in)\s+(?:juba\s+arabic|arabi\s+juba)|atkalam\s+arabi\s+juba|عربي\s+جوبا)\b",
            flags=re.IGNORECASE,
        ),
    ),
    (
        LocaleCode.AR,
        re.compile(
            r"\b(?:(?:speak|talk|switch\s+to|respond\s+in|reply\s+in|in)\s+arabic|تكلم\s+عربي|تحدث\s+بالعربية|باللغة\s+العربية)\b",
            flags=re.IGNORECASE,
        ),
    ),
    (
        LocaleCode.DIN,
        re.compile(
            r"\b(?:(?:speak|talk|switch\s+to|respond\s+in|reply\s+in|in)\s+(?:dinka|thuongjang)|thuɔŋjäŋ|jam\s+në\s+thuɔŋjäŋ|jam\s+ne\s+thuongjang)\b",
            flags=re.IGNORECASE,
        ),
    ),
    (
        LocaleCode.NUS,
        re.compile(
            r"\b(?:(?:speak|talk|switch\s+to|respond\s+in|reply\s+in|in)\s+(?:nuer|thok\s+na+th)|thok\s+naath|ruacni\s+thok\s+na+th)\b",
            flags=re.IGNORECASE,
        ),
    ),
    (
        LocaleCode.BFA,
        re.compile(
            r"\b(?:(?:speak|talk|switch\s+to|respond\s+in|reply\s+in|in)\s+bari|kutuk\s+na\s+bari|kulya\s+ko\s+bari)\b",
            flags=re.IGNORECASE,
        ),
    ),
    (
        LocaleCode.ZNE,
        re.compile(
            r"\b(?:(?:speak|talk|switch\s+to|respond\s+in|reply\s+in|in)\s+(?:zande|pazande)|pa\s+pazande|fura\s+pa\s+pazande)\b",
            flags=re.IGNORECASE,
        ),
    ),
    (
        LocaleCode.SHK,
        re.compile(
            r"\b(?:(?:speak|talk|switch\s+to|respond\s+in|reply\s+in|in)\s+(?:shilluk|dhog\s+collo)|dhøg\s+cøllø|kwop\s+dhøg\s+cøllø)\b",
            flags=re.IGNORECASE,
        ),
    ),
    (
        LocaleCode.EN,
        re.compile(
            r"\b(?:(?:speak|talk)(?:\s+in)?|switch\s+to|respond\s+in|reply\s+in)\s+english\b|تكلم\s+إنجليزي",
            flags=re.IGNORECASE,
        ),
    ),
)


def detect_explicit_locale_switch(raw_text: str) -> LocaleCode | None:
    """Detect an explicit language switch request with negation rejection and forward self-correction."""
    clean = unicodedata.normalize("NFC", raw_text or "").strip()
    if not clean:
        return None
    best_end = -1
    best_loc: LocaleCode | None = None
    for loc_code, pat in _EXPLICIT_LOCALE_PATTERNS:
        for match in pat.finditer(clean):
            prefix = clean[max(0, match.start() - 24) : match.start()]
            if _SWITCH_NEGATION_PREFIX_RE.search(prefix):
                continue
            if match.end() > best_end:
                best_end = match.end()
                best_loc = loc_code
    return best_loc


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
    explicit_target = detect_explicit_locale_switch(raw_text)
    if explicit_target is not None:
        return explicit_target, "LOCKED", None

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
    cleaned = unicodedata.normalize("NFC", raw_text).strip() or "general tax inquiry"
    lower = cleaned.lower()
    folded_lower = fold_south_sudan_orthography(cleaned)
    preserved = extract_preserved_statutory_tokens(cleaned)

    detected_vernacular = source_locale.value
    expansions: list[str] = []

    for marker_pairs, vern_code, en_concept in _PREFOLDED_VERNACULAR_TO_CANONICAL_EN:
        if any(raw_m in lower or fold_m in folded_lower for raw_m, fold_m in marker_pairs):
            detected_vernacular = vern_code
            if en_concept not in expansions:
                expansions.append(en_concept)

    for marker_lower, vern_code, en_canonical in _GLOSSARY_EXPANSIONS:
        if marker_lower in lower or marker_lower in folded_lower:
            detected_vernacular = vern_code
            if en_canonical not in expansions:
                expansions.append(en_canonical)

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
