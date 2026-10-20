"""Synthetic test factories for SSRA Assist (Section 16 & 19)."""

from __future__ import annotations

from ssra_core import (
    ChannelCapabilities,
    ChannelName,
    ContentPart,
    ConversationEvent,
    ConversationEventData,
    LocaleCode,
    new_id,
    utc_now,
)


def make_conversation_event(
    text: str,
    *,
    locale: LocaleCode = LocaleCode.EN,
    channel: ChannelName = ChannelName.WEB,
    thread_id: str | None = None,
    max_len: int = 4096,
    rich_ui: bool = True,
    metadata: dict[str, str] | None = None,
) -> ConversationEvent:
    source_map = {
        ChannelName.WEB: "urn:ssra:channel:web",
        ChannelName.WHATSAPP: "urn:ssra:channel:whatsapp",
        ChannelName.SMS: "urn:ssra:channel:sms",
        ChannelName.USSD: "urn:ssra:channel:ussd",
        ChannelName.VOICE: "urn:ssra:channel:voice",
        ChannelName.CONSOLE: "urn:ssra:channel:console",
    }
    return ConversationEvent(
        id=new_id("evt"),
        source=source_map[channel],  # type: ignore[arg-type]
        type="ssra.conversation.message.v1",
        subject=thread_id or new_id("thr"),
        time=utc_now(),
        data=ConversationEventData(
            locale=locale,
            channel=channel,
            parts=[ContentPart(kind="text", value=text)],
            capabilities=ChannelCapabilities(
                max_len=max_len,
                rich_ui=rich_ui,
                buttons=channel in (ChannelName.WEB, ChannelName.WHATSAPP, ChannelName.CONSOLE),
                media=channel in (ChannelName.WEB, ChannelName.WHATSAPP, ChannelName.CONSOLE),
                latency_budget_ms=2000 if channel == ChannelName.USSD else 6000,
                async_only=channel == ChannelName.SMS,
            ),
            metadata=dict(metadata or {}),
        ),
    )
