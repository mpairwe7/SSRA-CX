"""Knowledge retrieval adapter backed by published seed snapshot with temporal supersession filtering."""

from __future__ import annotations

import functools
import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from ssra_core import McpErrorCode, SSRAError, expand_ssra_nra_synonyms, juba_today

_SEED_CORPUS = Path(__file__).resolve().parents[4] / "knowledge" / "corpus" / "seed-documents.json"
_SOURCES_YAML = Path(__file__).resolve().parents[4] / "knowledge" / "sources.yaml"


@functools.lru_cache(maxsize=4)
def _load_cached_corpus_and_sources(
    corpus_file: Path, sources_file: Path
) -> tuple[str, tuple[dict[str, Any], ...], dict[str, dict[str, Any]]]:
    raw = json.loads(corpus_file.read_text(encoding="utf-8"))
    snapshot_version = str(raw.get("snapshot_version", "2026.10.1"))
    chunks = tuple(raw.get("chunks", []))
    sources_by_id: dict[str, dict[str, Any]] = {}
    if sources_file.exists():
        src_raw = yaml.safe_load(sources_file.read_text(encoding="utf-8")) or {}
        for s in src_raw.get("sources", []):
            if isinstance(s, dict) and "id" in s:
                sources_by_id[str(s["id"])] = s
    return snapshot_version, chunks, sources_by_id


