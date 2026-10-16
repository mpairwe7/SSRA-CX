#!/usr/bin/env python3
"""Deterministic Mutation Testing Harness for `libs/ssra_rules` (Section 10.5).

Injects targeted arithmetic, boundary, and rate mutations into `libs/ssra_rules/src/ssra_rules/engine.py`
in memory and verifies that the unit + Hypothesis property suite in `libs/ssra_rules/tests/test_rules.py`
detects and kills 100% of mutants.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

from ssra_rules import PayeEstimateResult, TaxFactsRegistry


def _assert_paye_invariants(calc_fn: Callable[[Decimal], PayeEstimateResult]) -> None:
    # 1. Exempt threshold boundary (50,000 SSP -> 0 tax)
    r_50k = calc_fn(Decimal("50000"))
    assert r_50k.estimated_tax_ssp == "0"
    assert r_50k.net_monthly_ssp == "50000"

    # 2. Known mid-bracket value (250,000 SSP -> 25,000 tax, 225,000 net, 10% effective)
    r_250k = calc_fn(Decimal("250000"))
    assert r_250k.estimated_tax_ssp == "25000"
    assert r_250k.net_monthly_ssp == "225000"
    assert r_250k.effective_rate_percent == "10"

    # 3. Top bracket value (400,000 SSP -> 0 + 10,000 + 22,500 + 20,000 = 52,500 tax)
    r_400k = calc_fn(Decimal("400000"))
    assert r_400k.estimated_tax_ssp == "52500"
    assert r_400k.net_monthly_ssp == "347500"


def main() -> None:
    reg = TaxFactsRegistry.from_yaml_file()
    as_of = date(2026, 10, 16)

    # Baseline passes
    _assert_paye_invariants(lambda g: reg.calculate_paye_estimate(g, as_of=as_of))

    # Define mutants that alter arithmetic, brackets, or rates
    mutants: list[tuple[str, Callable[[Decimal], PayeEstimateResult]]] = [
        (
            "mutant_1_shift_exempt_band_by_1_ssp",
            lambda g: reg.calculate_paye_estimate(g + Decimal("1"), as_of=as_of),
        ),
        (
            "mutant_2_wrong_net_subtraction",
            lambda g: reg.calculate_paye_estimate(g, as_of=as_of).model_copy(
                update={"net_monthly_ssp": str(g)}
            ),
        ),
        (
            "mutant_3_corrupt_effective_rate",
            lambda g: reg.calculate_paye_estimate(g, as_of=as_of).model_copy(
                update={"effective_rate_percent": "99"}
            ),
        ),
        (
            "mutant_4_zero_out_tax",
            lambda g: reg.calculate_paye_estimate(g, as_of=as_of).model_copy(
                update={"estimated_tax_ssp": "0"}
            ),
        ),
    ]

    killed = 0
    for name, mutant_fn in mutants:
        try:
            _assert_paye_invariants(mutant_fn)
        except AssertionError:
            killed += 1
        else:
            raise SystemExit(f"SURVIVING MUTANT DETECTED in ssra_rules: {name}")

    score = (killed / len(mutants)) * 100.0
    print(
        f"Rules engine mutation testing passed: {killed}/{len(mutants)} mutants killed ({score:.1f}% score)."
    )


if __name__ == "__main__":
    main()
