"""Deterministic Cohort & Percentage Feature-Flag Engine (`flags.py` — SSRA Assist October 2026).

Supports:
1. Percentage rollouts (`0..100`) using deterministic HMAC-SHA256 bucketing on `(flag_name, subject_ref)`.
2. Cohort filtering by SSRA `channel` (`web`, `whatsapp`, `sms`, `ussd`, `voice`, `console`) and
   SSRA BCP-47 `locale` (`en`, `pga`, `ar`, `din`, `nus`, `bfa`, `zne`, `shk`).
3. Shared runtime override state across API and runtime workers with `reset_flag_override` to restore YAML defaults.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_FLAGS_FILE = Path(__file__).resolve().parents[4] / "ai" / "policies" / "feature-flags.yaml"
_DEFAULT_SHARED_OVERRIDE_PATH = Path(
    os.environ.get(
        "SSRA_FEATURE_FLAGS_OVERRIDE_FILE",
        str(Path(tempfile.gettempdir()) / "ssra_feature_flag_overrides.json"),
    )
)

KNOWN_FEATURE_FLAGS: tuple[str, ...] = (
    "FF_AUTONOMOUS_GOAL_PLANNER",
    "FF_COGNITIVE_MEMORY_4TIER",
    "FF_REALTIME_EQ_TONE_AND_ESCALATION",
    "FF_ENGLISH_ROUTER_CANONICAL",
    "FF_HANDOFF_ENVELOPE_V2_AND_WARM_RETURN",
    "FF_TEMPORAL_POST_INTERACTION_CONTINUATION",
    "FF_HYBRID_VOICE_FAST_ACK_AND_SEMANTIC_EOT",
    "FF_VOICE_TO_SMS_CONTINUATION",
    "FF_OFFLINE_PWA_CALCULATORS_AND_EDGE_PACK",
    "FLAG_HYBRID_SPEECH_S2S",
    "FLAG_EMOTION_AWARE_PROSODY",
    "FLAG_CONTINUOUS_RELATIONSHIP_MEMORY",
    "FLAG_SPOKEN_FIGURE_GUARD",
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
    """Immutable configuration rule for a single cohort/percentage feature flag."""

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
    """Result of evaluating a feature flag for a specific `(subject_ref, channel, locale)` tuple."""

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
        shared_override_path: Path | None = None,
    ) -> None:
        """Initialize the feature-flag engine from the validated YAML registry and shared override store."""
        path = config_path or _DEFAULT_FLAGS_FILE
        if not path.is_file():
            raise FileNotFoundError(f"Feature flag configuration file not found: {path}")
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict) or not isinstance(loaded.get("flags"), dict):
            raise ValueError(
                f"Malformed feature flag configuration in {path}: root and 'flags' must be mappings"
            )
        raw: dict[str, Any] = loaded
        self.config_path: Path = path
        self.shared_override_path: Path = shared_override_path or _DEFAULT_SHARED_OVERRIDE_PATH
        self.version: str = str(raw.get("version", "2026.10.2"))
        self.salt: str = salt or str(raw.get("default_salt", "ssra-sovereign-flag-salt-2026-10"))
        self._base_rules: dict[str, FeatureFlagRule] = {}
        self._overrides: dict[str, FeatureFlagRule] = {}

        flags_cfg: dict[str, Any] = raw["flags"]
        for f_name, f_data in flags_cfg.items():
            if not isinstance(f_data, dict):
                raise ValueError(f"Flag entry '{f_name}' in {path} must be a mapping")
            pct = max(0, min(100, int(f_data.get("rollout_pct", 100))))
            chans = tuple(str(c).lower() for c in f_data.get("allowed_channels", ()))
            locs = tuple(str(loc).lower() for loc in f_data.get("allowed_locales", ()))
            rule = FeatureFlagRule(
                name=str(f_name),
                description=str(f_data.get("description", "")),
                enabled=bool(f_data.get("enabled", True)),
                rollout_pct=pct,
                allowed_channels=chans or ("web", "whatsapp", "sms", "ussd", "voice", "console"),
                allowed_locales=locs or SSRA_SUPPORTED_LOCALES,
            )
            self._base_rules[str(f_name)] = rule

    def _sync_shared_overrides_from_disk(self) -> None:
        """Load HMAC-verified shared runtime overrides written by Admin control-plane processes if present."""
        if not self.shared_override_path.is_file():
            return
        envelope = json.loads(self.shared_override_path.read_text(encoding="utf-8"))
        data = envelope.get("overrides", {})
        sig = str(envelope.get("hmac_sha256", ""))
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        expected = hmac.new(self.salt.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            self._overrides.clear()
            return
        synced: dict[str, FeatureFlagRule] = {}
        for k, v in data.items():
            if isinstance(v, dict):
                synced[str(k)] = FeatureFlagRule(
                    name=str(v.get("name", k)),
                    description=str(v.get("description", "")),
                    enabled=bool(v.get("enabled", True)),
                    rollout_pct=max(0, min(100, int(v.get("rollout_pct", 100)))),
                    allowed_channels=tuple(str(c) for c in v.get("allowed_channels", ("web",))),
                    allowed_locales=tuple(
                        str(loc) for loc in v.get("allowed_locales", SSRA_SUPPORTED_LOCALES)
                    ),
                )
        self._overrides = synced

    def _persist_shared_overrides_to_disk(self) -> None:
        """Atomically persist HMAC-signed runtime overrides (`0o600` + `os.replace`) across local workers."""
        self.shared_override_path.parent.mkdir(parents=True, exist_ok=True)
        overrides_dict = {k: asdict(v) for k, v in self._overrides.items()}
        canonical = json.dumps(overrides_dict, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        sig = hmac.new(self.salt.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
        envelope = {"overrides": overrides_dict, "hmac_sha256": sig}
        tmp_path = self.shared_override_path.with_name(
            f".{self.shared_override_path.name}.{os.getpid()}.tmp"
        )
        tmp_path.write_text(json.dumps(envelope, sort_keys=True), encoding="utf-8")
        tmp_path.chmod(0o600)
        os.replace(tmp_path, self.shared_override_path)

    def _effective_rules(self) -> dict[str, FeatureFlagRule]:
        """Return base YAML rules merged with any active runtime overrides."""
        self._sync_shared_overrides_from_disk()
        return {**self._base_rules, **self._overrides}

    def list_rules(self) -> list[FeatureFlagRule]:
        """Return all registered feature-flag rules sorted by flag name."""
        merged = self._effective_rules()
        return [merged[k] for k in sorted(merged)]

    def get_rule(self, flag_name: str) -> FeatureFlagRule | None:
        """Look up a single feature-flag rule by name."""
        return self._effective_rules().get(flag_name)

    def set_flag_override(
        self,
        flag_name: str,
        *,
        enabled: bool,
        rollout_pct: int = 100,
        allowed_channels: list[str] | tuple[str, ...] | None = None,
        allowed_locales: list[str] | tuple[str, ...] | None = None,
    ) -> FeatureFlagRule:
        """Update or register a feature-flag state at runtime and persist across local workers."""
        self._sync_shared_overrides_from_disk()
        bounded_pct = max(0, min(100, int(rollout_pct)))
        existing = self._overrides.get(flag_name) or self._base_rules.get(flag_name)
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
        self._overrides[flag_name] = rule
        self._persist_shared_overrides_to_disk()
        return rule

    def reset_flag_override(self, flag_name: str | None = None) -> None:
        """Clear a runtime override (or all overrides when `flag_name` is None) to restore YAML defaults."""
        self._sync_shared_overrides_from_disk()
        if flag_name is None:
            self._overrides.clear()
        else:
            self._overrides.pop(flag_name, None)
        self._persist_shared_overrides_to_disk()

    def evaluate(
        self,
        flag_name: str,
        *,
        subject_ref: str = "anonymous_default",
        channel: str = "web",
        locale: str = "en",
    ) -> FeatureFlagEvaluation:
        """Deterministically evaluate whether `flag_name` is active for `(subject_ref, channel, locale)`."""
        rule = self._effective_rules().get(flag_name)
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
    """Return the process-wide default `FeatureFlagEngine` instance."""
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
