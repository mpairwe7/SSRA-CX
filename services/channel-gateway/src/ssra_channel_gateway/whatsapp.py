"""WhatsApp Business Platform 24-Hour Service Window, Outbound Template Gate & Anti-Scam Footer (Section 11)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ssra_core import McpErrorCode, SSRAError, utc_now

WHATSAPP_SERVICE_WINDOW_HOURS = 24
APPROVED_OUTBOUND_TEMPLATES: frozenset[str] = frozenset(
    {
        "ssra_filing_reminder_v1",
        "ssra_appointment_confirmation_v1",
        "ssra_callback_scheduled_v1",
        "ssra_case_status_update_v1",
    }
)

ANTI_IMPERSONATION_VERIFICATION_FOOTER = (
    "\n---\nVerify this message: Official SSRA portal is https://etax.nra.gov.ss/. "
    "SSRA never asks for your OTP or cash payment to an individual."
)


@dataclass(frozen=True)
class WhatsAppOutboundDispatch:
    recipient_ref: str
    within_24h_window: bool
    template_id: str | None
    formatted_body: str
    estimated_cost_usd: float


def prepare_whatsapp_outbound_message(
    *,
    recipient_ref: str,
    body_text: str,
    last_inbound_at: datetime | None,
    opt_in_consent_active: bool,
    template_id: str | None = None,
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
        cost_usd = 0.014  # Utility template conversation rate
    else:
        cost_usd = 0.0  # Service conversation within 24-hour user-initiated window

    full_text = f"{body_text.strip()}{ANTI_IMPERSONATION_VERIFICATION_FOOTER}"
    return WhatsAppOutboundDispatch(
        recipient_ref=recipient_ref,
        within_24h_window=within_24h,
        template_id=template_id,
        formatted_body=full_text,
        estimated_cost_usd=cost_usd,
    )
