"""Anti-corruption ports and synthetic mock adapters for SSRA systems of record (Sections 5, 8.4, 12.3, 19).

Security invariant: Every T1+ method takes the verified `subject_ref` extracted from the
OAuth 2.1 RFC 8693 exchanged token and enforces ownership server-side. It NEVER accepts
an unverified TIN from LLM arguments to read another taxpayer's record.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Protocol

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

    channel_type: Literal["DOMAIN", "PAYMENT_PORTAL", "SMS_SENDER_ID", "WHATSAPP", "BANK_TSA_PATH"]
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
    """Curated anti-impersonation registry of official SSRA channels (`OQ-011`)."""

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
            "cms.nra.gov.ss": OfficialChannelEntry(
                channel_type="DOMAIN",
                identifier="https://cms.nra.gov.ss/",
                status="OFFICIAL_VERIFIED",
                guidance="OFFICIAL: Official SSRA document and statutory publication domain.",
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
        normalised = (
            candidate.strip().lower().removeprefix("https://").removeprefix("http://").rstrip("/")
        )
        entry = self._official_identifiers.get(normalised)
        if entry is not None:
            return entry
        return OfficialChannelEntry(
            channel_type="DOMAIN",
            identifier=candidate.strip(),
            status="UNVERIFIED_OR_SCAM",
            guidance=(
                "WARNING — NOT IN OFFICIAL SSRA REGISTRY: Do not pay money or share your TIN/OTP. "
                "Under the March 2026 directive, SSRA prohibits manual cash collection and personal "
                "account transfers. Always use https://etax.nra.gov.ss/ and report suspected scams."
            ),
            verified_at=self._verified_time,
        )


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
                legal_ref="Customs Service Act 2013 & Financial Act 2024/2025 Tariff Schedule (Subject to OQ-002)",
                boss_official_fx_rate_ssp_per_usd=self._boss_fx_ssp_per_usd,
                as_of=fixed_time,
            ),
            "8703.23": CustomsTariffItem(
                hs_code="8703.23",
                description="Passenger motor vehicles (1,500 cc to 3,000 cc)",
                duty_rate_percent="20",
                excise_rate_percent="15",
                legal_ref="Customs Service Act 2013 & Financial Act 2024/2025 Tariff Schedule (Subject to OQ-002)",
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
