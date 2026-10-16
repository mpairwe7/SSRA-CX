"""Download official SSRA / NRA / MoFP PDFs, manuals, acts, circulars, and sanitized CMS FAQs.

Fetches all official PDF documents from:
- https://cms.nra.gov.ss/resources (35 official Acts, Manuals, Circulars, and Policies)
- https://cms.nra.gov.ss/graphql customsResources (4 official eCustoms PDFs)
- https://mofp.gov.ss/wp-content/uploads/2026/03/2024_25_Execution-Report_v3.pdf

Also fetches and sanitizes the structured CMS content (FAQs, Individual & Business guides,
Penalties, Depreciation tables, Quarterly Advance Tax schedules, TCC guides, Investor & Agent
guides, and Office Locations) into `knowledge/corpus/cms-official-snapshot.json`, rejecting
any upstream HTML/XSS or pentest artefacts per Section 6.3 (`sanitiser.py`).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "knowledge" / "corpus" / "pdfs"
CMS_SNAPSHOT_FILE = ROOT / "knowledge" / "corpus" / "cms-official-snapshot.json"

_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) SSRA-Assist-Knowledge-Ingester/2026.10.1"
_POISON_PATTERNS = re.compile(
    r"(?:<img\b|<script\b|onerror\s*=|localStorage\.getItem|webhook\.site|pipedream\.net|PENTEST|Backdoor2026|89\.116\.171\.182)",
    re.IGNORECASE,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


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


def _clean_text(val: Any) -> str | None:
    if not isinstance(val, str):
        return None
    text = val.strip()
    if not text or _POISON_PATTERNS.search(text):
        return None
    text = _HTML_TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def download_all_pdfs() -> list[dict[str, Any]]:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    resources_raw = json.loads(
        _http_get_bytes("https://cms.nra.gov.ss/resources?_limit=500", timeout=45).decode("utf-8")
    )
    customs_res = _graphql_query(
        "{ customsResources { id title date type document { name url size } } }"
    )["data"]["customsResources"]

    downloads: list[dict[str, Any]] = []
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
        dest = PDF_DIR / item["filename"]
        if not dest.exists() or dest.stat().st_size == 0:
            data = _http_get_bytes(item["url"], timeout=180)
            dest.write_bytes(data)
        else:
            data = dest.read_bytes()
        sha256 = hashlib.sha256(data).hexdigest()
        is_pdf = data[:5] == b"%PDF-"
        entry = {
            **item,
            "local_path": f"knowledge/corpus/pdfs/{item['filename']}",
            "size_bytes": len(data),
            "sha256": sha256,
            "valid_pdf_header": is_pdf,
        }
        manifest.append(entry)
        print(
            f"[{idx:02d}/{len(downloads):02d}] {item['filename']} "
            f"({len(data) / 1024:.1f} KB, pdf={is_pdf}, sha256={sha256[:12]}...)"
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


def fetch_and_sanitize_cms_snapshot() -> dict[str, Any]:
    q = """
    {
      aboutUs { title par1 head1 head2 head3 head4 head5 mission branches par }
      abouts { id title heading slug intro }
      individualIntroductions { id title heading slug intro }
      tinRegistrations { id title heading slug intro content }
      taxesForIndividuals { id title heading slug intro }
      indFaqs { id head body }
      businessIntroductions { id title heading slug intro }
      tinRegBuses { id title heading slug intro }
      taxAppBsns { id title heading slug intro }
      penalties { id title heading slug intro content }
      dedAndDeps { id title heading slug intro content1 content2 }
      cdrTables { id category description rate }
      cpTables { id category property }
      crTables { id category rate }
      ftTables { id date period }
      idtTables { id item descr tax }
      ppTables { id pit perc }
      taxComCerts { id title heading slug intro content }
      bsnFaqs { id head body }
      invIntros { id title heading slug intro content1 content2 content3 }
      agIntros { id title heading slug intro content }
      ourLocations { id title heading slug intro }
    }
    """
    raw = _graphql_query(q)["data"]
    sanitized: dict[str, Any] = {}
    quarantined_count = 0

    for section, value in raw.items():
        if isinstance(value, list):
            clean_rows = []
            for row in value:
                if not isinstance(row, dict):
                    continue
                # Check if any field in row contains a poison/XSS/pentest payload
                raw_concat = " ".join(str(v) for v in row.values() if v is not None)
                if _POISON_PATTERNS.search(raw_concat):
                    quarantined_count += 1
                    continue
                cleaned_row = {}
                for k, v in row.items():
                    if k == "id":
                        cleaned_row[k] = str(v)
                    else:
                        cv = _clean_text(v)
                        if cv is not None:
                            cleaned_row[k] = cv
                if len(cleaned_row) > 1:
                    clean_rows.append(cleaned_row)
            sanitized[section] = clean_rows
        elif isinstance(value, dict):
            cleaned_obj = {}
            for k, v in value.items():
                cv = _clean_text(v)
                if cv is not None:
                    cleaned_obj[k] = cv
            sanitized[section] = cleaned_obj

    out = {
        "snapshot_version": "2026.10.1",
        "source": "https://cms.nra.gov.ss/graphql",
        "quarantined_upstream_xss_or_pentest_records": quarantined_count,
        "collections": sanitized,
    }
    CMS_SNAPSHOT_FILE.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(
        f"Saved sanitized CMS snapshot -> {CMS_SNAPSHOT_FILE.relative_to(ROOT)} "
        f"(quarantined {quarantined_count} poisoned/pentest upstream records)"
    )
    return out


if __name__ == "__main__":
    download_all_pdfs()
    fetch_and_sanitize_cms_snapshot()
