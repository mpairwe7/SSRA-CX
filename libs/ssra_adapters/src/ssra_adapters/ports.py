"""Anti-corruption ports and synthetic mock adapters for SSRA systems of record (Sections 5, 8.4, 12.3, 19).

Security invariant: Every T1+ method takes the verified `subject_ref` extracted from the
OAuth 2.1 RFC 8693 exchanged token and enforces ownership server-side. It NEVER accepts
an unverified TIN from LLM arguments to read another taxpayer's record.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Protocol
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict
from ssra_core import McpErrorCode, SSRAError
from ssra_security import mask_tin


class TaxpayerProfileMasked(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_ref: str
    tin_masked: str
    taxpayer_type: Literal["INDIVIDUAL", "BUSINESS", "NGO"]
    display_name_masked: str
    registration_status: Literal["ACTIVE", "PENDING_VERIFICATION", "SUSPENDED"]
    tax_office: str
    as_of: datetime


class LedgerBalanceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_ref: str
    tin_masked: str
    total_outstanding_ssp: str
    currency: Literal["SSP"] = "SSP"
    filing_status: Literal["COMPLIANT", "FILING_DUE", "OVERDUE"]
    last_filed_period: str
    tcc_status: Literal["VALID", "EXPIRED", "ELIGIBLE", "INELIGIBLE_BALANCE_DUE"]
    tcc_expiry_date: str | None
    as_of: datetime


class OfficialChannelEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    channel_type: Literal[
        "DOMAIN",
        "PAYMENT_PORTAL",
        "SMS_SENDER_ID",
        "WHATSAPP",
        "BANK_TSA_PATH",
        "SUPPORT_EMAIL",
        "SUPPORT_PHONE",
    ]
    identifier: str
    status: Literal["OFFICIAL_VERIFIED", "UNVERIFIED_OR_SCAM"]
    guidance: str
    verified_at: datetime


class CustomsDeclarationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_ref: str
    declaration_ref_masked: str
    port_of_entry: str
    status: Literal["UNDER_ASSESSMENT", "AWAITING_ETAX_BANK_PAYMENT", "CLEARED"]
    assessed_duty_ssp: str
    boss_official_fx_rate_used: str
    as_of: datetime


class ETaxPort(Protocol):
    def get_profile_masked(self, *, subject_ref: str) -> TaxpayerProfileMasked: ...
    def get_ledger_balance(self, *, subject_ref: str) -> LedgerBalanceRecord: ...


class MockETaxAdapter:
    """Deterministic synthetic e-Tax adapter (`OQ-001`) with server-side subject_ref isolation."""

    def __init__(self) -> None:
        fixed_time = datetime(2026, 10, 16, 8, 0, tzinfo=UTC)
        self._profiles: dict[str, TaxpayerProfileMasked] = {
            "sub_taxpayer_amina_01": TaxpayerProfileMasked(
                subject_ref="sub_taxpayer_amina_01",
                tin_masked=mask_tin("1002001234"),
                taxpayer_type="INDIVIDUAL",
                display_name_masked="A•••a M.",
                registration_status="ACTIVE",
                tax_office="Juba Domestic Tax Office",
                as_of=fixed_time,
            ),
            "sub_taxpayer_deng_02": TaxpayerProfileMasked(
                subject_ref="sub_taxpayer_deng_02",
                tin_masked=mask_tin("2003005678"),
                taxpayer_type="BUSINESS",
                display_name_masked="D•••g Trading Co.",
                registration_status="ACTIVE",
                tax_office="Juba Medium Taxpayer Office",
                as_of=fixed_time,
            ),
        }
        self._ledgers: dict[str, LedgerBalanceRecord] = {
            "sub_taxpayer_amina_01": LedgerBalanceRecord(
                subject_ref="sub_taxpayer_amina_01",
                tin_masked=mask_tin("1002001234"),
                total_outstanding_ssp="0",
                filing_status="COMPLIANT",
                last_filed_period="2026-09",
                tcc_status="VALID",
                tcc_expiry_date="2026-12-31",
                as_of=fixed_time,
            ),
            "sub_taxpayer_deng_02": LedgerBalanceRecord(
                subject_ref="sub_taxpayer_deng_02",
                tin_masked=mask_tin("2003005678"),
                total_outstanding_ssp="1450000",
                filing_status="FILING_DUE",
                last_filed_period="2026-08",
                tcc_status="INELIGIBLE_BALANCE_DUE",
                tcc_expiry_date=None,
                as_of=fixed_time,
            ),
        }

    def get_profile_masked(self, *, subject_ref: str) -> TaxpayerProfileMasked:
        profile = self._profiles.get(subject_ref)
        if profile is None:
            raise SSRAError(
                McpErrorCode.NOT_FOUND,
                f"No taxpayer profile bound to subject_ref '{subject_ref}'",
                status_code=404,
            )
        return profile

    def get_ledger_balance(self, *, subject_ref: str) -> LedgerBalanceRecord:
        ledger = self._ledgers.get(subject_ref)
        if ledger is None:
            raise SSRAError(
                McpErrorCode.NOT_FOUND,
                f"No ledger record bound to subject_ref '{subject_ref}'",
                status_code=404,
            )
        return ledger


class MockOfficialChannelsAdapter:
    """Curated anti-impersonation registry of official SSRA channels (`etax.nra.gov.ss`, `nra.gov.ss`)."""

    def __init__(self) -> None:
        self._verified_time = datetime(2026, 10, 16, 0, 0, tzinfo=UTC)
        self._official_identifiers: dict[str, OfficialChannelEntry] = {
            "etax.nra.gov.ss": OfficialChannelEntry(
                channel_type="PAYMENT_PORTAL",
                identifier="https://etax.nra.gov.ss/",
                status="OFFICIAL_VERIFIED",
                guidance=(
                    "OFFICIAL: https://etax.nra.gov.ss/ is the official SSRA (formerly NRA) "
                    "National e-Tax portal for TIN registration, filing, TCCs, and bank payment assessment slips."
                ),
                verified_at=self._verified_time,
            ),
            "nra.gov.ss": OfficialChannelEntry(
                channel_type="DOMAIN",
                identifier="https://www.nra.gov.ss/",
                status="OFFICIAL_VERIFIED",
                guidance="OFFICIAL: https://www.nra.gov.ss/ is the official South Sudan Revenue Authority website and verification portal (/tools).",
                verified_at=self._verified_time,
            ),
            "www.nra.gov.ss": OfficialChannelEntry(
                channel_type="DOMAIN",
                identifier="https://www.nra.gov.ss/",
                status="OFFICIAL_VERIFIED",
                guidance="OFFICIAL: https://www.nra.gov.ss/ is the official South Sudan Revenue Authority website and verification portal (/tools).",
                verified_at=self._verified_time,
            ),
            "cms.nra.gov.ss": OfficialChannelEntry(
                channel_type="DOMAIN",
                identifier="https://cms.nra.gov.ss/",
                status="OFFICIAL_VERIFIED",
                guidance="OFFICIAL: Official SSRA document and statutory publication domain (Financial Acts & SSRA Act 2023).",
                verified_at=self._verified_time,
            ),
            "eservices.gov.ss": OfficialChannelEntry(
                channel_type="DOMAIN",
                identifier="https://eservices.gov.ss/",
                status="OFFICIAL_VERIFIED",
                guidance="OFFICIAL: Republic of South Sudan National eServices single-window portal.",
                verified_at=self._verified_time,
            ),
            "business.eservices.gov.ss": OfficialChannelEntry(
                channel_type="DOMAIN",
                identifier="https://business.eservices.gov.ss/",
                status="OFFICIAL_VERIFIED",
                guidance="OFFICIAL: Ministry of Justice Business Registration validation portal required before business TIN registration on e-Tax.",
                verified_at=self._verified_time,
            ),
            "www.trade.eservices.gov.ss": OfficialChannelEntry(
                channel_type="DOMAIN",
                identifier="https://www.trade.eservices.gov.ss/",
                status="OFFICIAL_VERIFIED",
                guidance="OFFICIAL: Ministry of Trade and Industry portal for mandatory Trade Accreditation Permits (SSRA Public Notice 5 Oct 2024).",
                verified_at=self._verified_time,
            ),
            "customs.eservices.gov.ss": OfficialChannelEntry(
                channel_type="DOMAIN",
                identifier="https://customs.eservices.gov.ss/",
                status="OFFICIAL_VERIFIED",
                guidance="OFFICIAL: Official SSRA eCustoms portal for Custom Declaration Applications (SAD Form 17A) and Custom Agents License Applications.",
                verified_at=self._verified_time,
            ),
            "ecustoms.nra.gov.ss": OfficialChannelEntry(
                channel_type="DOMAIN",
                identifier="https://ecustoms.nra.gov.ss/",
                status="OFFICIAL_VERIFIED",
                guidance="OFFICIAL: Official SSRA Customs Revenue Division eCustoms resources and FAQs portal.",
                verified_at=self._verified_time,
            ),
            "mofp.gov.ss": OfficialChannelEntry(
                channel_type="DOMAIN",
                identifier="https://mofp.gov.ss/",
                status="OFFICIAL_VERIFIED",
                guidance="OFFICIAL: Republic of South Sudan Ministry of Finance and Planning (MoFP) official portal.",
                verified_at=self._verified_time,
            ),
            "boss.gov.ss": OfficialChannelEntry(
                channel_type="DOMAIN",
                identifier="https://boss.gov.ss/",
                status="OFFICIAL_VERIFIED",
                guidance="OFFICIAL: Bank of South Sudan (BoSS) official portal publishing official exchange rates and SSRA Block Account directives.",
                verified_at=self._verified_time,
            ),
            "support@nra.gov.ss": OfficialChannelEntry(
                channel_type="SUPPORT_EMAIL",
                identifier="support@nra.gov.ss",
                status="OFFICIAL_VERIFIED",
                guidance="OFFICIAL: Official SSRA e-Tax Helpdesk support email published on https://etax.nra.gov.ss/ and https://www.nra.gov.ss/.",
                verified_at=self._verified_time,
            ),
            "+211918806493": OfficialChannelEntry(
                channel_type="SUPPORT_PHONE",
                identifier="+211 918806493",
                status="OFFICIAL_VERIFIED",
                guidance="OFFICIAL: Published SSRA e-Tax Helpdesk support line on https://etax.nra.gov.ss/. Note: SSRA officers will never ask for your OTP or cash payment.",
                verified_at=self._verified_time,
            ),
            "+211912388318": OfficialChannelEntry(
                channel_type="SUPPORT_PHONE",
                identifier="+211 912388318",
                status="OFFICIAL_VERIFIED",
                guidance="OFFICIAL: Published SSRA e-Tax Helpdesk support line on https://etax.nra.gov.ss/.",
                verified_at=self._verified_time,
            ),
            "+211919382390": OfficialChannelEntry(
                channel_type="SUPPORT_PHONE",
                identifier="+211 919382390",
                status="OFFICIAL_VERIFIED",
                guidance="OFFICIAL: Published SSRA e-Tax Helpdesk support line on https://etax.nra.gov.ss/.",
                verified_at=self._verified_time,
            ),
            "+211917803637": OfficialChannelEntry(
                channel_type="SUPPORT_PHONE",
                identifier="+211 917803637",
                status="OFFICIAL_VERIFIED",
                guidance="OFFICIAL: Published SSRA e-Tax Helpdesk support line on https://etax.nra.gov.ss/.",
                verified_at=self._verified_time,
            ),
            "+211921058043": OfficialChannelEntry(
                channel_type="SUPPORT_PHONE",
                identifier="+211 921058043",
                status="OFFICIAL_VERIFIED",
                guidance="OFFICIAL: Published SSRA e-Tax Helpdesk support line on https://etax.nra.gov.ss/.",
                verified_at=self._verified_time,
            ),
            "ssra": OfficialChannelEntry(
                channel_type="SMS_SENDER_ID",
                identifier="SSRA",
                status="OFFICIAL_VERIFIED",
                guidance=(
                    "OFFICIAL SENDER ID (Pending final MNO confirmation OQ-007): Official SSRA "
                    "messages never ask for your password, OTP, or cash/personal mobile-money transfers."
                ),
                verified_at=self._verified_time,
            ),
            "tsa-etax-bank": OfficialChannelEntry(
                channel_type="BANK_TSA_PATH",
                identifier="TSA-ETAX-BANK",
                status="OFFICIAL_VERIFIED",
                guidance=(
                    "OFFICIAL: Under the March 2026 cash-free directive, all SSRA tax payments are "
                    "routed exclusively through the National e-Tax System (etax.nra.gov.ss) into designated commercial banks."
                ),
                verified_at=self._verified_time,
            ),
        }

    def verify_identifier(self, candidate: str) -> OfficialChannelEntry:
        raw = candidate.strip()
        lower_raw = raw.lower()
        scam_entry = OfficialChannelEntry(
            channel_type="DOMAIN",
            identifier=raw,
            status="UNVERIFIED_OR_SCAM",
            guidance=(
                "WARNING — NOT IN OFFICIAL SSRA REGISTRY: Do not pay money or share your TIN/OTP. "
                "Under the March 2026 directive, SSRA prohibits manual cash collection and personal "
                "account transfers. Always use https://etax.nra.gov.ss/ and report suspected scams."
            ),
            verified_at=self._verified_time,
        )
        # 1. Block Unicode homoglyphs (IDN homograph attacks), Punycode xn--, and cleartext HTTP downgrades
        if not raw.isascii() or "xn--" in lower_raw or lower_raw.startswith("http://"):
            return scam_entry

        cleaned = lower_raw.removeprefix("mailto:").strip()
        if cleaned in ("support@nra.gov.ss", "ssra", "tsa-etax-bank"):
            return self._official_identifiers[cleaned]

        compact_phone = cleaned.replace(" ", "").replace("-", "")
        if compact_phone.startswith("+211") and compact_phone in self._official_identifiers:
            return self._official_identifiers[compact_phone]

        # 2. Reject any remaining '@' (RFC 3986 userinfo spoofing e.g. https://etax.nra.gov.ss@evil.example/ or unknown emails)
        if "@" in cleaned:
            return scam_entry

        # 3. Parse URL/domain with urlsplit to verify exact official hostname while allowing official deep links
        url_target = cleaned if cleaned.startswith("https://") else f"https://{cleaned}"
        try:
            parsed = urlsplit(url_target)
            port = parsed.port
        except ValueError:
            return scam_entry

        host = (parsed.hostname or "").rstrip(".")
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or port not in (None, 443)
            or ".." in parsed.path
            or "//" in parsed.path
        ):
            return scam_entry

        entry = self._official_identifiers.get(host)
        if entry is not None and entry.channel_type in ("DOMAIN", "PAYMENT_PORTAL"):
            return entry
        return scam_entry


class BoSSOfficialFxRate(BaseModel):
    """Official Bank of South Sudan (BoSS) Exchange Rate Feed Record (Section 2 & OQ-006).

    Invariant: The assistant NEVER computes or guesses an exchange rate; it reads only
    published official BoSS rates from this deterministic port.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_currency: Literal["USD"] = "USD"
    quote_currency: Literal["SSP"] = "SSP"
    official_rate_ssp_per_usd: str
    effective_date: str
    source_authority: str = "Bank of South Sudan (BoSS) Official Daily Bulletin"


