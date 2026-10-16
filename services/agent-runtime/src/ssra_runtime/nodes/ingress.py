"""Node 1: ingress — normalise event, attach channel capabilities, initialise turn state."""

from __future__ import annotations

from typing import Any

from ssra_runtime.schemas import TurnBudget
from ssra_runtime.state import ConversationGraphState


def ingress_node(state: ConversationGraphState) -> dict[str, Any]:
    raw_text = state.get("raw_user_text", "").strip()
    return {
        "raw_user_text": raw_text,
        "deterministic_handled": False,
        "artifacts": list(state.get("artifacts", [])),
        "citations": list(state.get("citations", [])),
        "safety_flags": list(state.get("safety_flags", [])),
        "budget": state.get("budget", TurnBudget()),
        "regeneration_count": 0,
    }
