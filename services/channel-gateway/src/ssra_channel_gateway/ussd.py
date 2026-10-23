"""Phase 4 Deterministic USSD Menu Engine (Section 11).

Invariants:
1. Deterministic menu state machine with ZERO LLM calls in the synchronous path (<2s SLO).
2. Every USSD screen is strictly <= 182 characters (`USSD_MAX_CHARS = 182`).
3. Respects operator session timeout (`USSD_SESSION_TTL_SECONDS = 120`).
4. Includes '9. Send details by SMS' option (including multi-step topic-specific `1*9`..`5*9` SMS delivery)
   and full Juba Arabic (`pga`) submenu localization.
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
            "END Tasjil TIN online fi https://etax.nra.gov.ss/ "
            "(Muwatinin, Sharikat Wizarat al-Adl wa NGOs). Adrub *9 li SMS."
            if is_pga
            else "END Register for a TIN online at https://etax.nra.gov.ss/ "
            "(Citizens, MoJ-validated Businesses & NGOs). Dial *9 for SMS."
        )
        return UssdScreenResponse(
            session_id=session_id, response_type="END", screen_text=txt[:USSD_MAX_CHARS]
        )
    if choice == "2":
        txt = (
            "END Qarar March 2026: Adfa kul dariba عبر https://etax.nra.gov.ss/ "
            "fi bunuk TSA bas. Mamnu dafa kaash li ayyi muhassil."
            if is_pga
            else "END March 2026 Directive: Pay all taxes via https://etax.nra.gov.ss/ "
            "into designated banks only. Never pay cash to collectors."
        )
        return UssdScreenResponse(
            session_id=session_id, response_type="END", screen_text=txt[:USSD_MAX_CHARS]
        )
    if choice == "3":
        txt = (
            "END Iqrar wa dafa PAYE al-shahri fi https://etax.nra.gov.ss/ "
            "lazim gabil yom 15 min al-shahar al-jayi (Juba)."
            if is_pga
            else "END Monthly PAYE returns & bank payments via https://etax.nra.gov.ss/ "
            "are due by Day 15 of the following month (Africa/Juba)."
        )
        return UssdScreenResponse(
            session_id=session_id, response_type="END", screen_text=txt[:USSD_MAX_CHARS]
        )
    if choice == "4":
        txt = (
            "END Mawgi SSRA al-rasmi: https://etax.nra.gov.ss/. "
            "SSRA ma bi as'al OTP aw dafa kaash fi hisab shakhsi."
            if is_pga
            else "END Official SSRA portal: https://etax.nra.gov.ss/. "
            "SSRA never asks for your OTP or cash payment to personal accounts."
        )
        return UssdScreenResponse(
            session_id=session_id, response_type="END", screen_text=txt[:USSD_MAX_CHARS]
        )
    if choice == "5":
        txt = (
            "END Jamarik SSRA: Afa shakhsi lihad 500 USD. Iqrarat fi "
            "https://customs.eservices.gov.ss/ wa dafa bil bank fi e-Tax."
            if is_pga
            else "END SSRA Customs: Non-commercial baggage exempt up to 500 USD. "
            "File at https://customs.eservices.gov.ss/ & pay via e-Tax bank."
        )
        return UssdScreenResponse(
            session_id=session_id, response_type="END", screen_text=txt[:USSD_MAX_CHARS]
        )
    if choice == "9":
        if is_pga:
            topic_label_pga = _TOPIC_NAMES_PGA.get(parent_topic, "SSRA e-Tax")
            txt = f"END Rabit {topic_label_pga} (https://etax.nra.gov.ss/) jahiz li irsal bil SMS li raqamak."
        else:
            topic_label_en = _TOPIC_NAMES_EN.get(parent_topic, "SSRA e-Tax")
            txt = f"END Official {topic_label_en} link & instructions queued for SMS delivery to your number."
        return UssdScreenResponse(
            session_id=session_id,
            response_type="END",
            screen_text=txt[:USSD_MAX_CHARS],
            send_sms_followup=True,
        )
    if choice == "0":
        txt = (
            "END Talab mukalama min Muwazaf SSRA اتسجل (Itnin-Juma 08:00-17:00 Juba)."
            if is_pga
            else "END Your callback request has been queued for an SSRA Officer (Mon-Fri 08:00-17:00 EAT)."
        )
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
