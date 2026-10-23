"""Tests for fitting answer text to voice, IVR, and SMS limits without cutting a figure (AUD-041)."""

from __future__ import annotations

import re

from ssra_core import (
    compose_spoken_reply,
    compute_sms_segments,
    count_sms_segments,
    fit_text,
    sms_encoding,
    split_sentences,
)

_FIGURE_RE = re.compile(r"\d[\d,.]*")


def test_sms_segments_follow_gsm7_and_utf16_units() -> None:
    # ÆæßÉ are in the GSM 03.38 basic table, so they no longer force UCS-2.
    assert sms_encoding("Ærø Café É ß") == "GSM-7"
    assert count_sms_segments("A" * 160) == 1
    assert count_sms_segments("A" * 161) == 2
    assert count_sms_segments("€" * 80) == 1  # extension characters cost two septets
    assert count_sms_segments("€" * 81) == 2
    assert count_sms_segments("ب" * 70) == 1
    assert count_sms_segments("ب" * 71) == 2
    # A character outside the Basic Multilingual Plane is two UTF-16 code units.
    assert compute_sms_segments("😀" * 35)["septet_or_code_unit_count"] == 70
    assert count_sms_segments("😀" * 36) == 2


def test_split_sentences_keeps_abbreviations_and_arabic_questions() -> None:
    assert split_sentences("Per Reg. 1.21 and Sec. 18, PAYE applies. Pay via bank.") == [
        "Per Reg. 1.21 and Sec. 18, PAYE applies.",
        "Pay via bank.",
    ]
    assert len(split_sentences("كيف أسجل؟ استخدم البوابة.")) == 2


def test_fit_text_drops_whole_sentences_and_never_ends_on_a_figure() -> None:
    text = "Your PAYE is 25,000 SSP per month. File by the 15th. Pay only through a bank."
    fitted = fit_text(text, fits=lambda candidate: len(candidate) <= 52)
    assert fitted.text == "Your PAYE is 25,000 SSP per month. ..."
    assert (fitted.kept_sentences, fitted.total_sentences) == (1, 3)

    tight = fit_text(text, fits=lambda candidate: len(candidate) <= 23)
    assert tight.shortened_inside_sentence is True
    # "Your PAYE is 25,000" would fit, but a figure is never left without the words after it.
    assert tight.text == "Your PAYE is ..."
    for figure in _FIGURE_RE.findall(tight.text):
        assert figure in text


def test_spoken_reply_frames_estimates_on_the_spoken_sentences() -> None:
    reply = "PAYE is 25,000 SSP. File by the 15th. Pay via bank. This is an estimate."
    spoken = compose_spoken_reply(reply, is_estimate=True)
    assert spoken.kept_sentences == 3
    # The only "estimate" was in the fourth, unspoken sentence, so the framing is added.
    assert spoken.text.startswith("Estimate only. PAYE is 25,000 SSP.")
    assert "..." not in spoken.text
    capped = compose_spoken_reply("One. Two. Three. Four.", is_estimate=False, max_chars=9)
    assert capped.text == "One. Two."
