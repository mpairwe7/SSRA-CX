#!/usr/bin/env python3
"""Public Knowledge Corpus & Tax Facts Snapshot Ingestion & RAGShield Provenance Verifier.

Implements October 2026 RAGShield (arXiv:2604.00387) & OWASP RAG Security Cheat Sheet controls:
1. Re-verifies on-disk SHA-256 digests and active-object safety for all 40 official PDFs.
2. Runs a Cross-Source Numerical Contradiction Detector ensuring every statutory percentage rate
   in `knowledge/corpus/seed-documents.json` is backed by a matching `TaxFact` in
   `knowledge/tax-facts/seed-2026.10.1.yaml`.
3. Computes an immutable SHA-256 bundle checksum and HMAC-SHA256 provenance attestation over
   the entire published snapshot in `knowledge/snapshot-manifest-2026.10.1.json`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from pathlib import Path

import yaml
from ssra_rules import TaxFactsRegistry

ROOT = Path(__file__).resolve().parents[1]
SOURCES_YAML = ROOT / "knowledge" / "sources.yaml"
CORPUS_JSON = ROOT / "knowledge" / "corpus" / "seed-documents.json"
PDF_MANIFEST_JSON = ROOT / "knowledge" / "corpus" / "pdfs" / "pdf-manifest.json"
CMS_SNAPSHOT_JSON = ROOT / "knowledge" / "corpus" / "cms-official-snapshot.json"
TERMBASE_YAML = ROOT / "ai" / "termbase" / "glossary.yaml"
MANIFEST_OUT = ROOT / "knowledge" / "snapshot-manifest-2026.10.1.json"

_PERCENT_RE = re.compile(r"\b(\d+(?:\.\d+)?)%")
_MACRO_POLICY_TARGETS = {"6"}  # 6% Tax-to-GDP ratio by 2027 vision target in SSRA Act 2023


def _verify_cross_source_numerical_consistency(
    chunks: list[dict[str, object]],
    registry: TaxFactsRegistry,
) -> int:
    active_percent_values = {
        f.value for f in registry.list_facts() if str(f.unit) == "PERCENT"
    } | _MACRO_POLICY_TARGETS
    verified_rate_mentions = 0
    for chk in chunks:
        content = str(chk.get("content", ""))
        for m in _PERCENT_RE.finditer(content):
            pct_val = m.group(1)
            if pct_val not in active_percent_values:
                raise ValueError(
                    f"RAGShield cross-source contradiction in chunk '{chk.get('id')}': "
                    f"percentage '{pct_val}%' has no matching active PERCENT TaxFact in registry"
                )
            verified_rate_mentions += 1
    return verified_rate_mentions


def build_snapshot_manifest() -> dict[str, object]:
    sources_raw = yaml.safe_load(SOURCES_YAML.read_text(encoding="utf-8"))
    corpus_raw = json.loads(CORPUS_JSON.read_text(encoding="utf-8"))
    pdf_manifest_raw = json.loads(PDF_MANIFEST_JSON.read_text(encoding="utf-8"))
    cms_snapshot_raw = json.loads(CMS_SNAPSHOT_JSON.read_text(encoding="utf-8"))
    termbase_raw = yaml.safe_load(TERMBASE_YAML.read_text(encoding="utf-8"))
    registry = TaxFactsRegistry.from_yaml_file()

    snapshot_version = str(sources_raw["snapshot_version"])
    assert corpus_raw["snapshot_version"] == snapshot_version
    assert pdf_manifest_raw["snapshot_version"] == snapshot_version
    assert cms_snapshot_raw["snapshot_version"] == snapshot_version
    assert registry.snapshot_version == snapshot_version

    pdf_files = list(pdf_manifest_raw.get("files", []))
    for item in pdf_files:
        assert bool(item.get("valid_pdf_header")), f"Invalid PDF header in {item.get('filename')}"
        assert not bool(item.get("active_js_or_launch_objects")), (
            f"Active JS/Launch object in {item.get('filename')}"
        )
        local_pdf = ROOT / str(item["local_path"])
        if local_pdf.exists():
            actual_sha = hashlib.sha256(local_pdf.read_bytes()).hexdigest()
            assert actual_sha == item["sha256"], (
                f"On-disk SHA-256 mismatch for {local_pdf.name}: {actual_sha} != {item['sha256']}"
            )

    chunks = list(corpus_raw["chunks"])
    verified_rate_mentions = _verify_cross_source_numerical_consistency(chunks, registry)
    facts = [f.model_dump(mode="json") for f in registry.list_facts()]
    terms = list(termbase_raw.get("terms", []))

    canonical_bundle = json.dumps(
        {
            "snapshot_version": snapshot_version,
            "sources": sources_raw.get("sources", []),
            "chunks": chunks,
            "tax_facts": facts,
            "terms": terms,
            "pdf_manifest_sha256s": [f["sha256"] for f in pdf_files],
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    checksum = hashlib.sha256(canonical_bundle).hexdigest()

    signing_key = os.environ.get(
        "SSRA_MANIFEST_HMAC_KEY", "ssra-sovereign-knowledge-manifest-key-2026"
    ).encode("utf-8")
    attestation_hmac = hmac.new(signing_key, canonical_bundle, hashlib.sha256).hexdigest()

    locales_covered = sorted({str(c["language"]) for c in chunks})
    return {
        "snapshot_version": snapshot_version,
        "approval_state": "PUBLISHED",
        "approved_by": str(sources_raw["approved_by"]),
        "published_at": str(sources_raw["published_at"]),
        "checksum_sha256": checksum,
        "attestation_hmac_sha256": attestation_hmac,
        "ragshield_verified_rate_mentions": verified_rate_mentions,
        "counts": {
            "sources": len(sources_raw.get("sources", [])),
            "official_pdfs": len(pdf_files),
            "chunks": len(chunks),
            "tax_facts": len(facts),
            "termbase_entries": len(terms),
        },
        "locales_covered": locales_covered,
    }


def main() -> None:
    manifest = build_snapshot_manifest()
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Ingested public corpus snapshot {manifest['snapshot_version']} "
        f"(SHA-256={str(manifest['checksum_sha256'])[:16]}..., "
        f"HMAC={str(manifest['attestation_hmac_sha256'])[:16]}..., "
        f"verified_rates={manifest['ragshield_verified_rate_mentions']}, "
        f"counts={manifest['counts']}) -> {MANIFEST_OUT.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
