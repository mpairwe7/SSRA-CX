"""Unified `ChannelPort` Protocol and All 6 Channel Adapters (Section 11).

"Every channel implements one `ChannelPort` with capability flags, so the runtime fits each
answer to `max_len`, `rich_ui`, `buttons`, `media`, `latency_budget_ms` and `async_only`."
"""

from __future__ import annotations

from typing import Any, Protocol

from ssra_core import Answer, ChannelCapabilities, ChannelName

from ssra_channel_gateway.main import compute_sms_segments
from ssra_channel_gateway.ussd import USSD_MAX_CHARS
from ssra_channel_gateway.whatsapp import ANTI_IMPERSONATION_VERIFICATION_FOOTER


class ChannelPort(Protocol):
    @property
    def channel(self) -> ChannelName: ...

    @property
    def capabilities(self) -> ChannelCapabilities: ...

    def format_outbound(self, answer: Answer) -> dict[str, Any]: ...


class WebPwaChannelAdapter:
    channel = ChannelName.WEB
    capabilities = ChannelCapabilities(
        max_len=4096,
        rich_ui=True,
        buttons=True,
        media=True,
        latency_budget_ms=6000,
        async_only=False,
    )

    def format_outbound(self, answer: Answer) -> dict[str, Any]:
        text = " ".join(s.text for s in answer.segments)[: self.capabilities.max_len]
        return {
            "channel": self.channel.value,
            "transport": "ag-ui-sse",
            "text": text,
            "citations": [c.model_dump(mode="json") for c in answer.citations],
            "ui_component": answer.ui_component.model_dump(mode="json")
            if answer.ui_component
            else None,
        }


class WhatsAppChannelAdapter:
    channel = ChannelName.WHATSAPP
    capabilities = ChannelCapabilities(
        max_len=4096,
        rich_ui=False,
        buttons=True,
        media=True,
        latency_budget_ms=10000,
        async_only=False,
    )

    def format_outbound(self, answer: Answer) -> dict[str, Any]:
        raw = " ".join(s.text for s in answer.segments)
        with_footer = f"{raw}{ANTI_IMPERSONATION_VERIFICATION_FOOTER}"[: self.capabilities.max_len]
        return {
            "channel": self.channel.value,
            "transport": "whatsapp-interactive",
            "text": with_footer,
            "buttons_enabled": self.capabilities.buttons,
        }


class SmsChannelAdapter:
    channel = ChannelName.SMS
    capabilities = ChannelCapabilities(
        max_len=160,
        rich_ui=False,
        buttons=False,
        media=False,
        latency_budget_ms=10000,
        async_only=True,
    )

    def format_outbound(self, answer: Answer) -> dict[str, Any]:
        raw = " ".join(s.text for s in answer.segments)[: self.capabilities.max_len]
        return {
            "channel": self.channel.value,
            "transport": "smpp-http",
            "text": raw,
            "sms_metrics": compute_sms_segments(raw),
        }


class StaffConsoleChannelAdapter:
    channel = ChannelName.CONSOLE
    capabilities = ChannelCapabilities(
        max_len=8192,
        rich_ui=True,
        buttons=True,
        media=True,
        latency_budget_ms=6000,
        async_only=False,
    )

    def format_outbound(self, answer: Answer) -> dict[str, Any]:
        text = " ".join(s.text for s in answer.segments)[: self.capabilities.max_len]
        return {
            "channel": self.channel.value,
            "transport": "console-inbox-sse",
            "text": text,
            "citations": [c.model_dump(mode="json") for c in answer.citations],
        }


class UssdChannelAdapter:
    channel = ChannelName.USSD
    capabilities = ChannelCapabilities(
        max_len=USSD_MAX_CHARS,
        rich_ui=False,
        buttons=False,
        media=False,
        latency_budget_ms=2000,
        async_only=False,
    )

    def format_outbound(self, answer: Answer) -> dict[str, Any]:
        text = " ".join(s.text for s in answer.segments)[:USSD_MAX_CHARS]
        return {
            "channel": self.channel.value,
            "transport": "ussd-sync",
            "text": text,
            "char_length": len(text),
        }


class VoiceIvrChannelAdapter:
    channel = ChannelName.VOICE
    capabilities = ChannelCapabilities(
        max_len=1000,
        rich_ui=False,
        buttons=False,
        media=True,
        latency_budget_ms=1000,
        async_only=False,
    )

    def format_outbound(self, answer: Answer) -> dict[str, Any]:
        spoken = " ".join(s.text for s in answer.segments)[: self.capabilities.max_len]
        return {
            "channel": self.channel.value,
            "transport": "sip-rtp-tts",
            "ssml_or_text": spoken,
        }


CHANNEL_PORT_REGISTRY: dict[ChannelName, ChannelPort] = {
    ChannelName.WEB: WebPwaChannelAdapter(),
    ChannelName.WHATSAPP: WhatsAppChannelAdapter(),
    ChannelName.SMS: SmsChannelAdapter(),
    ChannelName.CONSOLE: StaffConsoleChannelAdapter(),
    ChannelName.USSD: UssdChannelAdapter(),
    ChannelName.VOICE: VoiceIvrChannelAdapter(),
}


def get_channel_port(channel: ChannelName) -> ChannelPort:
    return CHANNEL_PORT_REGISTRY[channel]
