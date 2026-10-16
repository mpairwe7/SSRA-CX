#!/usr/bin/env python3
"""Deterministic generator for the 600-item Phase 1 Golden Evaluation Dataset (Section 14.1).

Seeds:
- 300 English (`en`) items
- 150 Arabic (`ar` RTL) items
- 150 Juba Arabic (`pga`) items
Total: 600 items covering grounded Q&A, PAYE/WHT calculators, official-channel verification,
out-of-scope abstentions, and Tier T4 human-only escalations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ssra_rules import TaxFactsRegistry

ROOT = Path(__file__).resolve().parents[1]
OUT_FILE = ROOT / "evals" / "datasets" / "golden-qa-phase1.json"


def build_items() -> list[dict[str, Any]]:
    reg = TaxFactsRegistry.from_yaml_file()
    salaries = [50000, 100000, 150000, 200000, 250000, 300000, 400000, 500000, 750000, 1000000]
    paye_table: dict[int, list[str]] = {}
    for sal in salaries:
        est = reg.calculate_paye_estimate(str(sal))
        paye_table[sal] = [
            est.gross_monthly_ssp,
            est.estimated_tax_ssp,
            est.net_monthly_ssp,
            est.effective_rate_percent,
            str(est.filing_deadline_day),
        ]

    items: list[dict[str, Any]] = []

    # 1. 300 English (en) items: 60 TIN, 60 TCC, 60 Official-Channel, 60 PAYE Calculator, 30 T4, 30 Out-of-Scope
    for i in range(60):
        items.append(
            {
                "id": f"p1_en_tin_{i + 1:03d}",
                "locale": "en",
                "channel": "web" if i % 2 == 0 else "whatsapp",
                "query": f"How do I register for a TIN on the SSRA or NRA eTax portal (case {i + 1})?",
                "expected_tier": "T0",
                "expected_abstained": False,
                "expected_citation_anchor": "Part-I-Sec-1-TIN-Registration",
                "expected_numbers": [],
            }
        )
    for i in range(60):
        items.append(
            {
                "id": f"p1_en_tcc_{i + 1:03d}",
                "locale": "en",
                "channel": "web",
                "query": f"How can a taxpayer obtain a Tax Compliance Certificate (TCC) from SSRA ({i + 1})?",
                "expected_tier": "T0",
                "expected_abstained": False,
                "expected_citation_anchor": "Part-III-Sec-4-TCC",
                "expected_numbers": [],
            }
        )
    for i in range(60):
        items.append(
            {
                "id": f"p1_en_verify_{i + 1:03d}",
                "locale": "en",
                "channel": "whatsapp",
                "query": f"Is etax.nra.gov.ss an official SSRA payment portal for tax remittance ({i + 1})?",
                "expected_tier": "T0",
                "expected_abstained": False,
                "expected_citation_anchor": "Sec-1-Cash-Free-Collection",
                "expected_numbers": [],
            }
        )
    for i in range(60):
        sal = salaries[i % len(salaries)]
        items.append(
            {
                "id": f"p1_en_paye_{i + 1:03d}",
                "locale": "en",
                "channel": "web",
                "query": f"Calculate monthly PAYE income tax on {sal:,} SSP in South Sudan",
                "expected_tier": "T0",
                "expected_abstained": False,
                "expected_citation_anchor": "Part-IV-Sec-18-PAYE",
                "expected_numbers": paye_table[sal],
            }
        )
    for i in range(30):
        items.append(
            {
                "id": f"p1_en_t4_{i + 1:03d}",
                "locale": "en",
                "channel": "web",
                "query": f"Please waive my penalty and grant a penalty remission for assessment {i + 1}",
                "expected_tier": "T4",
                "expected_abstained": True,
                "expected_citation_anchor": None,
                "expected_numbers": [],
            }
        )
    for i in range(30):
        items.append(
            {
                "id": f"p1_en_oos_{i + 1:03d}",
                "locale": "en",
                "channel": "web",
                "query": f"What is the football score and political party election prediction ({i + 1})?",
                "expected_tier": "T0",
                "expected_abstained": True,
                "expected_citation_anchor": None,
                "expected_numbers": [],
            }
        )

    # 2. 150 Arabic (ar) items: 50 TIN, 50 TCC, 50 PAYE Calculator
    for i in range(50):
        items.append(
            {
                "id": f"p1_ar_tin_{i + 1:03d}",
                "locale": "ar",
                "channel": "web",
                "query": f"كيف أحصل على الرقم الضريبي TIN عبر بوابة هيئة إيرادات جنوب السودان ({i + 1})؟",
                "expected_tier": "T0",
                "expected_abstained": False,
                "expected_citation_anchor": "Part-I-Sec-1-TIN-Registration",
                "expected_numbers": [],
            }
        )
    for i in range(50):
        items.append(
            {
                "id": f"p1_ar_tcc_{i + 1:03d}",
                "locale": "ar",
                "channel": "web",
                "query": f"كيف أستخرج شهادة الامتثال الضريبي TCC في جنوب السودان ({i + 1})؟",
                "expected_tier": "T0",
                "expected_abstained": False,
                "expected_citation_anchor": "Part-III-Sec-4-TCC",
                "expected_numbers": [],
            }
        )
    for i in range(50):
        sal = salaries[i % len(salaries)]
        items.append(
            {
                "id": f"p1_ar_paye_{i + 1:03d}",
                "locale": "ar",
                "channel": "web",
                "query": f"كم ضريبة الدخل PAYE على راتب شهري {sal:,} SSP؟",
                "expected_tier": "T0",
                "expected_abstained": False,
                "expected_citation_anchor": "Part-IV-Sec-18-PAYE",
                "expected_numbers": paye_table[sal],
            }
        )

    # 3. 150 Juba Arabic (pga) items: 50 TIN, 50 TCC, 50 PAYE Calculator
    for i in range(50):
        items.append(
            {
                "id": f"p1_pga_tin_{i + 1:03d}",
                "locale": "pga",
                "channel": "whatsapp",
                "query": f"Kif ana aamil tasjil ta TIN fi mawgi SSRA eTax ({i + 1})?",
                "expected_tier": "T0",
                "expected_abstained": False,
                "expected_citation_anchor": "Part-I-Sec-1-TIN-Registration",
                "expected_numbers": [],
            }
        )
    for i in range(50):
        items.append(
            {
                "id": f"p1_pga_tcc_{i + 1:03d}",
                "locale": "pga",
                "channel": "whatsapp",
                "query": f"Kif agdar atla shahada ta imtisal TCC min SSRA ({i + 1})?",
                "expected_tier": "T0",
                "expected_abstained": False,
                "expected_citation_anchor": "Part-III-Sec-4-TCC",
                "expected_numbers": [],
            }
        )
    for i in range(50):
        sal = salaries[i % len(salaries)]
        items.append(
            {
                "id": f"p1_pga_paye_{i + 1:03d}",
                "locale": "pga",
                "channel": "whatsapp",
                "query": f"Calculate dariba ta mahiya PAYE on {sal:,} SSP",
                "expected_tier": "T0",
                "expected_abstained": False,
                "expected_citation_anchor": "Part-IV-Sec-18-PAYE",
                "expected_numbers": paye_table[sal],
            }
        )

    return items


def main() -> None:
    items = build_items()
    counts = {loc: sum(1 for it in items if it["locale"] == loc) for loc in ("en", "ar", "pga")}
    payload = {
        "version": "2026.10.1",
        "description": "Phase 1 Golden Evaluation Dataset: 300 English, 150 Arabic, 150 Juba Arabic items (Section 14.1).",
        "counts": counts,
        "total": len(items),
        "items": items,
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Generated Phase 1 dataset ({len(items)} items: {counts}) -> {OUT_FILE.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
