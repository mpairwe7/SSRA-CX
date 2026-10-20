"""Sovereign Air-Gap & Production Safety Readiness Gate (NIST SP 800-218 SSDF PO.1.1, OWASP LLM03, ASI10).

Enforces:
1. Sovereign Mode (`SSRA_SOVEREIGN_MODE=true` / `SOVEREIGN_MODE=true`):
   - Zero commercial cloud LLM API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, etc.) in environment (logs variable names only, never secret values).
   - `HF_HUB_OFFLINE=1` active for local HuggingFace weight loading.
   - All configured inference/vector endpoints (`SSRA_VLLM_SUNFLOWER_URL`, `SSRA_VLLM_REASONER_URL`, `SSRA_ORPHEUS_TTS_URL`, `SSRA_QDRANT_URL`) resolve strictly to localhost, loopback, RFC 1918 private IPs, or single-label Docker Compose service names.
2. Production Safety Gate (`SSRA_ENV=production` / `APP_ENV=production`):
   - Rejects default development HMAC secrets (`ssra-dev-hmac-key`, `dev-insecure-change-me`).
   - Rejects `LLM_TRUST_REMOTE_CODE=true` and `STORE_RAW_PROMPTS=true`.
   - Rejects world-writable (`S_IWOTH`) audit/flag storage directories.
   - Rejects persisted feature-flag overrides that disable protected security controls (`PROTECTED_SECURITY_FLAGS`).
"""

from __future__ import annotations

import ipaddress
import os
import re
import stat
from collections.abc import Mapping
from urllib.parse import urlparse

from ssra_core import McpErrorCode, SSRAError

COMMERCIAL_CLOUD_KEY_ENV_VARS: tuple[str, ...] = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
    "CF_AIG_TOKEN",
    "CLOUDFLARE_API_TOKEN",
)

SOVEREIGN_ENDPOINT_ENV_VARS: tuple[str, ...] = (
    "SSRA_VLLM_SUNFLOWER_URL",
    "SSRA_VLLM_REASONER_URL",
    "SSRA_ORPHEUS_TTS_URL",
    "SSRA_QDRANT_URL",
    "VLLM_BASE_URL",
    "REASONER_BASE_URL",
)

PROTECTED_SECURITY_FLAGS: frozenset[str] = frozenset(
    {
        "numeric_provenance",
        "opa_policy_gate",
        "pii_redaction",
        "audit_ledger",
        "auth_required",
        "voice_consent",
        "FF_NUMERIC_PROVENANCE",
        "FF_OPA_POLICY_GATE",
        "FF_PII_REDACTION",
    }
)

_INSECURE_DEFAULT_SECRETS: frozenset[str] = frozenset(
    {
        "ssra-dev-hmac-key",
        "dev-insecure-change-me",
        "changeme",
    }
)

