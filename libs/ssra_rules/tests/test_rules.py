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
    cat=st.sampled_from(["goods_and_services", "rent", "technical_fees"]),
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
