"""Political neutrality and prohibited promise guardrail (Sections 2, 3, 6.1, 12.2)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_PROHIBITED_PROMISE_RE = re.compile(
    r"\b(your\s+penalty\s+will\s+be\s+waived|"
    r"we\s+have\s+waived\s+your\s+(tax|penalty)|"
    r"this\s+is\s+a\s+binding\s+legal\s+ruling|"
    r"pay\s+cash\s+to\s+an?\s+(officer|collector)|"
    r"ssra\s+admits\s+legal\s+liability|"
    r"i\s+guarantee\s+your\s+refund\s+is\s+approved)\b",
    flags=re.IGNORECASE,
)

_POLITICAL_COMMENTARY_RE = re.compile(
    r"\b(vote\s+for|political\s+party\s+endorsement|regime\s+criticism)\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class NeutralityResult:
    passed: bool
    reason: str | None = None


def validate_neutrality_and_promises(text: str) -> NeutralityResult:
    if _PROHIBITED_PROMISE_RE.search(text):
        return NeutralityResult(
            passed=False,
            reason="Output contains a prohibited T4 promise (waiver, binding legal ruling, or cash payment)",
        )
    if _POLITICAL_COMMENTARY_RE.search(text):
        return NeutralityResult(
            passed=False,
            reason="Output violates SSRA strict political neutrality policy",
        )
    return NeutralityResult(passed=True)
