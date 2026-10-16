"""Provider-agnostic ModelPort, L0-L5 spotlighted prompt builder, and termbase loader (Section 6.3, 6.4, 7)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict
from ssra_core import ChannelCapabilities, LocaleCode

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PROMPTS_FILE = _REPO_ROOT / "ai" / "prompts" / "registry.yaml"
_TERMBASE_FILE = _REPO_ROOT / "ai" / "termbase" / "glossary.yaml"
_ROUTING_FILE = _REPO_ROOT / "ai" / "routing" / "model-routing.yaml"


class LayeredPromptEnvelope(BaseModel):
    """L0-L5 Context Engineering Envelope (Section 6.3) with data-only spotlighting delimiters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt_id: str
    prompt_version: str
    system_instructions: str
    spotlighted_data_block: str


class PromptRegistry:
    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw = raw
        self.version: str = str(raw.get("version", "2026.10.1"))

    @classmethod
    def load_default(cls) -> PromptRegistry:
        data = yaml.safe_load(_PROMPTS_FILE.read_text(encoding="utf-8"))
        return cls(data)

    def build_layered_prompt(
        self,
        *,
        prompt_id: str,
        locale: LocaleCode,
        capabilities: ChannelCapabilities,
        user_input_redacted: str,
        retrieved_evidence: list[dict[str, Any]],
        tool_artifacts: list[dict[str, Any]],
    ) -> LayeredPromptEnvelope:
        layers = self._raw.get("layers", {})
        prompts = self._raw.get("prompts", {})
        spec = prompts.get(prompt_id, {})
        prompt_version = str(spec.get("version", "1.0.0"))

        l0 = str(layers.get("L0_immutable_policy", "")).strip()
        l1 = (
            f"[L1 CHANNEL CONTRACT]\n"
            f"locale={locale.value} max_len={capabilities.max_len} "
            f"rich_ui={capabilities.rich_ui} buttons={capabilities.buttons}"
        )
        l2 = str(layers.get("L2_persona_and_tone", "")).strip()
        l3 = str(spec.get("task_instruction", "")).strip()

        # L4 & L5 wrapped strictly inside untrusted data-only delimiters (Principle 5)
        l4_json = json.dumps(retrieved_evidence, ensure_ascii=False, sort_keys=True)
        l5_json = json.dumps(tool_artifacts, ensure_ascii=False, sort_keys=True)

        spotlighted_data = (
            f"<untrusted_user_input>\n{user_input_redacted}\n</untrusted_user_input>\n"
            f"<untrusted_retrieved_evidence>\n{l4_json}\n</untrusted_retrieved_evidence>\n"
            f"<untrusted_tool_artifacts>\n{l5_json}\n</untrusted_tool_artifacts>"
        )

        return LayeredPromptEnvelope(
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            system_instructions="\n\n".join([l0, l1, l2, l3]),
            spotlighted_data_block=spotlighted_data,
        )


def load_termbase() -> dict[str, Any]:
    return dict(yaml.safe_load(_TERMBASE_FILE.read_text(encoding="utf-8")))


def load_routing_config() -> dict[str, Any]:
    return dict(yaml.safe_load(_ROUTING_FILE.read_text(encoding="utf-8")))
