"""Unit and Hypothesis property tests for ssra_rules (Section 10.5 mandatory property tests)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from ssra_core import McpErrorCode, SSRAError
from ssra_rules import TaxFactsRegistry


def test_seed_tax_facts_load_and_validate() -> None:
    reg = TaxFactsRegistry.from_yaml_file()
    facts = reg.list_facts(as_of=date(2026, 10, 16))
    assert len(facts) >= 10
    for f in facts:
        assert len(f.legal_ref) >= 5
        assert len(f.approved_by) >= 2


def test_paye_known_values_and_disclaimer() -> None:
    reg = TaxFactsRegistry.from_yaml_file()
    # 50,000 SSP is in the 0% band
    res_exempt = reg.calculate_paye_estimate("50000", as_of=date(2026, 10, 16))
    assert res_exempt.estimated_tax_ssp == "0"
    assert res_exempt.net_monthly_ssp == "50000"
    assert res_exempt.is_estimate is True
    assert "ESTIMATE ONLY" in res_exempt.disclaimer

    # 250,000 SSP:
    # Band 1 (0..50,000 @ 0%) = 0
    # Band 2 (50,000..150,000 = 100,000 @ 10%) = 10,000
    # Band 3 (150,000..250,000 = 100,000 @ 15%) = 15,000
    # Total = 25,000 SSP; Net = 225,000 SSP; Effective rate = 10%
    res_250k = reg.calculate_paye_estimate("250000", as_of=date(2026, 10, 16))
    assert res_250k.estimated_tax_ssp == "25000"
    assert res_250k.net_monthly_ssp == "225000"
    assert res_250k.effective_rate_percent == "10"
    assert res_250k.filing_deadline_day == 15


@given(
    g1=st.decimals(min_value=Decimal("0"), max_value=Decimal("100000000"), places=2),
    delta=st.decimals(min_value=Decimal("0"), max_value=Decimal("10000000"), places=2),
)
def test_paye_monotonicity_and_accounting_identity(g1: Decimal, delta: Decimal) -> None:
    reg = TaxFactsRegistry.from_yaml_file()
    g2 = g1 + delta
    r1 = reg.calculate_paye_estimate(g1, as_of=date(2026, 10, 16))
    r2 = reg.calculate_paye_estimate(g2, as_of=date(2026, 10, 16))

    t1 = Decimal(r1.estimated_tax_ssp)
    t2 = Decimal(r2.estimated_tax_ssp)
    n1 = Decimal(r1.net_monthly_ssp)
    n2 = Decimal(r2.net_monthly_ssp)

    # Tax is non-negative, bounded by gross, and monotonically non-decreasing
    assert Decimal("0") <= t1 <= g1
    assert t2 >= t1
    # Net income is also monotonically non-decreasing (marginal rate <= 20% < 100%)
    assert n2 >= n1
    # Exact accounting identity: gross == tax + net
    assert t1 + n1 == g1
    assert t2 + n2 == g2


@given(
    amount=st.decimals(min_value=Decimal("0"), max_value=Decimal("100000000"), places=2),
    cat=st.sampled_from(
        [
            "goods_and_services",
            "rent",
            "technical_fees",
            "government_contractors_resident",
            "government_contractors_non_resident",
            "mobile_money_commissions",
            "end_of_service_benefits",
        ]
    ),
)
def test_withholding_accounting_identity(amount: Decimal, cat: str) -> None:
    reg = TaxFactsRegistry.from_yaml_file()
    res = reg.calculate_withholding_estimate(
        amount,
        category=cat,  # type: ignore[arg-type]
        as_of=date(2026, 10, 16),
    )
    tax = Decimal(res.withholding_tax_ssp)
    net = Decimal(res.net_payable_ssp)
    assert Decimal("0") <= tax <= amount
    assert tax + net == amount


def test_financial_act_2024_2025_rates_in_registry() -> None:
    reg = TaxFactsRegistry.from_yaml_file()
    as_of = date(2026, 10, 16)
    assert reg.get_fact("bpt.standard.rate_percent", as_of=as_of).value == "30"
    assert reg.get_fact("bpt.imported_goods_advance.rate_percent", as_of=as_of).value == "4"
    assert (
        reg.get_fact("wht.government_contractors_resident.rate_percent", as_of=as_of).value == "15"
    )
    assert (
        reg.get_fact("wht.government_contractors_non_resident.rate_percent", as_of=as_of).value
        == "20"
    )
    assert reg.get_fact("wht.mobile_money_commissions.rate_percent", as_of=as_of).value == "10"
    assert reg.get_fact("excise.beer_2203.rate_percent", as_of=as_of).value == "50"
    assert reg.get_fact("excise.passenger_cars_8703.rate_percent", as_of=as_of).value == "25"
    assert reg.get_fact("customs.exports_ch99.rate_percent", as_of=as_of).value == "18"
    assert reg.get_fact("gaming.gross_gaming_tax.rate_percent", as_of=as_of).value == "24"
    assert reg.get_fact("pit.nsif_pension_deduction.rate_percent", as_of=as_of).value == "8"
    assert reg.get_fact("bpt.depreciation.cat1_buildings.rate_percent", as_of=as_of).value == "10"
    assert (
        reg.get_fact("bpt.depreciation.cat2_vehicles_computers.rate_percent", as_of=as_of).value
        == "33"
    )
    assert (
        reg.get_fact("bpt.depreciation.cat3_other_property.rate_percent", as_of=as_of).value == "25"
    )
    assert reg.get_fact("customs.passenger_baggage_exemption.max_usd", as_of=as_of).value == "500"
    assert reg.get_fact("penalty.late_filing_or_payment.rate_percent", as_of=as_of).value == "5"
    assert reg.get_fact("filing.extension.max_months", as_of=as_of).value == "2"
    assert reg.get_fact("payment.installment.max_months", as_of=as_of).value == "6"
    assert reg.get_fact("etax.filing_and_einvoice.fee_ssp", as_of=as_of).value == "0"


def test_negative_amounts_rejected() -> None:
    reg = TaxFactsRegistry.from_yaml_file()
    with pytest.raises(SSRAError) as exc_info:
        reg.calculate_paye_estimate("-100")
    assert exc_info.value.code == McpErrorCode.VALIDATION_FAILED

    with pytest.raises(SSRAError) as wht_exc:
        reg.calculate_withholding_estimate("-50")
    assert wht_exc.value.code == McpErrorCode.VALIDATION_FAILED

    with pytest.raises(SSRAError) as nf_exc:
        reg.get_fact("unknown.tax.fact.key")
    assert nf_exc.value.code == McpErrorCode.NOT_FOUND


def test_overlapping_tax_fact_effective_date_ranges_rejected() -> None:
    from ssra_core import TaxFactContract

    f1 = TaxFactContract(
        key="paye.bracket.2.rate_percent",
        value="10",
        unit="PERCENT",
        currency="NONE",
        applies_to="Band 2",
        effective_from=date(2024, 7, 1),
        effective_to=date(2025, 6, 30),
        legal_ref="Taxation Act 2009",
        approved_by="SSRA Legal",
        version="2026.10.1",
    )
    f2_overlapping = TaxFactContract(
        key="paye.bracket.2.rate_percent",
        value="12",
        unit="PERCENT",
        currency="NONE",
        applies_to="Band 2",
        effective_from=date(2025, 1, 1),
        effective_to=None,
        legal_ref="Taxation Act 2009",
        approved_by="SSRA Legal",
        version="2026.10.1",
    )
    with pytest.raises(SSRAError) as ov_exc:
        TaxFactsRegistry(facts=[f1, f2_overlapping], snapshot_version="2026.10.1")
    assert ov_exc.value.code == McpErrorCode.VALIDATION_FAILED


def test_tax_fact_end_before_start_rejected() -> None:
    from ssra_core import TaxFactContract

    invalid = TaxFactContract(
        key="paye.bracket.2.rate_percent",
        value="10",
        unit="PERCENT",
        currency="NONE",
        applies_to="Band 2",
        effective_from=date(2025, 1, 1),
        effective_to=date(2024, 12, 31),
        legal_ref="Taxation Act 2009",
        approved_by="SSRA Legal",
        version="2026.10.1",
    )

    with pytest.raises(SSRAError) as exc_info:
        TaxFactsRegistry(facts=[invalid], snapshot_version="2026.10.1")

    assert exc_info.value.code == McpErrorCode.VALIDATION_FAILED
