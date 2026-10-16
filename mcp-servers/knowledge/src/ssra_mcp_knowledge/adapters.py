"""Knowledge retrieval adapter backed by published seed snapshot (and Postgres + pgvector in stack)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ssra_core import McpErrorCode, SSRAError, expand_ssra_nra_synonyms

_SEED_CORPUS = Path(__file__).resolve().parents[4] / "knowledge" / "corpus" / "seed-documents.json"


class KnowledgeCorpusAdapter:
    def __init__(self, corpus_path: Path | None = None) -> None:
        target = corpus_path or _SEED_CORPUS
        raw = json.loads(target.read_text(encoding="utf-8"))
        self.snapshot_version: str = str(raw.get("snapshot_version", "2026.10.1"))
        self._chunks: list[dict[str, Any]] = list(raw.get("chunks", []))

    def search_knowledge(
        self,
        *,
        query: str,
        language: str = "en",
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        expanded_q = expand_ssra_nra_synonyms(query).lower()
        terms = [t for t in expanded_q.replace("?", " ").replace(",", " ").split() if len(t) >= 2]

        scored: list[tuple[int, dict[str, Any]]] = []
        is_tin_query = any(
            k in expanded_q
            for k in ("tin", "tasjil", "register", "الرقم الضريبي", "الرقم التعريفي")
        )
        is_tcc_query = any(
            k in expanded_q
            for k in (
                "tcc",
                "tax compliance certificate",
                "شهادة الامتثال",
                "shahada ta imtisal",
            )
        )
        is_customs_query = any(
            k in expanded_q
            for k in (
                "customs",
                "exchange rate",
                "boss",
                "جمارك",
                "سعر الصرف",
                "gamarik",
                "accreditation permit",
                "trade.eservices.gov.ss",
            )
        )
        is_bpt_query = any(
            k in expanded_q
            for k in ("business profit tax", "bpt", "advance bpt", "rental investment")
        )
        is_excise_query = any(
            k in expanded_q for k in ("excise", "beer", "cigarettes", "tobacco", "perfumes")
        )
        is_support_tools_query = any(
            k in expanded_q
            for k in ("support@nra.gov.ss", "e-invoice-search", "helpdesk", "918806493")
        )
        is_einvoice_query = any(
            k in expanded_q for k in ("b2b e-invoice", "e-invoice", "qr code", "purchases")
        )
        is_ecustoms_manual_query = any(
            k in expanded_q
            for k in (
                "customs.eservices.gov.ss",
                "ecustoms",
                "sad form 17a",
                "release note",
                "declaration stages",
            )
        )
        is_faq_penalty_query = any(
            k in expanded_q
            for k in ("installment", "extension", "late filing", "late payment", "underestimation")
        )
        is_depreciation_query = any(
            k in expanded_q
            for k in ("depreciation", "tangible property", "intangible property", "15 april")
        )
        for chk in self._chunks:
            haystack = f"{chk['doc_title']} {chk['section_anchor']} {chk['content']}".lower()
            score = sum(3 if t in haystack else 0 for t in terms)
            anchor = str(chk.get("section_anchor", ""))
            if is_tin_query and "TIN-Registration" in anchor and not is_tcc_query:
                score += 12
            if is_tcc_query and "TCC" in anchor:
                score += 14
            if is_customs_query and "Customs-Valuation-FX" in anchor:
                score += 14
            if is_bpt_query and "Business-Profit-Tax" in anchor:
                score += 14
            if is_excise_query and "Excise-Tax-Schedule" in anchor:
                score += 14
            if is_support_tools_query and "Official-Support-And-Verification-Tools" in anchor:
                score += 14
            if is_einvoice_query and "B2B-EInvoice" in anchor:
                score += 14
            if is_ecustoms_manual_query and "eCustoms-Declaration" in anchor:
                score += 14
            if is_faq_penalty_query and "Penalties-Extensions-And-Installments" in anchor:
                score += 14
            if is_depreciation_query and "Depreciation-And-Quarterly-Advance-Tax" in anchor:
                score += 14
            if chk.get("language") == language and score > 0:
                score += 15
            if score > 0:
                scored.append((score, chk))

        scored.sort(key=lambda item: item[0], reverse=True)
        if not scored:
            # Fallback to language-matched chunks if query had non-overlapping script tokens
            fallback = [c for c in self._chunks if c.get("language") == language]
            return fallback[:top_k] if fallback else self._chunks[:1]
        return [item[1] for item in scored[:top_k]]

    def get_section(self, *, section_anchor: str) -> dict[str, Any]:
        for chk in self._chunks:
            if chk["section_anchor"] == section_anchor or chk["id"] == section_anchor:
                return chk
        raise SSRAError(
            McpErrorCode.NOT_FOUND,
            f"Knowledge section '{section_anchor}' not found in published snapshot {self.snapshot_version}",
            status_code=404,
        )

    def list_forms(self) -> list[dict[str, str]]:
        return [
            {
                "form_code": "ETAX-TIN-01",
                "title": "Online TIN Registration Application (Individual / Business / NGO)",
                "portal_url": "https://etax.nra.gov.ss/",
            },
            {
                "form_code": "ETAX-PAYE-M01",
                "title": "Monthly Personal Income Tax (PAYE) Return",
                "portal_url": "https://etax.nra.gov.ss/",
            },
            {
                "form_code": "ETAX-TCC-01",
                "title": "Tax Compliance Certificate (TCC) Electronic Application",
                "portal_url": "https://etax.nra.gov.ss/",
            },
        ]

    def get_office_info(self, *, office_code: str = "JUBA_HQ") -> dict[str, Any]:
        offices = {
            "JUBA_HQ": {
                "office_code": "JUBA_HQ",
                "name": "SSRA Headquarters & Domestic Tax Office — Juba",
                "city": "Juba",
                "timezone": "Africa/Juba (UTC+02:00)",
                "hours": "Monday–Friday, 08:00–17:00 EAT",
                "portal_url": "https://etax.nra.gov.ss/",
            },
            "NIMULE_CUSTOMS": {
                "office_code": "NIMULE_CUSTOMS",
                "name": "SSRA Nimule Border Customs Station",
                "city": "Nimule",
                "timezone": "Africa/Juba (UTC+02:00)",
                "hours": "Daily border operations (Administrative desk Mon–Fri 08:00–17:00 EAT)",
                "portal_url": "https://etax.nra.gov.ss/",
            },
        }
        office = offices.get(office_code.upper())
        if office is None:
            raise SSRAError(
                McpErrorCode.NOT_FOUND,
                f"Office '{office_code}' not found in SSRA directory",
                status_code=404,
            )
        return office
