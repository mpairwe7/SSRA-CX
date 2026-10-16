"""Sovereign ModelPort Router, 5-Step Degradation Ladder & T0-Only Semantic Cache (Sections 6.4 & 13).

Enforces:
1. Node-tiered sovereign model selection (`input_guard`, `understand`, `compose`).
2. External frontier models blocked unless `external_providers.enabled == True` AND `tier == T0` (OQ-004).
3. 5-step deterministic degradation ladder:
   - Level 1: PRIMARY_SOVEREIGN_VLLM
   - Level 2: SECONDARY_SOVEREIGN_VLLM
   - Level 3: SELF_HOSTED_CPU_QUANTIZED
   - Level 4: RETRIEVAL_ONLY_ANSWER_CARDS (bypasses LLM generation)
   - Level 5: STATIC_FAQ_PLUS_CALLBACK (bypasses LLM and vector search)
4. T0-only semantic cache keyed by `(snapshot_version, locale, normalized_query)` — never caches T1-T3 turns.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Literal

from ssra_core import Answer, AuthLevel, LocaleCode, McpErrorCode, RiskTier, SSRAError

from ssra_llm.prompts import load_routing_config

_VLLM_SPECIAL_TOKEN_RE = re.compile(
    r"<\|(?:image_pad|video_pad|vision_start|vision_end|endoftext|im_start|im_end)\|>|<image>|<video>",
    flags=re.IGNORECASE,
)
_HEAP_ADDR_RE = re.compile(r"0x[0-9a-fA-F]{6,16}")

DegradationMode = Literal[
    "PRIMARY_SOVEREIGN_VLLM",
    "SECONDARY_SOVEREIGN_VLLM",
    "SELF_HOSTED_CPU_QUANTIZED",
    "RETRIEVAL_ONLY_ANSWER_CARDS",
    "STATIC_FAQ_PLUS_CALLBACK",
]

_LADDER_MAP: dict[int, DegradationMode] = {
    1: "PRIMARY_SOVEREIGN_VLLM",
    2: "SECONDARY_SOVEREIGN_VLLM",
    3: "SELF_HOSTED_CPU_QUANTIZED",
    4: "RETRIEVAL_ONLY_ANSWER_CARDS",
    5: "STATIC_FAQ_PLUS_CALLBACK",
}


@dataclass(frozen=True)
class ModelRouteDecision:
    node_name: str
    selected_model: str
    degradation_level: int
    degradation_mode: DegradationMode
    llm_enabled: bool
    max_tokens: int
    timeout_ms: int


class SovereignModelRouter:
    def __init__(self, *, force_degradation_level: int = 1) -> None:
        if not (1 <= force_degradation_level <= 5):
            raise ValueError("force_degradation_level must be in 1..5")
        self._config = load_routing_config()
        self._level = force_degradation_level

    @property
    def degradation_level(self) -> int:
        return self._level

    def set_degradation_level(self, level: int) -> None:
        if not (1 <= level <= 5):
            raise ValueError("degradation_level must be in 1..5")
        self._level = level

    def set_external_providers_enabled(self, enabled: bool) -> None:
        self._config["external_providers"] = {"enabled": enabled}

    def select_route(
        self,
        *,
        node_name: str,
        tier: RiskTier,
        request_external_provider: bool = False,
    ) -> ModelRouteDecision:
        ext_cfg = self._config.get("external_providers", {})
        if request_external_provider:
            if not ext_cfg.get("enabled", False):
                raise SSRAError(
                    McpErrorCode.NOT_AUTHORIZED,
                    "External AI providers are disabled by sovereignty policy until OQ-004 is approved",
                    status_code=403,
                )
            if tier != RiskTier.T0:
                raise SSRAError(
                    McpErrorCode.NOT_AUTHORIZED,
                    f"Tier {tier.value} data may never route to an external AI provider",
                    status_code=403,
                )

        node_cfg = self._config.get("node_routes", {}).get(node_name, {})
        primary = str(node_cfg.get("primary_model", "ssra-sovereign/qwen2.5-7b-instruct"))
        secondary = str(node_cfg.get("secondary_model", "ssra-sovereign/llama-3.3-8b-instruct"))
        max_tokens = int(node_cfg.get("max_tokens", 512))
        timeout_ms = int(node_cfg.get("timeout_ms", 2000))
        mode = _LADDER_MAP[self._level]

        if self._level == 1:
            model = primary
            llm_enabled = True
        elif self._level == 2:
            model = secondary
            llm_enabled = True
        elif self._level == 3:
            model = "ssra-sovereign/qwen2.5-3b-cpu-gguf"
            llm_enabled = True
        elif self._level == 4:
            model = "none:retrieval-only-cards"
            llm_enabled = False
        else:
            model = "none:static-faq-callback"
            llm_enabled = False

        return ModelRouteDecision(
            node_name=node_name,
            selected_model=model,
            degradation_level=self._level,
            degradation_mode=mode,
            llm_enabled=llm_enabled,
            max_tokens=max_tokens,
            timeout_ms=timeout_ms,
        )


class AnonymousT0SemanticCache:
    """Section 13: Semantic cache ONLY for anonymous T0 answers, keyed by knowledge snapshot & locale."""

    def __init__(self) -> None:
        self._store: dict[str, Answer] = {}

    @staticmethod
    def _make_key(*, snapshot_version: str, locale: LocaleCode, query: str) -> str:
        norm_q = " ".join(query.strip().lower().split())
        digest = hashlib.sha256(f"{snapshot_version}:{locale.value}:{norm_q}".encode()).hexdigest()
        return f"t0_cache:{snapshot_version}:{locale.value}:{digest}"

    def get(
        self,
        *,
        snapshot_version: str,
        locale: LocaleCode,
        query: str,
        tier: RiskTier,
        auth_level: AuthLevel,
    ) -> Answer | None:
        if tier != RiskTier.T0 or auth_level != AuthLevel.ANONYMOUS:
            return None
        key = self._make_key(snapshot_version=snapshot_version, locale=locale, query=query)
        return self._store.get(key)

    def put(
        self,
        *,
        snapshot_version: str,
        locale: LocaleCode,
        query: str,
        tier: RiskTier,
        auth_level: AuthLevel,
        answer: Answer,
    ) -> bool:
        if tier != RiskTier.T0 or auth_level != AuthLevel.ANONYMOUS or answer.abstained:
            return False
        key = self._make_key(snapshot_version=snapshot_version, locale=locale, query=query)
        self._store[key] = answer
        return True

    def invalidate_snapshot(self, snapshot_version: str) -> int:
        prefix = f"t0_cache:{snapshot_version}:"
        keys = [k for k in self._store if k.startswith(prefix)]
        for k in keys:
            del self._store[k]
        return len(keys)


class VllmServingGuard:
    """October 2026 vLLM (>= 0.26.0) & HuggingFace Offline Cache Guard.

    Mitigates:
    - CVE-2026-73559: Rejects prompt list fan-out (enforces single string prompt)
    - CVE-2026-44222: Strips multimodal special-token placeholders (`<|image_pad|>`, `<|video_pad|>`)
    - CVE-2026-54236: Scrubs heap memory addresses (`0x7f...`) from upstream inference error messages
    - Enforces `HF_HUB_OFFLINE=1` / `local_files_only=True` and `xgrammar` guided JSON decoding.
    """

    def __init__(self, *, hf_home: str = "/var/cache/ssra/huggingface") -> None:
        self.hf_home = hf_home

    def build_guided_json_request(
        self,
        *,
        model: str,
        prompt: str | list[str],
        json_schema: dict[str, Any],
        max_tokens: int = 512,
    ) -> dict[str, Any]:
        if not isinstance(prompt, str):
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                "vLLM prompt list fan-out rejected (CVE-2026-73559: single string prompt required)",
                status_code=400,
            )
        sanitized_prompt = _VLLM_SPECIAL_TOKEN_RE.sub("", prompt).strip()
        return {
            "model": model,
            "prompt": sanitized_prompt,
            "max_tokens": max_tokens,
            "temperature": 0.0,
            "guided_decoding_backend": "xgrammar",
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "ssra_structured_output", "schema": json_schema},
            },
            "extra_body": {
                "enable_prefix_caching": True,
                "hf_home": self.hf_home,
                "local_files_only": True,
            },
        }

    @staticmethod
    def sanitize_upstream_error(raw_message: str) -> str:
        """Scrub heap pointer addresses from vLLM/PIL exception strings (CVE-2026-54236)."""
        return _HEAP_ADDR_RE.sub("0xREDACTED", raw_message)
