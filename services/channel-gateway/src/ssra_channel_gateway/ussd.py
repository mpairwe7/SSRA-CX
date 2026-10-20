"""Phase 4 Deterministic USSD Menu Engine (Section 11).

Invariants:
1. Deterministic menu state machine with ZERO LLM calls in the synchronous path (<2s SLO).
2. Every USSD screen is strictly <= 182 characters (`USSD_MAX_CHARS = 182`).
3. Respects operator session timeout (`USSD_SESSION_TTL_SECONDS = 120`).
4. Includes '9. Send details by SMS' option.
"""

from __future__ import annotations

from dataclasses import dataclass

USSD_MAX_CHARS = 182
USSD_SESSION_TTL_SECONDS = 120


@dataclass(frozen=True)
class UssdScreenResponse:
    session_id: str
    response_type: str  # CON (continue) | END (terminate)
    screen_text: str
    send_sms_followup: bool = False


def render_ussd_screen(
    *,
    session_id: str,
    ussd_input: str,
    elapsed_seconds: int = 0,
    locale: str = "en",
) -> UssdScreenResponse:
    if elapsed_seconds < 0:
        raise ValueError("elapsed_seconds must be non-negative")
    if elapsed_seconds > USSD_SESSION_TTL_SECONDS:
        msg = "END Session timed out. Dial short code again or visit https://etax.nra.gov.ss/"
        return UssdScreenResponse(
            session_id=session_id,
            response_type="END",
            screen_text=msg[:USSD_MAX_CHARS],
        )

    cleaned = ussd_input.strip()
    steps = [s for s in cleaned.split("*") if s]

    if not steps:
        if locale == "pga":
            menu = (
                "CON Qaima ta SSRA:\n"
                "1. Tasjil TIN\n"
                "2. Dafa bil Bank\n"
                "3. Mawid PAYE\n"
                "4. At'akkad min SSRA\n"
                "9. Arsil bil SMS\n"
                "0. Muwazaf SSRA"
            )
        else:
            # Tier C locales (e.g. `din`) use the approved English menu fallback until OQ-008 human translator sign-off
            menu = (
                "CON SSRA Official Menu:\n"
                "1. TIN Registration\n"
                "2. Cash-Free Bank Payment\n"
                "3. PAYE Deadlines\n"
                "4. Verify SSRA Sender\n"
                "9. Send Details by SMS\n"
                "0. Officer Callback"
            )
        return UssdScreenResponse(
            session_id=session_id,
            response_type="CON",
            screen_text=menu[:USSD_MAX_CHARS],
        )

    choice = steps[-1]
    if choice == "1":
        txt = (
            "END Register for a TIN online at https://etax.nra.gov.ss/ "
            "(Citizens, MoJ-validated Businesses & NGOs). Dial *9 for SMS."
        )
        return UssdScreenResponse(
            session_id=session_id, response_type="END", screen_text=txt[:USSD_MAX_CHARS]
        )
    if choice == "2":
        txt = (
            "END March 2026 Directive: Pay all taxes via https://etax.nra.gov.ss/ "
            "into designated banks only. Never pay cash to collectors."
        )
        return UssdScreenResponse(
            session_id=session_id, response_type="END", screen_text=txt[:USSD_MAX_CHARS]
        )
    if choice == "3":
        txt = (
            "END Monthly PAYE returns & bank payments via https://etax.nra.gov.ss/ "
            "are due by Day 15 of the following month (Africa/Juba)."
        )
        return UssdScreenResponse(
            session_id=session_id, response_type="END", screen_text=txt[:USSD_MAX_CHARS]
        )
    if choice == "4":
        txt = (
            "END Official SSRA portal: https://etax.nra.gov.ss/. "
            "SSRA never asks for your OTP or cash payment to personal accounts."
        )
        return UssdScreenResponse(
            session_id=session_id, response_type="END", screen_text=txt[:USSD_MAX_CHARS]
        )
    if choice == "9":
        txt = "END Official SSRA e-Tax link & instructions queued for SMS delivery to your number."
        return UssdScreenResponse(
            session_id=session_id,
            response_type="END",
            screen_text=txt[:USSD_MAX_CHARS],
            send_sms_followup=True,
        )
    if choice == "0":
        txt = "END Your callback request has been queued for an SSRA Officer (Mon-Fri 08:00-17:00 EAT)."
        return UssdScreenResponse(
            session_id=session_id, response_type="END", screen_text=txt[:USSD_MAX_CHARS]
        )

    fallback = "CON Invalid option. Press 1 (TIN), 2 (Payment), 3 (PAYE), 9 (SMS), or 0 (Officer)."
    return UssdScreenResponse(
        session_id=session_id, response_type="CON", screen_text=fallback[:USSD_MAX_CHARS]
    )
