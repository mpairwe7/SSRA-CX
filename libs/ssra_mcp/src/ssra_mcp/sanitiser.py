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
MAX_STRING_FIELD_LEN = 2000


def is_allowed_ssra_url(url: str) -> bool:
    try:
        parsed = urlparse(url.rstrip(".,;:)]"))
        host = (parsed.hostname or "").lower()
        return parsed.scheme == "https" and host in ALLOWED_SSRA_DOMAINS
    except Exception:
        return False


def scrub_untrusted_urls_and_cap_length(text: str, max_len: int = MAX_STRING_FIELD_LEN) -> str:
    def _check_url(match: re.Match[str]) -> str:
        raw_url = match.group(0)
        trailing = ""
        while raw_url and raw_url[-1] in ".,;:)]":
            trailing = raw_url[-1] + trailing
            raw_url = raw_url[:-1]
        if is_allowed_ssra_url(raw_url):
            return raw_url + trailing
        return f"[REDACTED_UNALLOWLISTED_URL]{trailing}"

    scrubbed = _URL_RE.sub(_check_url, text)
    return scrubbed[:max_len]


def sanitise_structured_output(value: Any, max_len: int = MAX_STRING_FIELD_LEN) -> Any:
    if isinstance(value, str):
        return scrub_untrusted_urls_and_cap_length(value, max_len=max_len)
    if isinstance(value, dict):
        return {str(k): sanitise_structured_output(v, max_len=max_len) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitise_structured_output(item, max_len=max_len) for item in value]
    return value


def wrap_tool_result_as_untrusted_data(tool_name: str, structured_content: dict[str, Any]) -> str:
    sanitised = sanitise_structured_output(structured_content)
    payload = json.dumps(sanitised, ensure_ascii=False, sort_keys=True)
    return f'<untrusted_tool_result tool="{tool_name}">\n{payload}\n</untrusted_tool_result>'
