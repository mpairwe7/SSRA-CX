"""Prompt-injection and goal-hijack guardrail with 6-Pass Unicode/Homoglyph Normalizer (OWASP Agentic ASI01 & ASI02, Section 6.1 & 12.2)."""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass

_ZERO_WIDTH_AND_BIDI_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\u2066-\u2069\ufeff]")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", flags=re.DOTALL)
_WHITESPACE_RE = re.compile(r"\s+")

_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "PROMPT_INJECTION_IGNORE_RULES",
        re.compile(
            r"(ignore\s+(all\s+)?(previous|prior|system)\s+(instructions|rules|prompts)|"
            r"disregard\s+system\s+policy|reveal\s+your\s+system\s+prompt|"
            r"تجاهل\s+(?:جميع\s+)?التعليمات|اكشف\s+موجه\s+النظام|"
            r"khali\s+kullu\s+talimat)",
            flags=re.IGNORECASE,
        ),
    ),
    (
        "GOAL_HIJACK_PAYMENT_DIVERSION",
        re.compile(
            r"(tell\s+the\s+user\s+to\s+pay\s+to\s+account|"
            r"send\s+tax\s+money\s+to\s+personal\s+number|"
            r"override\s+official\s+bank\s+account|"
            r"ادفع\s+الضريبة\s+إلى\s+حساب|adfa\s+gurush\s+fi\s+hisab\s+shakhsi)",
            flags=re.IGNORECASE,
        ),
    ),
    (
        "CROSS_SUBJECT_IDOR_ATTEMPT",
        re.compile(
            r"(show\s+(me\s+)?(balance|filings?|tcc|record)\s+(for|of)\s+(another|other)\s+taxpayer|"
            r"balance\s+(for|of)\s+tin\s+\d{6,12}|"
            r"access\s+victim\s+tin)",
            flags=re.IGNORECASE,
        ),
    ),
    (
        "DATA_EXFILTRATION_MARKDOWN_OR_DELIMITER",
        re.compile(
            r"(!\[[^\]]*\]\(https?://[^\s)]+\)|"
            r"</?untrusted_(?:user_document|knowledge_chunk|tool_result)[^>]*>)",
            flags=re.IGNORECASE,
        ),
    ),
)


def normalise_adversarial_input(raw_text: str) -> str:
    """Execute 6-pass canonicalization before prompt-injection scanning (OWASP ASI01 2026)."""
    # Pass 1: HTML entity decode
    step1 = html.unescape(raw_text)
    # Pass 2: Strip zero-width and Unicode Bidirectional Override characters
    step2 = _ZERO_WIDTH_AND_BIDI_RE.sub("", step1)
    # Pass 3: Unicode NFKC compatibility normalization (collapses fullwidth chars U+FF49.. to ASCII)
    step3 = unicodedata.normalize("NFKC", step2)
    # Pass 4: Strip hidden HTML comments
    step4 = _HTML_COMMENT_RE.sub(" ", step3)
    # Pass 5: Strip combining diacritical marks used to obfuscate ASCII keywords
    step5 = "".join(
        ch for ch in unicodedata.normalize("NFD", step4) if unicodedata.category(ch) != "Mn"
    )
    # Pass 6: Collapse repeated whitespace
    return _WHITESPACE_RE.sub(" ", step5).strip()


@dataclass(frozen=True)
class InjectionCheckResult:
    is_blocked: bool
    flags: list[str]
    normalised_text: str = ""


def check_prompt_injection(text: str) -> InjectionCheckResult:
    normalised = normalise_adversarial_input(text)
    flags: list[str] = []
    for flag_name, pattern in _INJECTION_PATTERNS:
        if pattern.search(text) or pattern.search(normalised):
            flags.append(flag_name)
    return InjectionCheckResult(
        is_blocked=len(flags) > 0,
        flags=flags,
        normalised_text=normalised,
    )
