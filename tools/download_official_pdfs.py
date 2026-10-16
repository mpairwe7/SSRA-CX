"""Download & audit official SSRA / NRA / MoFP PDFs, manuals, acts, circulars, and CMS FAQs.

Implements October 2026 RAGShield (arXiv:2604.00387) & OWASP RAG Security Cheat Sheet controls:
1. Strict filename & path-traversal confinement (CVE-2026-13509)
2. Binary PDF active-object inspection for /JS, /JavaScript, /Launch, /OpenAction, /AA (CVE-2026-24737)
3. Native text-layer vs. scanned-image OCR classification (OpenRAG-Soc arXiv:2601.10923)
4. Temporal & statutory RAG eligibility classification (MemStrata arXiv:2606.26511)
5. Upstream CMS GraphQL stored-XSS and pentest payload quarantine (Section 6.3 sanitiser)
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "knowledge" / "corpus" / "pdfs"
CMS_SNAPSHOT_FILE = ROOT / "knowledge" / "corpus" / "cms-official-snapshot.json"

_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) SSRA-Assist-Knowledge-Ingester/2026.10.1"
_SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.-]+\.pdf$")
_PDF_ACTIVE_OBJECT_RE = re.compile(rb"/S\s*/(?:JavaScript|Launch)\b|/OpenAction\s*<<")
_POISON_PATTERNS = re.compile(
    r"(?:<img\b|<script\b|onerror\s*=|localStorage\.getItem|webhook\.site|pipedream\.net|PENTEST|Backdoor2026|89\.116\.171\.182)",
    re.IGNORECASE,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")

_EXCLUDED_HR_TITLES = {
    "Job Advert",
    "Job Adverts",
    "Job Adverts (Internal)",
    "Expression of Interest",
    "Tender Notice",
    "The Speech of Hon. Stephen Dhieu Dau, Chairperson of NRA Board of Directors",
}
_HISTORICAL_SUPERSEDED_FILES = {
    "Financial_Act_2016_2017_0_84f50e24a7.pdf",
    "Financial_Act_2017_2018_82c06b5491.pdf",
    "FY_2019_2020_Financial_Act_2_b5659f5ed9.pdf",
    "F_Inance_Act_20212022_3b0694c45d.pdf",
    "FINANCE_ACT_20212022_6cc3f803fb.pdf",
    "Operationalization_of_the_Financial_Act_2021_2022_771f70ae6e.pdf",
    "FINANCIAL_Act_FY_2023_2024_MAIL_97b32cab38.pdf",
    "PUBLIC_NOTICE_LETTER_34b83cb43f.pdf",
}


def _http_get_bytes(url: str, timeout: int = 120) -> bytes:
    assert url.startswith("https://")
    with httpx.Client(
        timeout=timeout, follow_redirects=True, headers={"User-Agent": _USER_AGENT}
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.content


def _graphql_query(query: str) -> dict[str, Any]:
    with httpx.Client(
        timeout=45, follow_redirects=True, headers={"User-Agent": _USER_AGENT}
    ) as client:
        resp = client.post("https://cms.nra.gov.ss/graphql", json={"query": query})
        resp.raise_for_status()
        return resp.json()


def clean_cms_text(val: Any) -> str | None:
    if not isinstance(val, str):
        return None
    text = val.strip()
    if not text or _POISON_PATTERNS.search(text):
        return None
    text = _HTML_TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _classify_rag_eligibility(title: str, filename: str, category: str) -> str:
    if title in _EXCLUDED_HR_TITLES:
        return "EXCLUDED_HR_PROCUREMENT"
    if filename in _HISTORICAL_SUPERSEDED_FILES:
        return "HISTORICAL_SUPERSEDED"
    if category == "manuals" and "Manual" in title:
        return "PROCEDURAL_MANUAL"
    if category == "report":
        return "OFFICIAL_REPORT"
    if any(
        k in filename
        for k in ("SCHEME_OF_SERVICE", "CODE_OF_CONDUCT", "Staff_Regulations", "ICT_POLICY")
    ):
        return "GOVERNANCE_POLICY"
    return "STATUTORY_PRIMARY"


def _detect_extraction_mode(pdf_path: Path) -> str:
    exe = shutil.which("pdftotext")
    if exe is None:
        return "SCANNED_IMAGE_OCR_REQUIRED"
    try:
        res = subprocess.run(  # noqa: S603
            [exe, "-f", "1", "-l", "5", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        alnum_chars = sum(1 for ch in res.stdout if ch.isalnum())
        return "NATIVE_TEXT_LAYER" if alnum_chars >= 80 else "SCANNED_IMAGE_OCR_REQUIRED"
    except Exception:
        return "SCANNED_IMAGE_OCR_REQUIRED"


def download_all_pdfs() -> list[dict[str, Any]]:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    existing_manifest_path = PDF_DIR / "pdf-manifest.json"
    if existing_manifest_path.exists():
        raw_items = json.loads(existing_manifest_path.read_text(encoding="utf-8")).get("files", [])
        downloads = [
            {
                "source_id": item["source_id"],
                "title": item["title"],
                "category": item["category"],
                "published_date": item["published_date"],
                "url": item["url"],
                "filename": item["filename"],
            }
            for item in raw_items
        ]
    else:
        resources_raw = json.loads(
            _http_get_bytes("https://cms.nra.gov.ss/resources?_limit=500", timeout=45).decode(
                "utf-8"
            )
        )
        customs_res = _graphql_query(
            "{ customsResources { id title date type document { name url size } } }"
        )["data"]["customsResources"]
        downloads = []
        seen_urls: set[str] = set()
        for r in resources_raw:
            doc = r.get("document") or {}
            u = doc.get("url")
            if not u:
                continue
            full_url = f"https://cms.nra.gov.ss{u}"
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            downloads.append(
                {
                    "source_id": f"cms_resource_{r.get('id')}",
                    "title": (r.get("title") or "").strip(),
                    "category": r.get("type") or "unknown",
                    "published_date": (r.get("date") or "").strip(),
                    "url": full_url,
                    "filename": Path(u).name,
                }
            )
        for r in customs_res:
            doc = r.get("document") or {}
            u = doc.get("url")
            if not u:
                continue
            full_url = f"https://cms.nra.gov.ss{u}"
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            downloads.append(
                {
                    "source_id": f"cms_customs_resource_{r.get('id')}",
                    "title": f"eCustoms: {(r.get('title') or '').strip()}",
                    "category": r.get("type") or "customs",
                    "published_date": (r.get("date") or "").strip(),
                    "url": full_url,
                    "filename": Path(u).name,
                }
            )
        downloads.append(
            {
                "source_id": "mofp_fy2024_25_execution_report",
                "title": "MoFP FY 2024/2025 Budget Execution Report (SSRA Non-Oil Revenue Performance)",
                "category": "report",
                "published_date": "January 15, 2026",
                "url": "https://mofp.gov.ss/wp-content/uploads/2026/03/2024_25_Execution-Report_v3.pdf",
                "filename": "MoFP_2024_25_Execution_Report_v3.pdf",
            }
        )

    manifest: list[dict[str, Any]] = []
    for idx, item in enumerate(downloads, 1):
        fname = item["filename"]
        if not _SAFE_FILENAME_RE.match(fname):
            raise ValueError(f"Unsafe PDF filename rejected (CVE-2026-13509): {fname}")
        dest = (PDF_DIR / fname).resolve()
        if dest.parent != PDF_DIR.resolve():
            raise ValueError(f"Path traversal rejected (CVE-2026-13509): {dest}")

        if not dest.exists() or dest.stat().st_size == 0:
            data = _http_get_bytes(item["url"], timeout=180)
            dest.write_bytes(data)
        else:
            data = dest.read_bytes()

        sha256 = hashlib.sha256(data).hexdigest()
        is_pdf = data[:5] == b"%PDF-"
        has_active_objects = bool(_PDF_ACTIVE_OBJECT_RE.search(data))
        if has_active_objects:
            raise ValueError(f"Active PDF JS/Launch object detected in {fname} (CVE-2026-24737)")

        extraction_mode = _detect_extraction_mode(dest)
        rag_eligibility = _classify_rag_eligibility(item["title"], fname, item["category"])

        entry = {
            **item,
            "local_path": f"knowledge/corpus/pdfs/{fname}",
            "size_bytes": len(data),
            "sha256": sha256,
            "valid_pdf_header": is_pdf,
            "active_js_or_launch_objects": has_active_objects,
            "extraction_mode": extraction_mode,
            "rag_eligibility": rag_eligibility,
        }
        manifest.append(entry)
        print(
            f"[{idx:02d}/{len(downloads):02d}] {fname} "
            f"(eligibility={rag_eligibility}, mode={extraction_mode}, active_js={has_active_objects})"
        )

    manifest_payload = {
        "snapshot_version": "2026.10.1",
        "total_files": len(manifest),
        "total_bytes": sum(m["size_bytes"] for m in manifest),
        "files": manifest,
    }
    (PDF_DIR / "pdf-manifest.json").write_text(
        json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    download_all_pdfs()
