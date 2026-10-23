"""Phase 4 Deterministic USSD Menu Engine (Section 11).

Invariants:
1. Deterministic menu state machine with ZERO LLM calls in the synchronous path (<2s SLO).
2. Every USSD screen is strictly <= 182 characters (`USSD_MAX_CHARS = 182`).
3. Respects operator session timeout (`USSD_SESSION_TTL_SECONDS = 120`).
4. Includes '9. Send details by SMS' option (keeping topic screens open as `CON` so users can
   press `9` in-session or dial `1*9`..`5*9` directly) and full Juba Arabic (`pga`) localization.
"""

from __future__ import annotations

from dataclasses import dataclass

USSD_MAX_CHARS = 182
USSD_SESSION_TTL_SECONDS = 120

_TOPIC_NAMES_EN: dict[str, str] = {
    "1": "TIN Registration",
    "2": "Cash-Free Bank Payment",
    "3": "PAYE Deadlines",
    "4": "Official Sender Verification",
    "5": "Customs & $500 Exemption",
}
_TOPIC_NAMES_PGA: dict[str, str] = {
    "1": "Tasjil TIN",
    "2": "Dafa bil Bank",
    "3": "Mawid PAYE",
    "4": "At'akkad min SSRA",
    "5": "Jamarik ($500)",
}


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
    is_pga = locale == "pga"
    if elapsed_seconds > USSD_SESSION_TTL_SECONDS:
        msg = (
            "END الزمن خلص. اضرب الكود تاني أو زور https://etax.nra.gov.ss/"
            if is_pga
            else "END Session timed out. Dial short code again or visit https://etax.nra.gov.ss/"
        )
        return UssdScreenResponse(
            session_id=session_id,
            response_type="END",
            screen_text=msg[:USSD_MAX_CHARS],
        )

    cleaned = ussd_input.strip()
    steps = [s for s in cleaned.split("*") if s]

    if not steps:
        if is_pga:
            menu = (
                "CON Qaima ta SSRA:\n"
                "1. Tasjil TIN\n"
                "2. Dafa bil Bank\n"
                "3. Mawid PAYE\n"
                "4. At'akkad min SSRA\n"
                "5. Jamarik ($500)\n"
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
                "5. Customs ($500 Exempt)\n"
                "9. Send Details by SMS\n"
                "0. Officer Callback"
            )
        return UssdScreenResponse(
            session_id=session_id,
            response_type="CON",
            screen_text=menu[:USSD_MAX_CHARS],
        )

    choice = steps[-1]
    parent_topic = steps[-2] if len(steps) >= 2 else ""

    if choice == "1":
        txt = (
            "CON Tasjil TIN online fi https://etax.nra.gov.ss/ "
            "(Muwatinin, Sharikat Wizarat al-Adl wa NGOs). Adrub 9 li SMS aw 0."
            if is_pga
            else "CON Register for a TIN online at https://etax.nra.gov.ss/ "
            "(Citizens, MoJ-validated Businesses & NGOs). Press 9 for SMS or 0."
        )
        return UssdScreenResponse(
            session_id=session_id, response_type="CON", screen_text=txt[:USSD_MAX_CHARS]
        )
    if choice == "2":
        txt = (
            "CON Qarar March 2026: Adfa kul dariba fi https://etax.nra.gov.ss/ "
            "bi bunuk TSA bas. Mamnu kaash. Adrub 9 li SMS aw 0."
            if is_pga
            else "CON March 2026 Directive: Pay all taxes via https://etax.nra.gov.ss/ "
            "into designated banks only. Press 9 for SMS or 0."
        )
        return UssdScreenResponse(
            session_id=session_id, response_type="CON", screen_text=txt[:USSD_MAX_CHARS]
        )
    if choice == "3":
        txt = (
            "CON Iqrar wa dafa PAYE al-shahri fi https://etax.nra.gov.ss/ "
            "lazim gabil yom 15 (Juba). Adrub 9 li SMS aw 0."
            if is_pga
            else "CON Monthly PAYE returns & bank payments via https://etax.nra.gov.ss/ "
            "are due by Day 15 (Africa/Juba). Press 9 for SMS or 0."
        )
        return UssdScreenResponse(
            session_id=session_id, response_type="CON", screen_text=txt[:USSD_MAX_CHARS]
        )
    if choice == "4":
        txt = (
            "CON Mawgi SSRA al-rasmi: https://etax.nra.gov.ss/. "
            "SSRA ma bi as'al OTP aw kaash. Adrub 9 li SMS aw 0."
            if is_pga
            else "CON Official SSRA portal: https://etax.nra.gov.ss/. "
            "SSRA never asks for OTP or cash. Press 9 for SMS or 0."
        )
        return UssdScreenResponse(
            session_id=session_id, response_type="CON", screen_text=txt[:USSD_MAX_CHARS]
        )
    if choice == "5":
        txt = (
            "CON Jamarik SSRA: Afa shakhsi lihad 500 USD. Iqrarat fi "
            "https://customs.eservices.gov.ss/. Adrub 9 li SMS aw 0."
            if is_pga
            else "CON SSRA Customs: Non-commercial baggage exempt up to 500 USD "
            "at https://customs.eservices.gov.ss/. Press 9 for SMS or 0."
        )
        return UssdScreenResponse(
            session_id=session_id, response_type="CON", screen_text=txt[:USSD_MAX_CHARS]
        )
    if choice == "9":
        portal_url = (
            "https://customs.eservices.gov.ss/"
            if parent_topic == "5"
            else "https://etax.nra.gov.ss/"
        )
        if is_pga:
            topic_label_pga = _TOPIC_NAMES_PGA.get(parent_topic, "SSRA e-Tax")
            txt = f"END Rabit {topic_label_pga} ({portal_url}) jahiz li irsal bil SMS li raqamak."
        else:
            topic_label_en = _TOPIC_NAMES_EN.get(parent_topic, "SSRA e-Tax")
            txt = f"END Official {topic_label_en} link ({portal_url}) queued for SMS delivery."
        return UssdScreenResponse(
            session_id=session_id,
            response_type="END",
            screen_text=txt[:USSD_MAX_CHARS],
            send_sms_followup=True,
        )
    if choice == "0":
        if is_pga:
            topic_pga = _TOPIC_NAMES_PGA.get(parent_topic, "")
            prefix_pga = f" ({topic_pga})" if topic_pga else ""
            txt = f"END Talab mukalama min Muwazaf SSRA{prefix_pga} اتسجل (Itnin-Juma 08:00-17:00 Juba)."
        else:
            topic_en = _TOPIC_NAMES_EN.get(parent_topic, "")
            prefix_en = f" ({topic_en})" if topic_en else ""
            txt = f"END Your{prefix_en} callback request has been queued for an SSRA Officer (Mon-Fri 08:00-17:00 EAT)."
        return UssdScreenResponse(
            session_id=session_id, response_type="END", screen_text=txt[:USSD_MAX_CHARS]
        )

    fallback = (
        "CON Ikhtiyar ghalat. Adrub 1 (TIN), 2 (Bank), 3 (PAYE), 5 (Jamarik), 9 (SMS), aw 0."
        if is_pga
        else "CON Invalid option. Press 1 (TIN), 2 (Payment), 3 (PAYE), 5 (Customs), 9 (SMS), or 0 (Officer)."
    )
    return UssdScreenResponse(
        session_id=session_id, response_type="CON", screen_text=fallback[:USSD_MAX_CHARS]
    )
