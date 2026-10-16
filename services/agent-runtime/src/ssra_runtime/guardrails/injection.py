"""Prompt-injection and goal-hijack guardrail (OWASP Agentic ASI01 & ASI02, Section 6.1 & 12.2)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "PROMPT_INJECTION_IGNORE_RULES",
        re.compile(
            r"(ignore\s+(all\s+)?(previous|prior|system)\s+(instructions|rules|prompts)|"
            r"disregard\s+system\s+policy|reveal\s+your\s+system\s+prompt)",
            flags=re.IGNORECASE,
        ),
    ),
    (
        "GOAL_HIJACK_PAYMENT_DIVERSION",
        re.compile(
            r"(tell\s+the\s+user\s+to\s+pay\s+to\s+account|"
            r"send\s+tax\s+money\s+to\s+personal\s+number|"
            r"override\s+official\s+bank\s+account)",
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
)


@dataclass(frozen=True)
class InjectionCheckResult:
    is_blocked: bool
    flags: list[str]


def check_prompt_injection(text: str) -> InjectionCheckResult:
    flags: list[str] = []
    for flag_name, pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            flags.append(flag_name)
    return InjectionCheckResult(is_blocked=len(flags) > 0, flags=flags)
