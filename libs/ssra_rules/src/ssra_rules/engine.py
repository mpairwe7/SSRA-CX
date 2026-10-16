"""Deterministic rules engine & versioned Tax Facts registry (Sections 3, 4, 7, 17)."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict
from ssra_core import (
    McpErrorCode,
    NumericClaim,
    NumericUnit,
    SSRAError,
    TaxFactContract,
    juba_today,
)

_DEFAULT_SEED_FILE = (
    Path(__file__).resolve().parents[4] / "knowledge" / "tax-facts" / "seed-2026.10.1.yaml"
)

ESTIMATE_DISCLAIMER_EN = (
    "ESTIMATE ONLY: This calculation is an informational estimate based on published SSRA "
    "Tax Facts and is not an official tax assessment or legal ruling."
)


class PayeBandBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    band_index: int
    taxable_amount_ssp: str
    rate_percent: str
    tax_amount_ssp: str
    rate_fact_key: str


class PayeEstimateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    gross_monthly_ssp: str
    estimated_tax_ssp: str
    net_monthly_ssp: str
    effective_rate_percent: str
    filing_deadline_day: int
    currency: Literal["SSP"] = "SSP"
    snapshot_version: str
    as_of: date
    legal_ref: str
    is_estimate: Literal[True] = True
    disclaimer: str = ESTIMATE_DISCLAIMER_EN
    bands: list[PayeBandBreakdown]
    numeric_claims: list[NumericClaim]


WithholdingCategory = Literal[
    "goods_and_services",
    "rent",
    "technical_fees",
    "government_contractors_resident",
    "government_contractors_non_resident",
    "mobile_money_commissions",
    "end_of_service_benefits",
]


class WithholdingEstimateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: WithholdingCategory
    gross_amount_ssp: str
    rate_percent: str
    withholding_tax_ssp: str
    net_payable_ssp: str
    currency: Literal["SSP"] = "SSP"
    snapshot_version: str
    as_of: date
    legal_ref: str
    rate_fact_key: str
    is_estimate: Literal[True] = True
    disclaimer: str = ESTIMATE_DISCLAIMER_EN
    numeric_claims: list[NumericClaim]


def _quantize_ssp(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _format_decimal(amount: Decimal) -> str:
    q = _quantize_ssp(amount)
    if q == q.to_integral_value():
        return str(int(q))
    return format(q.normalize(), "f")


class TaxFactsRegistry:
    """Loads and queries versioned TaxFact records with effective-date & non-overlap validation."""

    def __init__(self, facts: list[TaxFactContract], snapshot_version: str = "2026.10.1") -> None:
        self._verify_no_overlapping_effective_ranges(facts)
        self._facts = tuple(facts)
        self._snapshot_version = snapshot_version

    @staticmethod
    def _verify_no_overlapping_effective_ranges(facts: list[TaxFactContract]) -> None:
        """Enforce PostgreSQL 18 WITHOUT OVERLAPS temporal invariant in application memory."""
        by_key: dict[tuple[str, str], list[TaxFactContract]] = {}
        for f in facts:
            if f.effective_to is not None and f.effective_to < f.effective_from:
                raise SSRAError(
                    McpErrorCode.VALIDATION_FAILED,
                    f"TaxFact '{f.key}' has effective_to ({f.effective_to}) < effective_from ({f.effective_from})",
                    status_code=400,
                )
            by_key.setdefault((f.key, f.version), []).append(f)

        max_date = date(9999, 12, 31)
        for (key, ver), group in by_key.items():
            ordered = sorted(group, key=lambda x: x.effective_from)
            for idx in range(len(ordered) - 1):
                cur = ordered[idx]
                nxt = ordered[idx + 1]
                cur_end = cur.effective_to or max_date
                if cur_end >= nxt.effective_from:
                    raise SSRAError(
                        McpErrorCode.VALIDATION_FAILED,
                        f"Overlapping effective date range for TaxFact '{key}' (version {ver}): "
                        f"[{cur.effective_from}..{cur_end}] overlaps [{nxt.effective_from}..{nxt.effective_to}]",
                        status_code=400,
                    )

    @classmethod
    def from_yaml_file(cls, path: Path | None = None) -> TaxFactsRegistry:
        target = path or _DEFAULT_SEED_FILE
        raw = yaml.safe_load(target.read_text(encoding="utf-8"))
        snapshot_version = str(raw.get("snapshot_version", "2026.10.1"))
        facts = [TaxFactContract.model_validate(item) for item in raw.get("facts", [])]
        return cls(facts=facts, snapshot_version=snapshot_version)

    @property
    def snapshot_version(self) -> str:
        return self._snapshot_version

    def get_fact(self, key: str, *, as_of: date | None = None) -> TaxFactContract:
        target_date = as_of or juba_today()
        matches = [
            f
            for f in self._facts
            if f.key == key
            and f.effective_from <= target_date
            and (f.effective_to is None or target_date <= f.effective_to)
        ]
        if not matches:
            raise SSRAError(
                McpErrorCode.NOT_FOUND,
                f"TaxFact '{key}' not found or not active as of {target_date.isoformat()}",
                status_code=404,
            )
        matches.sort(key=lambda f: f.effective_from, reverse=True)
        return matches[0]

    def list_facts(
        self, *, prefix: str | None = None, as_of: date | None = None
    ) -> list[TaxFactContract]:
        target_date = as_of or juba_today()
        results = [
            f
            for f in self._facts
            if (prefix is None or f.key.startswith(prefix))
            and f.effective_from <= target_date
            and (f.effective_to is None or target_date <= f.effective_to)
        ]
        return sorted(results, key=lambda f: f.key)

    def calculate_paye_estimate(
        self,
        gross_monthly_ssp: Decimal | int | float | str,
        *,
        as_of: date | None = None,
    ) -> PayeEstimateResult:
        target_date = as_of or juba_today()
        gross = Decimal(str(gross_monthly_ssp))
        if gross < Decimal("0"):
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                "gross_monthly_ssp must be non-negative",
                status_code=400,
            )

        b1_max_fact = self.get_fact("paye.bracket.1.max_monthly_ssp", as_of=target_date)
        b1_rate_fact = self.get_fact("paye.bracket.1.rate_percent", as_of=target_date)
        b2_max_fact = self.get_fact("paye.bracket.2.max_monthly_ssp", as_of=target_date)
        b2_rate_fact = self.get_fact("paye.bracket.2.rate_percent", as_of=target_date)
        b3_max_fact = self.get_fact("paye.bracket.3.max_monthly_ssp", as_of=target_date)
        b3_rate_fact = self.get_fact("paye.bracket.3.rate_percent", as_of=target_date)
        b4_rate_fact = self.get_fact("paye.bracket.4.rate_percent", as_of=target_date)
        deadline_fact = self.get_fact("paye.filing.deadline_day", as_of=target_date)

        b1_max = Decimal(b1_max_fact.value)
        b2_max = Decimal(b2_max_fact.value)
        b3_max = Decimal(b3_max_fact.value)

        r1 = Decimal(b1_rate_fact.value)
        r2 = Decimal(b2_rate_fact.value)
        r3 = Decimal(b3_rate_fact.value)
        r4 = Decimal(b4_rate_fact.value)

        band_defs = [
            (1, Decimal("0"), b1_max, r1, b1_rate_fact.key),
            (2, b1_max, b2_max, r2, b2_rate_fact.key),
            (3, b2_max, b3_max, r3, b3_rate_fact.key),
            (4, b3_max, None, r4, b4_rate_fact.key),
        ]

        total_tax = Decimal("0")
        bands: list[PayeBandBreakdown] = []
        for idx, lower, upper, rate_pct, fact_key in band_defs:
            if gross <= lower:
                taxable = Decimal("0")
            elif upper is None:
                taxable = gross - lower
            else:
                taxable = min(gross, upper) - lower

            band_tax = _quantize_ssp(taxable * rate_pct / Decimal("100"))
            total_tax += band_tax
            bands.append(
                PayeBandBreakdown(
                    band_index=idx,
                    taxable_amount_ssp=_format_decimal(taxable),
                    rate_percent=_format_decimal(rate_pct),
                    tax_amount_ssp=_format_decimal(band_tax),
                    rate_fact_key=fact_key,
                )
            )

        total_tax = _quantize_ssp(total_tax)
        net_monthly = _quantize_ssp(gross - total_tax)
        eff_rate = (
            _quantize_ssp((total_tax / gross) * Decimal("100"))
            if gross > Decimal("0")
            else Decimal("0")
        )

        gross_str = _format_decimal(gross)
        tax_str = _format_decimal(total_tax)
        net_str = _format_decimal(net_monthly)
        eff_str = _format_decimal(eff_rate)
        deadline_day = int(deadline_fact.value)

        claims = [
            NumericClaim(
                value=gross_str,
                unit=NumericUnit.SSP,
                source_ref="calculate_paye_estimate.gross_monthly_ssp",
            ),
            NumericClaim(
                value=tax_str,
                unit=NumericUnit.SSP,
                source_ref="calculate_paye_estimate.estimated_tax_ssp",
            ),
            NumericClaim(
                value=net_str,
                unit=NumericUnit.SSP,
                source_ref="calculate_paye_estimate.net_monthly_ssp",
            ),
            NumericClaim(
                value=eff_str,
                unit=NumericUnit.PERCENT,
                source_ref="calculate_paye_estimate.effective_rate_percent",
            ),
            NumericClaim(
                value=str(deadline_day),
                unit=NumericUnit.DAY_OF_MONTH,
                source_ref=deadline_fact.key,
            ),
        ]

        return PayeEstimateResult(
            gross_monthly_ssp=gross_str,
            estimated_tax_ssp=tax_str,
            net_monthly_ssp=net_str,
            effective_rate_percent=eff_str,
            filing_deadline_day=deadline_day,
            snapshot_version=self._snapshot_version,
            as_of=target_date,
            legal_ref=b2_rate_fact.legal_ref,
            bands=bands,
            numeric_claims=claims,
        )

    def calculate_withholding_estimate(
        self,
        gross_amount_ssp: Decimal | int | float | str,
        category: WithholdingCategory = "goods_and_services",
        *,
        as_of: date | None = None,
    ) -> WithholdingEstimateResult:
        target_date = as_of or juba_today()
        gross = Decimal(str(gross_amount_ssp))
        if gross < Decimal("0"):
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                "gross_amount_ssp must be non-negative",
                status_code=400,
            )

        fact_key = f"wht.{category}.rate_percent"
        rate_fact = self.get_fact(fact_key, as_of=target_date)
        rate_pct = Decimal(rate_fact.value)
        wht_ssp = _quantize_ssp(gross * rate_pct / Decimal("100"))
        net_ssp = _quantize_ssp(gross - wht_ssp)

        gross_str = _format_decimal(gross)
        rate_str = _format_decimal(rate_pct)
        wht_str = _format_decimal(wht_ssp)
        net_str = _format_decimal(net_ssp)

        claims = [
            NumericClaim(
                value=gross_str,
                unit=NumericUnit.SSP,
                source_ref="calculate_withholding_estimate.gross_amount_ssp",
            ),
            NumericClaim(
                value=rate_str,
                unit=NumericUnit.PERCENT,
                source_ref=rate_fact.key,
            ),
            NumericClaim(
                value=wht_str,
                unit=NumericUnit.SSP,
                source_ref="calculate_withholding_estimate.withholding_tax_ssp",
            ),
            NumericClaim(
                value=net_str,
                unit=NumericUnit.SSP,
                source_ref="calculate_withholding_estimate.net_payable_ssp",
            ),
        ]

        return WithholdingEstimateResult(
            category=category,
            gross_amount_ssp=gross_str,
            rate_percent=rate_str,
            withholding_tax_ssp=wht_str,
            net_payable_ssp=net_str,
            snapshot_version=self._snapshot_version,
            as_of=target_date,
            legal_ref=rate_fact.legal_ref,
            rate_fact_key=rate_fact.key,
            numeric_claims=claims,
        )
