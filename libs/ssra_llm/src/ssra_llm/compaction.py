"""Token Budget Enforcement, Static Prefix Cache Keying & Running-Summary Context Compaction (Section 6.3 & 13)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from ssra_llm.prompts import LayeredPromptEnvelope


@dataclass(frozen=True)
class CompactedPromptContext:
    static_prefix_hash: str
    compacted_running_summary: str
    estimated_input_tokens: int
    within_node_budget: bool


def estimate_token_count(text: str) -> int:
    """Conservative token estimator (~4 chars per token across Latin and Arabic scripts)."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def compact_context_for_node(
    envelope: LayeredPromptEnvelope,
    *,
    running_summary: str,
    node_token_budget: int = 2048,
) -> CompactedPromptContext:
    static_prefix_hash = hashlib.sha256(envelope.system_instructions.encode("utf-8")).hexdigest()
    sys_tokens = estimate_token_count(envelope.system_instructions)
    data_tokens = estimate_token_count(envelope.spotlighted_data_block)

    remaining_for_summary = max(64, node_token_budget - sys_tokens - data_tokens)
    max_summary_chars = remaining_for_summary * 3
    compacted_summary = (
        running_summary[-max_summary_chars:]
        if len(running_summary) > max_summary_chars
        else running_summary
    )
    total_tokens = sys_tokens + data_tokens + estimate_token_count(compacted_summary)

    return CompactedPromptContext(
        static_prefix_hash=static_prefix_hash,
        compacted_running_summary=compacted_summary,
        estimated_input_tokens=total_tokens,
        within_node_budget=total_tokens <= node_token_budget,
    )
