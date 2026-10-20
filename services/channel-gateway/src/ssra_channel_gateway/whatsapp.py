"""WhatsApp Business Platform Cloud API (2026): 24h Window, Interactive Buttons/Lists, & Template Gate (Section 11)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from ssra_core import McpErrorCode, SSRAError, utc_now

WHATSAPP_SERVICE_WINDOW_HOURS = 24
WHATSAPP_MAX_REPLY_BUTTONS = 3
WHATSAPP_MAX_BUTTON_TITLE_LEN = 20
WHATSAPP_MAX_LIST_ROWS = 10
WHATSAPP_MAX_ROW_TITLE_LEN = 24
WHATSAPP_MAX_ROW_DESC_LEN = 72

APPROVED_OUTBOUND_TEMPLATES: frozenset[str] = frozenset(
    {
        "ssra_filing_reminder_v1",
        "ssra_appointment_confirmation_v1",
        "ssra_callback_scheduled_v1",
        "ssra_case_status_update_v1",
        "TMPL_SSRA_GOAL_CONTINUATION_2026",
        "TMPL_SSRA_TCC_READY_2026",
        "TMPL_SSRA_DOCUMENT_REVIEWED_2026",
    }
)

ANTI_IMPERSONATION_VERIFICATION_FOOTER = (
    "\n---\nVerify this message: Official SSRA portal is https://etax.nra.gov.ss/. "
    "SSRA never asks for your OTP or cash payment to an individual."
)


@dataclass(frozen=True)
class WhatsAppReplyButton:
    id: str
    title: str


@dataclass(frozen=True)
class WhatsAppListRow:
    id: str
    title: str
    description: str = ""


@dataclass(frozen=True)
class WhatsAppOutboundDispatch:
    recipient_ref: str
    within_24h_window: bool
    template_id: str | None
    formatted_body: str
    estimated_cost_usd: float


def validate_whatsapp_reply_buttons(
    buttons: list[WhatsAppReplyButton],
) -> list[WhatsAppReplyButton]:
    """Validate Meta Cloud API interactive reply button constraints (1..3 buttons, title <= 20 chars)."""
    if not (1 <= len(buttons) <= WHATSAPP_MAX_REPLY_BUTTONS):
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            f"WhatsApp interactive message must have 1..{WHATSAPP_MAX_REPLY_BUTTONS} reply buttons",
            status_code=400,
        )
    seen_ids: set[str] = set()
    for btn in buttons:
        cid = btn.id.strip()
        ctitle = btn.title.strip()
        if not cid or cid in seen_ids or len(cid) > 256:
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                f"Invalid or duplicate WhatsApp button id '{btn.id}'",
                status_code=400,
            )
        if not (1 <= len(ctitle) <= WHATSAPP_MAX_BUTTON_TITLE_LEN):
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                f"WhatsApp button title '{ctitle}' must be 1..{WHATSAPP_MAX_BUTTON_TITLE_LEN} chars",
                status_code=400,
            )
        seen_ids.add(cid)
    return buttons


def validate_whatsapp_list_rows(rows: list[WhatsAppListRow]) -> list[WhatsAppListRow]:
    """Validate Meta Cloud API interactive list row constraints (1..10 rows, title <= 24 chars, desc <= 72 chars)."""
    if not (1 <= len(rows) <= WHATSAPP_MAX_LIST_ROWS):
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            f"WhatsApp list message must have 1..{WHATSAPP_MAX_LIST_ROWS} rows",
            status_code=400,
        )
    for row in rows:
        if not (1 <= len(row.title.strip()) <= WHATSAPP_MAX_ROW_TITLE_LEN):
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                f"WhatsApp list row title must be 1..{WHATSAPP_MAX_ROW_TITLE_LEN} chars",
                status_code=400,
            )
        if len(row.description.strip()) > WHATSAPP_MAX_ROW_DESC_LEN:
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                f"WhatsApp list row description exceeds {WHATSAPP_MAX_ROW_DESC_LEN} chars",
                status_code=400,
            )
    return rows


def prepare_whatsapp_outbound_message(
    *,
    recipient_ref: str,
    body_text: str,
    last_inbound_at: datetime | None,
    opt_in_consent_active: bool,
    template_id: str | None = None,
    template_category: Literal["UTILITY", "MARKETING", "AUTHENTICATION"] = "UTILITY",
    now: datetime | None = None,
) -> WhatsAppOutboundDispatch:
    current = now or utc_now()
    within_24h = last_inbound_at is not None and (current - last_inbound_at) <= timedelta(
        hours=WHATSAPP_SERVICE_WINDOW_HOURS
    )

    if not within_24h:
        # Outside 24-hour customer service window: requires active opt-in consent AND pre-approved template
        if not opt_in_consent_active:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "Outbound WhatsApp outside 24-hour window requires active opt-in consent",
                status_code=403,
            )
        if not template_id or template_id not in APPROVED_OUTBOUND_TEMPLATES:
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                "Outbound WhatsApp outside 24-hour window requires an approved SSRA template_id",
                status_code=400,
            )
        cost_usd = 0.025 if template_category == "MARKETING" else 0.014
    else:
        # Inside 24-hour customer service window: non-template & UTILITY templates are $0.00; MARKETING is billed
        cost_usd = 0.025 if (template_id and template_category == "MARKETING") else 0.0

    full_text = f"{body_text.strip()}{ANTI_IMPERSONATION_VERIFICATION_FOOTER}"
    return WhatsAppOutboundDispatch(
        recipient_ref=recipient_ref,
        within_24h_window=within_24h,
        template_id=template_id,
        formatted_body=full_text,
        estimated_cost_usd=cost_usd,
    )
