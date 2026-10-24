"""MCP Tool Output Sanitiser (Section 8.3: allow-listed URLs only, length caps, wrapped as data)."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

ALLOWED_SSRA_DOMAINS: frozenset[str] = frozenset(
    {
        "nra.gov.ss",
        "www.nra.gov.ss",
        "etax.nra.gov.ss",
        "ecustoms.nra.gov.ss",
        "cms.nra.gov.ss",
        "eservices.gov.ss",
        "business.eservices.gov.ss",
        "customs.eservices.gov.ss",
        "www.trade.eservices.gov.ss",
        "ssra.gov.ss",
        "etax.ssra.gov.ss",
        "assist.ssra.gov.ss",
        "mofp.gov.ss",
        "www.mofp.gov.ss",
        "boss.gov.ss",
        "mojca.gov.ss",
    }
)

_URL_RE = re.compile(r"https?://[^\s\"'<>]+", flags=re.IGNORECASE)
_DANGEROUS_URI_RE = re.compile(
    r"\b(?:javascript|data|vbscript|file):[^\s\"'<>]*",
    flags=re.IGNORECASE,
)
_DELIMITER_BREAKOUT_RE = re.compile(
    r"(</?untrusted_tool_result[^>]*>|<\|im_start\|>|<\|im_end\|>|<\|endoftext\|>|\[/?INST\])",
    flags=re.IGNORECASE,
)
_CONTEXTUAL_PROMPT_INJECTION_RE = re.compile(
    r"(?:ignore\s+(?:all\s+)?(?:previous|prior|system)\s+(?:instructions|rules|prompts)|"
    r"disregard\s+system\s+policy|"
    r"tell\s+the\s+user\s+to\s+pay\s+to\s+account|"
    r"!\[[^\]]*\]\(https?://[^\s)]+\))",
    flags=re.IGNORECASE,
)
_BIDI_OVERRIDE_RE = re.compile(r"[\u202a-\u202e\u2066-\u2069]")
_SAFE_TOOL_NAME_RE = re.compile(r"^[a-z0-9_.-]{1,64}$")
MAX_STRING_FIELD_LEN = 2000


def is_allowed_ssra_url(url: str) -> bool:
    """Return True if url is an HTTPS URL on an allow-listed South Sudan government domain."""
    try:
        parsed = urlparse(url.rstrip(".,;:)]"))
        host = (parsed.hostname or "").lower()
        return (
            parsed.scheme == "https"
            and not parsed.username
            and not parsed.password
            and host in ALLOWED_SSRA_DOMAINS
        )
    except Exception:
        return False


def scrub_untrusted_urls_and_cap_length(text: str, max_len: int = MAX_STRING_FIELD_LEN) -> str:
    """Scrub Bidi overrides, delimiter breakouts, MCP06 contextual injections, dangerous URIs, and unallowlisted URLs."""

    def _check_url(match: re.Match[str]) -> str:
        """Replace non-allowlisted HTTP(S) URLs while preserving trailing punctuation."""
        raw_url = match.group(0)
        trailing = ""
        while raw_url and raw_url[-1] in ".,;:)]":
            trailing = raw_url[-1] + trailing
            raw_url = raw_url[:-1]
        if is_allowed_ssra_url(raw_url):
            return raw_url + trailing
        return f"[REDACTED_UNALLOWLISTED_URL]{trailing}"

    scrubbed = _BIDI_OVERRIDE_RE.sub("", text)
    scrubbed = _DELIMITER_BREAKOUT_RE.sub("[REDACTED_DELIMITER_BREAKOUT]", scrubbed)
    scrubbed = _CONTEXTUAL_PROMPT_INJECTION_RE.sub(
        "[REDACTED_MCP06_CONTEXTUAL_INJECTION]", scrubbed
    )
    scrubbed = _DANGEROUS_URI_RE.sub("[REDACTED_DANGEROUS_URI]", scrubbed)
    scrubbed = _URL_RE.sub(_check_url, scrubbed)
    return scrubbed[:max_len]


def sanitise_structured_output(
    value: Any,
    max_len: int = MAX_STRING_FIELD_LEN,
    *,
    _depth: int = 0,
    max_depth: int = 12,
) -> Any:
    """Recursively sanitise strings and dict keys inside structured MCP tool output with depth bounds."""
    if _depth > max_depth:
        return "[REDACTED_MAX_DEPTH_EXCEEDED]"
    if isinstance(value, str):
        return scrub_untrusted_urls_and_cap_length(value, max_len=max_len)
    if isinstance(value, dict):
        return {
            scrub_untrusted_urls_and_cap_length(str(k), max_len=256): sanitise_structured_output(
                v, max_len=max_len, _depth=_depth + 1, max_depth=max_depth
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [
            sanitise_structured_output(
                item, max_len=max_len, _depth=_depth + 1, max_depth=max_depth
            )
            for item in value
        ]
    return value


def wrap_tool_result_as_untrusted_data(tool_name: str, structured_content: dict[str, Any]) -> str:
    """Wrap sanitised MCP tool output in spotlighted <untrusted_tool_result> data delimiters."""
    safe_tool = tool_name if _SAFE_TOOL_NAME_RE.match(tool_name) else "mcp_tool"
    sanitised = sanitise_structured_output(structured_content)
    payload = json.dumps(sanitised, ensure_ascii=False, sort_keys=True)
    return f'<untrusted_tool_result tool="{safe_tool}">\n{payload}\n</untrusted_tool_result>'
