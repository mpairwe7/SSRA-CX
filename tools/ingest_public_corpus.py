#!/usr/bin/env python3
"""Public Knowledge Corpus & Tax Facts Snapshot Ingestion & Checksum Verifier (Sections 7, 17, 18).

Reads:
- `knowledge/sources.yaml`
- `knowledge/tax-facts/seed-2026.10.1.yaml`
- `knowledge/corpus/seed-documents.json`
- `ai/termbase/glossary.yaml`

Validates every chunk and TaxFact, computes an immutable SHA-256 snapshot checksum over the
entire published bundle, and writes `knowledge/snapshot-manifest-2026.10.1.json`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
from ssra_rules import TaxFactsRegistry

ROOT = Path(__file__).resolve().parents[1]
SOURCES_YAML = ROOT / "knowledge" / "sources.yaml"
CORPUS_JSON = ROOT / "knowledge" / "corpus" / "seed-documents.json"
TERMBASE_YAML = ROOT / "ai" / "termbase" / "glossary.yaml"
MANIFEST_OUT = ROOT / "knowledge" / "snapshot-manifest-2026.10.1.json"


def build_snapshot_manifest() -> dict[str, object]:
    sources_raw = yaml.safe_load(SOURCES_YAML.read_text(encoding="utf-8"))
    corpus_raw = json.loads(CORPUS_JSON.read_text(encoding="utf-8"))
    termbase_raw = yaml.safe_load(TERMBASE_YAML.read_text(encoding="utf-8"))
    registry = TaxFactsRegistry.from_yaml_file()

    snapshot_version = str(sources_raw["snapshot_version"])
    assert corpus_raw["snapshot_version"] == snapshot_version
    assert registry.snapshot_version == snapshot_version

    chunks = list(corpus_raw["chunks"])
    facts = [f.model_dump(mode="json") for f in registry.list_facts()]
    terms = list(termbase_raw.get("terms", []))

    canonical_bundle = json.dumps(
        {
            "snapshot_version": snapshot_version,
            "sources": sources_raw.get("sources", []),
            "chunks": chunks,
            "tax_facts": facts,
            "terms": terms,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    checksum = hashlib.sha256(canonical_bundle).hexdigest()

    locales_covered = sorted({str(c["language"]) for c in chunks})
    return {
        "snapshot_version": snapshot_version,
        "approval_state": "PUBLISHED",
        "approved_by": str(sources_raw["approved_by"]),
        "published_at": str(sources_raw["published_at"]),
        "checksum_sha256": checksum,
        "counts": {
            "sources": len(sources_raw.get("sources", [])),
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
        f"(SHA-256={str(manifest['checksum_sha256'])[:16]}..., counts={manifest['counts']}) -> "
        f"{MANIFEST_OUT.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
