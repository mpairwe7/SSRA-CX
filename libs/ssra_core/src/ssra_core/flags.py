"""Deterministic Cohort & Percentage Feature-Flag Engine (`flags.py` — SSRA Assist October 2026).

Supports:
1. Percentage rollouts (`0..100`) using deterministic HMAC-SHA256 bucketing on `(flag_name, subject_key)`.
2. Cohort filtering by SSRA `channel` (`web`, `whatsapp`, `sms`, `ussd`, `voice`, `console`) and
   SSRA BCP-47 `locale` (`en`, `pga`, `ar`, `din`, `nus`, `bfa`, `zne`, `shk`).
3. Live SecOps / Admin overrides without service restarts (`set_flag_override`).
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_FLAGS_FILE = Path(__file__).resolve().parents[4] / "ai" / "policies" / "feature-flags.yaml"

KNOWN_FEATURE_FLAGS: tuple[str, ...] = (
    "FF_AUTONOMOUS_GOAL_PLANNER",
    "FF_COGNITIVE_MEMORY_4TIER",
    "FF_REALTIME_EQ_TONE_AND_ESCALATION",
    "FF_ENGLISH_ROUTER_CANONICAL",
    "FF_HANDOFF_ENVELOPE_V2_AND_WARM_RETURN",
    "FF_TEMPORAL_POST_INTERACTION_CONTINUATION",
)

SSRA_SUPPORTED_LOCALES: tuple[str, ...] = (
    "en",
    "pga",
    "ar",
    "din",
    "nus",
    "bfa",
    "zne",
    "shk",
)


@dataclass(frozen=True)
class FeatureFlagRule:
    name: str
    description: str
    enabled: bool = True
    rollout_pct: int = 100
    allowed_channels: tuple[str, ...] = field(
        default_factory=lambda: ("web", "whatsapp", "sms", "ussd", "voice", "console")
    )
    allowed_locales: tuple[str, ...] = field(default_factory=lambda: SSRA_SUPPORTED_LOCALES)


@dataclass(frozen=True)
class FeatureFlagEvaluation:
    flag_name: str
    active: bool
    bucket: int
    rollout_pct: int
    reason: str


def compute_deterministic_flag_bucket(
    flag_name: str,
    subject_ref: str,
    *,
    salt: str = "ssra-sovereign-flag-salt-2026-10",
) -> int:
    """Compute a deterministic integer bucket in `0..99` via HMAC-SHA256."""
    clean_subject = subject_ref.strip() or "anonymous_default"
    msg = f"{flag_name}:{clean_subject}".encode()
    digest = hmac.new(salt.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return int(digest[:8], 16) % 100


class FeatureFlagEngine:
    """Deterministic cohort and percentage feature-flag evaluator for SSRA Assist."""

    def __init__(
        self,
        *,
        config_path: Path | None = None,
        salt: str | None = None,
    ) -> None:
        path = config_path or _DEFAULT_FLAGS_FILE
        raw: dict[str, Any] = {}
        if path.is_file():
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                raw = loaded
        self.version: str = str(raw.get("version", "2026.10.2"))
        self.salt: str = salt or str(raw.get("default_salt", "ssra-sovereign-flag-salt-2026-10"))
        self._rules: dict[str, FeatureFlagRule] = {}

        flags_cfg = raw.get("flags", {})
        if isinstance(flags_cfg, dict):
            for f_name, f_data in flags_cfg.items():
                if not isinstance(f_data, dict):
                    continue
                pct = max(0, min(100, int(f_data.get("rollout_pct", 100))))
                chans = tuple(str(c).lower() for c in f_data.get("allowed_channels", ()))
                locs = tuple(str(loc).lower() for loc in f_data.get("allowed_locales", ()))
                self._rules[str(f_name)] = FeatureFlagRule(
                    name=str(f_name),
                    description=str(f_data.get("description", "")),
                    enabled=bool(f_data.get("enabled", True)),
                    rollout_pct=pct,
                    allowed_channels=chans
                    or ("web", "whatsapp", "sms", "ussd", "voice", "console"),
                    allowed_locales=locs or SSRA_SUPPORTED_LOCALES,
                )

        for known in KNOWN_FEATURE_FLAGS:
            if known not in self._rules:
                self._rules[known] = FeatureFlagRule(
                    name=known,
                    description=f"Default rule for {known}",
                    enabled=True,
                    rollout_pct=100,
                )

    def list_rules(self) -> list[FeatureFlagRule]:
        return [self._rules[k] for k in sorted(self._rules)]

    def get_rule(self, flag_name: str) -> FeatureFlagRule | None:
        return self._rules.get(flag_name)

    def set_flag_override(
        self,
        flag_name: str,
        *,
        enabled: bool,
        rollout_pct: int = 100,
        allowed_channels: list[str] | tuple[str, ...] | None = None,
        allowed_locales: list[str] | tuple[str, ...] | None = None,
    ) -> FeatureFlagRule:
        """Update or register a feature-flag state at runtime (used by SSRA Admin control plane)."""
        bounded_pct = max(0, min(100, int(rollout_pct)))
        existing = self._rules.get(flag_name)
        desc = existing.description if existing else f"Runtime override for {flag_name}"
        chans = (
            tuple(str(c).lower() for c in allowed_channels)
            if allowed_channels is not None
            else (
                existing.allowed_channels
                if existing
                else ("web", "whatsapp", "sms", "ussd", "voice", "console")
            )
        )
        locs = (
            tuple(str(loc).lower() for loc in allowed_locales)
            if allowed_locales is not None
            else (existing.allowed_locales if existing else SSRA_SUPPORTED_LOCALES)
        )
        rule = FeatureFlagRule(
            name=flag_name,
            description=desc,
            enabled=bool(enabled),
            rollout_pct=bounded_pct,
            allowed_channels=chans,
            allowed_locales=locs,
        )
        self._rules[flag_name] = rule
        return rule

    def evaluate(
        self,
        flag_name: str,
        *,
        subject_ref: str = "anonymous_default",
        channel: str = "web",
        locale: str = "en",
    ) -> FeatureFlagEvaluation:
        """Deterministically evaluate whether `flag_name` is active for `(subject_ref, channel, locale)`."""
        rule = self._rules.get(flag_name)
        bucket = compute_deterministic_flag_bucket(flag_name, subject_ref, salt=self.salt)
        if rule is None:
            return FeatureFlagEvaluation(
                flag_name=flag_name,
                active=False,
                bucket=bucket,
                rollout_pct=0,
                reason="FLAG_NOT_REGISTERED",
            )
        if not rule.enabled or rule.rollout_pct <= 0:
            return FeatureFlagEvaluation(
                flag_name=flag_name,
                active=False,
                bucket=bucket,
                rollout_pct=rule.rollout_pct,
                reason="FLAG_DISABLED",
            )
        norm_channel = str(channel).strip().lower()
        if rule.allowed_channels and norm_channel not in rule.allowed_channels:
            return FeatureFlagEvaluation(
                flag_name=flag_name,
                active=False,
                bucket=bucket,
                rollout_pct=rule.rollout_pct,
                reason=f"CHANNEL_EXCLUDED:{norm_channel}",
            )
        norm_locale = str(locale).strip().lower()
        if rule.allowed_locales and norm_locale not in rule.allowed_locales:
            return FeatureFlagEvaluation(
                flag_name=flag_name,
                active=False,
                bucket=bucket,
                rollout_pct=rule.rollout_pct,
                reason=f"LOCALE_EXCLUDED:{norm_locale}",
            )
        if rule.rollout_pct >= 100:
            return FeatureFlagEvaluation(
                flag_name=flag_name,
                active=True,
                bucket=bucket,
                rollout_pct=100,
                reason="FULL_ROLLOUT",
            )
        active = bucket < rule.rollout_pct
        return FeatureFlagEvaluation(
            flag_name=flag_name,
            active=active,
            bucket=bucket,
            rollout_pct=rule.rollout_pct,
            reason="COHORT_INCLUDED" if active else "COHORT_BUCKET_OUTSIDE_PCT",
        )


_DEFAULT_ENGINE = FeatureFlagEngine()


def get_default_feature_flag_engine() -> FeatureFlagEngine:
    return _DEFAULT_ENGINE


def evaluate_flag(
    flag_name: str,
    *,
    subject_ref: str = "anonymous_default",
    channel: str = "web",
    locale: str = "en",
) -> bool:
    """Convenience helper returning boolean flag activation from the default engine."""
    return _DEFAULT_ENGINE.evaluate(
        flag_name,
        subject_ref=subject_ref,
        channel=channel,
        locale=locale,
    ).active