class KnowledgeCorpusAdapter:
    def __init__(self, corpus_path: Path | None = None, sources_path: Path | None = None) -> None:
        target = (corpus_path or _SEED_CORPUS).resolve()
        src_file = (sources_path or _SOURCES_YAML).resolve()
        snap_ver, chunks, sources_by_id = _load_cached_corpus_and_sources(target, src_file)
        self.snapshot_version: str = snap_ver
        self._chunks: list[dict[str, Any]] = list(chunks)
        self._sources_by_id: dict[str, dict[str, Any]] = dict(sources_by_id)

    def is_temporally_valid(self, chk: dict[str, Any], as_of: date) -> bool:
        """Enforce bi-temporal validity & supersession filtering (MemStrata arXiv:2606.26511)."""
        eff_from_str = chk.get("effective_from")
        if eff_from_str and date.fromisoformat(str(eff_from_str)) > as_of:
            return False
        eff_to_str = chk.get("effective_to")
        if eff_to_str and date.fromisoformat(str(eff_to_str)) < as_of:
            return False

        doc_id = str(chk.get("doc_id", ""))
        src = self._sources_by_id.get(doc_id)
        if src is not None:
            if src.get("approval_state") != "PUBLISHED":
                return False
            s_from = src.get("effective_from")
            if s_from and date.fromisoformat(str(s_from)) > as_of:
                return False
            s_to = src.get("effective_to")
            if s_to and date.fromisoformat(str(s_to)) < as_of:
                return False
        return True

    def search_knowledge(
        self,
        *,
        query: str,
        language: str = "en",
        top_k: int = 3,
        as_of: date | None = None,
    ) -> list[dict[str, Any]]:
        target_date = as_of or juba_today()
        expanded_q = expand_ssra_nra_synonyms(query).lower()
        terms = [t for t in expanded_q.replace("?", " ").replace(",", " ").split() if len(t) >= 2]

        scored: list[tuple[int, dict[str, Any]]] = []
        is_tin_faq_query = any(
            k in expanded_q
            for k in (
                "expire",
                "confidential",
                "cancel",
                "two tins",
                "legal status",
                "تنتهي صلاحية",
                "سرية",
                "bikhlas",
                "sirri",
            )
        )
        is_tin_query = (
            any(
                k in expanded_q
                for k in ("tin", "tasjil", "register", "الرقم الضريبي", "الرقم التعريفي")
            )
            and not is_tin_faq_query
        )
        is_tcc_query = any(
            k in expanded_q
            for k in (
                "tcc",
                "tax compliance certificate",
                "tax clearance certificate",
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
                "passenger baggage",
            )
        )
        is_bpt_query = any(
            k in expanded_q
            for k in (
                "business profit tax",
                "bpt",
                "advance bpt",
                "rental investment",
                "ضريبة أرباح الأعمال",
                "dariba ta arbah",
            )
        )
        is_wht_query = any(
            k in expanded_q
            for k in (
                "withholding tax",
                "government contractor",
                "mobile money commission",
                "end of service",
                "eosb",
            )
        )
        is_excise_query = any(
            k in expanded_q
            for k in ("excise", "beer", "cigarettes", "tobacco", "perfumes", "passenger cars")
        )
        is_support_tools_query = any(
            k in expanded_q
            for k in ("support@nra.gov.ss", "e-invoice-search", "helpdesk", "918806493")
        )
        is_einvoice_query = any(
            k in expanded_q for k in ("b2b e-invoice", "e-invoice", "qr code", "purchases")
        )
        is_filing_manual_query = any(
            k in expanded_q
            for k in ("forgot your tin", "excel", "tax-code template", "switch between")
        )
        is_ecustoms_manual_query = any(
            k in expanded_q
            for k in (
                "customs.eservices.gov.ss",
                "ecustoms",
                "sad form 17a",
                "release note",
                "declaration stages",
                "customs declaration",
            )
        )
        is_faq_penalty_query = any(
            k in expanded_q
            for k in (
                "installment",
                "extension",
                "late filing",
                "late payment",
                "underestimation",
                "penalty",
                "غرامة التأخير",
                "gharama",
            )
        )
        is_depreciation_query = any(
            k in expanded_q
            for k in (
                "depreciation",
                "tangible property",
                "intangible property",
                "15 april",
                "quarterly advance",
            )
        )
        is_pit_nsif_query = any(
            k in expanded_q
            for k in ("nsif", "social insurance", "pension deduction", "diplomatic", "8%")
        )

        for chk in self._chunks:
            if not self.is_temporally_valid(chk, target_date):
                continue
            haystack = f"{chk['doc_title']} {chk['section_anchor']} {chk['content']}".lower()
            score = sum(3 if t in haystack else 0 for t in terms)
            anchor = str(chk.get("section_anchor", ""))
            if is_tin_faq_query and "FAQs-TIN-Validity-Confidentiality" in anchor:
                score += 18
            if (
                is_tin_query
                and "TIN-Registration" in anchor
                and not is_tcc_query
                and not is_ecustoms_manual_query
                and not is_einvoice_query
            ):
                score += 12
            if is_tcc_query and "TCC" in anchor:
                score += 14
            if (
                is_customs_query
                and "Customs-Valuation-FX" in anchor
                and not is_ecustoms_manual_query
            ):
                score += 14
            if is_bpt_query and "Business-Profit-Tax" in anchor:
                score += 14
            if is_wht_query and "Withholding-Tax" in anchor:
                score += 14
            if is_excise_query and "Excise-Tax-Schedule" in anchor:
                score += 14
            if is_support_tools_query and "Official-Support-And-Verification-Tools" in anchor:
                score += 14
            if is_einvoice_query and "B2B-EInvoice" in anchor:
                score += 16
            if is_filing_manual_query and "Declaration-And-Filing" in anchor:
                score += 16
            if is_ecustoms_manual_query and "eCustoms-Declaration" in anchor:
                score += 18
            if is_faq_penalty_query and "Penalties-Extensions-And-Installments" in anchor:
                score += 18
            if is_depreciation_query and "Depreciation-And-Quarterly-Advance-Tax" in anchor:
                score += 18
            if is_pit_nsif_query and "PIT-Exemptions-And-8-Percent-NSIF" in anchor:
                score += 18
            if chk.get("language") == language and score > 0:
                score += 15
            if score > 0:
                scored.append((score, chk))

        scored.sort(key=lambda item: item[0], reverse=True)
        if not scored:
            fallback = [
                c
                for c in self._chunks
                if c.get("language") == language and self.is_temporally_valid(c, target_date)
            ]
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

    def get_document_section(self, *, chunk_id: str) -> dict[str, Any]:
        return self.get_section(section_anchor=chunk_id)

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
            {
                "form_code": "ECUSTOMS-SAD-17A",
                "title": "eCustoms Single Administrative Document (SAD Form 17A) Declaration",
                "portal_url": "https://customs.eservices.gov.ss/",
            },
        ]

    def get_office_info(self, *, office_code: str = "JUBA_HQ") -> dict[str, Any]:
        """Return official SSRA office metadata and Africa/Juba operating hours by office_code."""
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
                "portal_url": "https://customs.eservices.gov.ss/",
            },
            "WAU_BRANCH": {
                "office_code": "WAU_BRANCH",
                "name": "SSRA Western Bahr el Ghazal Regional Tax Office — Wau",
                "city": "Wau",
                "timezone": "Africa/Juba (UTC+02:00)",
                "hours": "Monday–Friday, 08:00–17:00 EAT",
                "portal_url": "https://etax.nra.gov.ss/",
            },
            "MALAKAL_BRANCH": {
                "office_code": "MALAKAL_BRANCH",
                "name": "SSRA Upper Nile Regional Tax Office — Malakal",
                "city": "Malakal",
                "timezone": "Africa/Juba (UTC+02:00)",
                "hours": "Monday–Friday, 08:00–17:00 EAT",
                "portal_url": "https://etax.nra.gov.ss/",
            },
        }
        office = offices.get(office_code.strip().upper())
        if office is None:
            raise SSRAError(
                McpErrorCode.NOT_FOUND,
                f"Office '{office_code}' not found in SSRA directory",
                status_code=404,
            )
        return office