class MockBoSSAdapter:
    """Deterministic Bank of South Sudan (BoSS) official exchange rate adapter (`OQ-006`)."""

    def get_official_usd_to_ssp_rate(self, *, as_of_date: str = "2026-10-16") -> BoSSOfficialFxRate:
        return BoSSOfficialFxRate(
            official_rate_ssp_per_usd="4500",
            effective_date=as_of_date,
        )


class CustomsTariffItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    hs_code: str
    description: str
    duty_rate_percent: str
    excise_rate_percent: str
    legal_ref: str
    boss_official_fx_rate_ssp_per_usd: str
    as_of: datetime


class MockECustomsAdapter:
    """Synthetic e-Customs adapter (`OQ-002`) using official BoSS exchange rate feed."""

    def __init__(self) -> None:
        fixed_time = datetime(2026, 10, 16, 8, 0, tzinfo=UTC)
        self._fixed_time = fixed_time
        self._boss_fx_ssp_per_usd = "4500"
        self._tariffs: dict[str, CustomsTariffItem] = {
            "1006.30": CustomsTariffItem(
                hs_code="1006.30",
                description="Semi-milled or wholly milled rice (essential foodstuff schedule)",
                duty_rate_percent="0",
                excise_rate_percent="0",
                legal_ref="Customs Service Act 2013 & Financial Act 2024/2025 Tariff Schedule",
                boss_official_fx_rate_ssp_per_usd=self._boss_fx_ssp_per_usd,
                as_of=fixed_time,
            ),
            "2201.10": CustomsTariffItem(
                hs_code="2201.10",
                description="Mineral waters and aerated waters (unsweetened/unflavored)",
                duty_rate_percent="35",
                excise_rate_percent="15",
                legal_ref="Financial Act 2024/2025 (Ch. 22 Customs 35%, HS 22.01 Excise 15%, Effective 2 Dec 2024)",
                boss_official_fx_rate_ssp_per_usd=self._boss_fx_ssp_per_usd,
                as_of=fixed_time,
            ),
            "2203.00": CustomsTariffItem(
                hs_code="2203.00",
                description="Beer made from malt",
                duty_rate_percent="35",
                excise_rate_percent="50",
                legal_ref="Financial Act 2024/2025 (Ch. 22 Customs 35%, HS 22.03 Excise 50%, Effective 2 Dec 2024)",
                boss_official_fx_rate_ssp_per_usd=self._boss_fx_ssp_per_usd,
                as_of=fixed_time,
            ),
            "2402.20": CustomsTariffItem(
                hs_code="2402.20",
                description="Cigarettes containing tobacco",
                duty_rate_percent="35",
                excise_rate_percent="100",
                legal_ref="Financial Act 2024/2025 (Ch. 24 Customs 35%, HS 24.02 Excise 100%, Effective 2 Dec 2024)",
                boss_official_fx_rate_ssp_per_usd=self._boss_fx_ssp_per_usd,
                as_of=fixed_time,
            ),
            "3303.00": CustomsTariffItem(
                hs_code="3303.00",
                description="Perfumes and toilet waters",
                duty_rate_percent="15",
                excise_rate_percent="25",
                legal_ref="Financial Act 2024/2025 (HS 33.03 Excise 25%, Effective 2 Dec 2024)",
                boss_official_fx_rate_ssp_per_usd=self._boss_fx_ssp_per_usd,
                as_of=fixed_time,
            ),
            "3901.10": CustomsTariffItem(
                hs_code="3901.10",
                description="Plastics in primary form (polyethylene)",
                duty_rate_percent="5",
                excise_rate_percent="0",
                legal_ref="Financial Act 2024/2025 (Ch. 39 39.01-39.08 Customs 5%, Effective 2 Dec 2024)",
                boss_official_fx_rate_ssp_per_usd=self._boss_fx_ssp_per_usd,
                as_of=fixed_time,
            ),
            "8702.10": CustomsTariffItem(
                hs_code="8702.10",
                description="Motor vehicles for transport of 10 or more persons (buses)",
                duty_rate_percent="15",
                excise_rate_percent="10",
                legal_ref="Financial Act 2024/2025 (HS 87.02 Excise 10%, Effective 2 Dec 2024)",
                boss_official_fx_rate_ssp_per_usd=self._boss_fx_ssp_per_usd,
                as_of=fixed_time,
            ),
            "8703.23": CustomsTariffItem(
                hs_code="8703.23",
                description="Passenger motor cars and station wagons (HS 87.03)",
                duty_rate_percent="20",
                excise_rate_percent="25",
                legal_ref="Financial Act 2024/2025 (HS 87.03 Excise 25%, Effective 2 Dec 2024)",
                boss_official_fx_rate_ssp_per_usd=self._boss_fx_ssp_per_usd,
                as_of=fixed_time,
            ),
            "8704.21": CustomsTariffItem(
                hs_code="8704.21",
                description="Motor vehicles for the transport of goods (trucks)",
                duty_rate_percent="15",
                excise_rate_percent="10",
                legal_ref="Financial Act 2024/2025 (HS 87.04 Excise 10%, Effective 2 Dec 2024)",
                boss_official_fx_rate_ssp_per_usd=self._boss_fx_ssp_per_usd,
                as_of=fixed_time,
            ),
            "8711.20": CustomsTariffItem(
                hs_code="8711.20",
                description="Motorcycles and mopeds (HS 87.11)",
                duty_rate_percent="15",
                excise_rate_percent="25",
                legal_ref="Financial Act 2024/2025 (HS 87.11 Excise 25%, Effective 2 Dec 2024)",
                boss_official_fx_rate_ssp_per_usd=self._boss_fx_ssp_per_usd,
                as_of=fixed_time,
            ),
        }
        self._declarations: dict[str, CustomsDeclarationSummary] = {
            "sub_taxpayer_deng_02": CustomsDeclarationSummary(
                subject_ref="sub_taxpayer_deng_02",
                declaration_ref_masked="SSD-NIM-2026-••89",
                port_of_entry="Nimule Border Station",
                status="AWAITING_ETAX_BANK_PAYMENT",
                assessed_duty_ssp="3250000",
                boss_official_fx_rate_used="Official BoSS Rate (As-of 2026-10-16)",
                as_of=fixed_time,
            )
        }

    def lookup_tariff(self, hs_code: str) -> CustomsTariffItem:
        item = self._tariffs.get(hs_code.strip())
        if item is None:
            raise SSRAError(
                McpErrorCode.NOT_FOUND,
                f"HS code '{hs_code}' not found in synthetic tariff schedule (OQ-002)",
                status_code=404,
            )
        return item

    def get_declaration_status(self, *, subject_ref: str) -> CustomsDeclarationSummary:
        dec = self._declarations.get(subject_ref)
        if dec is None:
            raise SSRAError(
                McpErrorCode.NOT_FOUND,
                f"No customs declaration found for subject_ref '{subject_ref}'",
                status_code=404,
            )
        return dec
