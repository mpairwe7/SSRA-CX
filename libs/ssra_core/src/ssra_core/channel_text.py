"""Fit answer text to channel limits without cutting a figure (voice, IVR, and SMS).

Text is shortened by dropping whole sentences from the end. Only when not even the first sentence
fits are words dropped, and never in the middle of a word or right after a number, so a figure is
either sent with the words that follow it or not at all.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

# 3GPP TS 23.038 / GSM 03.38 basic (1 septet) and extension (2 septets via the 0x1B escape) character sets
GSM7_BASIC_CHARS: frozenset[str] = frozenset(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM7_EXTENDED_CHARS: frozenset[str] = frozenset("^{}\\[~]|€\f")

# Master prompt voice rule: speak at most three sentences and offer the rest by SMS.
MAX_SPOKEN_SENTENCES: int = 3
SPOKEN_ESTIMATE_PREFIX = "Estimate only."
OMISSION_MARKER = "..."

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?؟])\s+")
_ABBREV_PROTECT_RE = re.compile(
    r"\b(Sec|Reg|Art|No|Vol|Ch|Pt|Dr|Mr|Mrs|Ms)\.\s+",
    flags=re.IGNORECASE,
)
_HAS_DIGIT_RE = re.compile(r"\d")


def split_sentences(text: str) -> list[str]:
    """Split text into sentences while preserving statutory abbreviations (`Sec. 18`, `Reg. 1.21`)."""
    cleaned = text.strip()
    if not cleaned:
        return []
    protected = _ABBREV_PROTECT_RE.sub(r"\1<DOT> ", cleaned)
    return [
        s.replace("<DOT>", ".").strip() for s in _SENTENCE_SPLIT_RE.split(protected) if s.strip()
    ]


def sms_encoding(text: str) -> Literal["GSM-7", "UCS-2"]:
    """Return the SMS encoding a message needs; one character outside GSM-7 forces UCS-2."""
    if all(ch in GSM7_BASIC_CHARS or ch in GSM7_EXTENDED_CHARS for ch in text):
        return "GSM-7"
    return "UCS-2"


def _sms_units(text: str, encoding: Literal["GSM-7", "UCS-2"]) -> int:
    if encoding == "GSM-7":
        return sum(2 if ch in GSM7_EXTENDED_CHARS else 1 for ch in text)
    return len(text.encode("utf-16-le")) // 2


def count_sms_segments(text: str) -> int:
    """Return how many SMS segments a message needs (160 or 153 GSM-7 septets; 70 or 67 UCS-2 units)."""
    encoding = sms_encoding(text)
    units = _sms_units(text, encoding)
    single_limit, concat_limit = (160, 153) if encoding == "GSM-7" else (70, 67)
    if units == 0:
        return 0
    if units <= single_limit:
        return 1
    return math.ceil(units / concat_limit)


def compute_sms_segments(text: str) -> dict[str, int | str]:
    """Compute SMS encoding (3GPP TS 23.038 GSM-7 + Extended vs UCS-2) and segment count (Section 11)."""
    encoding = sms_encoding(text)
    return {
        "encoding": encoding,
        "char_count": len(text),
        "septet_or_code_unit_count": _sms_units(text, encoding),
        "segments": count_sms_segments(text),
        "per_segment_limit": 160 if encoding == "GSM-7" else 70,
    }


@dataclass(frozen=True)
class FittedText:
    text: str
    kept_sentences: int
    total_sentences: int
    shortened_inside_sentence: bool


def _join(*parts: str) -> str:
    return " ".join(part for part in parts if part)


def _words_without_trailing_figures(words: Sequence[str]) -> list[str]:
    kept = list(words)
    while kept and _HAS_DIGIT_RE.search(kept[-1]):
        kept.pop()
    return kept


def fit_text(
    text: str,
    *,
    fits: Callable[[str], bool],
    prefix: str = "",
    suffix: str = "",
    max_sentences: int | None = None,
    omission_marker: str = OMISSION_MARKER,
) -> FittedText:
    """Fit `text` between `prefix` and `suffix` so that `fits` accepts the result.

    Whole sentences are kept from the start. If none fits, words of the first sentence are kept up to
    the last one that is not a number. Shortened text ends with `omission_marker`.
    """
    sentences = split_sentences(text)
    limit = len(sentences) if max_sentences is None else max(0, max_sentences)
    for kept in range(min(limit, len(sentences)), 0, -1):
        marker = omission_marker if kept < len(sentences) else ""
        candidate = _join(prefix, " ".join(sentences[:kept]), marker, suffix)
        if fits(candidate):
            return FittedText(candidate, kept, len(sentences), False)

    marker = omission_marker if sentences else ""
    words = sentences[0].split() if sentences else []
    for count in range(len(words) - 1, 0, -1):
        kept_words = _words_without_trailing_figures(words[:count])
        if not kept_words:
            continue
        candidate = _join(prefix, " ".join(kept_words), marker, suffix)
        if fits(candidate):
            return FittedText(candidate, 0, len(sentences), True)
    return FittedText(_join(prefix, marker, suffix), 0, len(sentences), bool(sentences))


def compose_spoken_reply(
    text: str, *, is_estimate: bool, max_chars: int | None = None
) -> FittedText:
    """Return at most three whole sentences to speak, framed as an estimate when it is one.

    The framing is checked on the sentences that will be spoken, not on the full answer.
    """

    def fits(candidate: str) -> bool:
        return max_chars is None or len(candidate) <= max_chars

    spoken = fit_text(text, fits=fits, max_sentences=MAX_SPOKEN_SENTENCES, omission_marker="")
    if not is_estimate or "estimate" in spoken.text.lower():
        return spoken
    return fit_text(
        text,
        fits=fits,
        prefix=SPOKEN_ESTIMATE_PREFIX,
        max_sentences=MAX_SPOKEN_SENTENCES,
        omission_marker="",
    )