_COMPOSE_SERVICE_HOST_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$", re.IGNORECASE)
_RFC1918_NETWORKS: tuple[ipaddress.IPv4Network, ...] = (
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def is_allowed_sovereign_host(hostname: str | None) -> bool:
    """Return True if `hostname` is localhost, loopback, RFC 1918 private IP, or a single-label Compose service."""
    if not hostname:
        return False
    host = hostname.strip().lower()
    if host in {"localhost", "host.docker.internal"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return "." not in host and bool(_COMPOSE_SERVICE_HOST_RE.match(host))
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if ip.is_loopback:
        return True
    if isinstance(ip, ipaddress.IPv4Address):
        return any(ip in net for net in _RFC1918_NETWORKS)
    return ip in ipaddress.IPv6Network("fc00::/7")


def _is_world_writable(path: str) -> bool:
    """Return True when `path` exists on disk and has the world-writable `S_IWOTH` bit set."""
    try:
        return bool(os.stat(path).st_mode & stat.S_IWOTH)
    except OSError:
        return False


def evaluate_sovereign_and_production_readiness(
    env: Mapping[str, str] | None = None,
    *,
    persisted_flag_overrides: Mapping[str, bool] | None = None,
) -> list[str]:
    """Evaluate sovereign air-gap and production safety invariants, returning a list of violation descriptions."""
    active_env = env if env is not None else os.environ
    errors: list[str] = []

    sovereign_mode = _truthy(active_env.get("SSRA_SOVEREIGN_MODE")) or _truthy(
        active_env.get("SOVEREIGN_MODE")
    )
    if sovereign_mode:
        for key_var in COMMERCIAL_CLOUD_KEY_ENV_VARS:
            if (active_env.get(key_var) or "").strip():
                # Log ONLY the variable name, never the secret value
                errors.append(
                    f"SOVEREIGN_MODE: commercial API key environment variable {key_var} must not be set."
                )
        if not _truthy(active_env.get("HF_HUB_OFFLINE")):
            errors.append(
                "SOVEREIGN_MODE: HF_HUB_OFFLINE must be '1' to enforce air-gapped weight loading."
            )
        for url_var in SOVEREIGN_ENDPOINT_ENV_VARS:
            raw_url = (active_env.get(url_var) or "").strip()
            if not raw_url:
                continue
            parsed = urlparse(raw_url)
            if parsed.scheme not in {"http", "https"} or not is_allowed_sovereign_host(
                parsed.hostname
            ):
                errors.append(
                    f"SOVEREIGN_MODE: {url_var} must resolve to localhost, RFC 1918 private IP, or a local Compose service."
                )

    is_prod = (
        active_env.get("SSRA_ENV") or active_env.get("APP_ENV") or "development"
    ).strip().lower() == "production"
    if is_prod:
        for sec_var in (
            "SSRA_CONFIRM_HMAC_SECRET",
            "SSRA_FLAG_HMAC_SECRET",
            "SSRA_TOKEN_EXCHANGE_SECRET",
        ):
            val = (active_env.get(sec_var) or "").strip()
            if not val or val in _INSECURE_DEFAULT_SECRETS or len(val) < 16:
                errors.append(
                    f"PRODUCTION_SAFETY: {sec_var} must be set to a strong (>= 16 char) non-default secret in production."
                )
        if _truthy(active_env.get("LLM_TRUST_REMOTE_CODE")):
            errors.append(
                "PRODUCTION_SAFETY: LLM_TRUST_REMOTE_CODE=true is prohibited in production (OWASP LLM03)."
            )
        if _truthy(active_env.get("STORE_RAW_PROMPTS")):
            errors.append(
                "PRODUCTION_SAFETY: STORE_RAW_PROMPTS=true violates data minimisation in production."
            )
        for dir_var in ("SSRA_AUDIT_DIR", "SSRA_DATA_DIR"):
            dir_path = (active_env.get(dir_var) or "").strip()
            if dir_path and _is_world_writable(dir_path):
                errors.append(
                    f"PRODUCTION_SAFETY: {dir_var} points to a world-writable directory; restrict permissions to 0750/0700."
                )
        if persisted_flag_overrides:
            disabled_protected = sorted(
                name
                for name, enabled in persisted_flag_overrides.items()
                if name in PROTECTED_SECURITY_FLAGS and not enabled
            )
            if disabled_protected:
                errors.append(
                    "PRODUCTION_SAFETY: persisted flag override(s) attempt to disable protected security control(s): "
                    + ", ".join(disabled_protected)
                )

    return errors


def assert_sovereign_and_production_readiness(
    env: Mapping[str, str] | None = None,
    *,
    persisted_flag_overrides: Mapping[str, bool] | None = None,
) -> None:
    """Raise `SSRAError` (`503 UPSTREAM_UNAVAILABLE`) when any sovereign or production safety invariant fails."""
    errors = evaluate_sovereign_and_production_readiness(
        env, persisted_flag_overrides=persisted_flag_overrides
    )
    if errors:
        raise SSRAError(
            McpErrorCode.UPSTREAM_UNAVAILABLE,
            "Sovereign / Production Safety Gate failed: " + "; ".join(errors),
            status_code=503,
        )
