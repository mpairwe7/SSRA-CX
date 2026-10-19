#!/usr/bin/env python3
"""Deterministic CycloneDX 1.6 Software + AI/ML-BOM Generator for SSRA Assist (Section 12.4, 15, ISO/IEC 42001, OWASP ASI04)."""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
PACKAGE_JSON = ROOT / "package.json"
ROUTING_YAML = ROOT / "ai" / "routing" / "model-routing.yaml"
SNAPSHOT_MANIFEST = ROOT / "knowledge" / "snapshot-manifest-2026.10.1.json"
OPENAPI_JSON = ROOT / "services" / "api" / "openapi.json"
OUT_SBOM = ROOT / "infra" / "observability" / "cyclonedx-sbom.json"
OUT_SLSA = ROOT / "infra" / "observability" / "slsa-provenance-v1.json"


def build_sbom() -> dict[str, Any]:
    py_data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    js_data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    routing_data = yaml.safe_load(ROUTING_YAML.read_text(encoding="utf-8")) or {}
    snap_data = json.loads(SNAPSHOT_MANIFEST.read_text(encoding="utf-8"))

    components: list[dict[str, Any]] = []
    for dep in py_data.get("project", {}).get("dependencies", []):
        if "==" in dep:
            name, ver = dep.split("==", 1)
            components.append(
                {
                    "type": "library",
                    "name": name,
                    "version": ver,
                    "purl": f"pkg:pypi/{name}@{ver}",
                }
            )

    for name, ver in sorted(js_data.get("devDependencies", {}).items()):
        components.append(
            {
                "type": "library",
                "name": name,
                "version": str(ver),
                "purl": f"pkg:npm/{name}@{ver}",
            }
        )

    # CycloneDX 1.6 ML-BOM: Include sovereign vLLM & HuggingFace cache models
    hf_models = routing_data.get("hf_cache", {}).get("models", {})
    for model_key, cfg in sorted(hf_models.items()):
        if not isinstance(cfg, dict):
            continue
        repo_id = cfg.get("repo_id")
        revision = str(cfg.get("revision") or "unknown")
        if repo_id:
            components.append(
                {
                    "type": "machine-learning-model",
                    "name": str(repo_id),
                    "version": revision,
                    "purl": f"pkg:huggingface/{repo_id}@{revision}",
                    "modelCard": {
                        "modelParameters": {
                            "approach": {"type": "supervised"},
                            "task": model_key,
                            "architectureFamily": str(cfg.get("engine", "vllm")),
                        }
                    },
                }
            )
        checkpoints = cfg.get("checkpoints_by_locale")
        rev_map = cfg.get("revisions_by_checkpoint") or {}
        if isinstance(checkpoints, dict):
            for ck_repo in sorted(set(checkpoints.values())):
                ck_rev = str(rev_map.get(ck_repo) or revision)
                components.append(
                    {
                        "type": "machine-learning-model",
                        "name": str(ck_repo),
                        "version": ck_rev,
                        "purl": f"pkg:huggingface/{ck_repo}@{ck_rev}",
                        "modelCard": {
                            "modelParameters": {
                                "approach": {"type": "supervised"},
                                "task": "tts_mms",
                                "architectureFamily": "hf-vits-offline",
                            }
                        },
                    }
                )

    # CycloneDX 1.6 Data-BOM: Include immutable KnowledgeSnapshot & TaxFacts manifest
    components.append(
        {
            "type": "data",
            "name": "ssra-knowledge-snapshot",
            "version": str(snap_data.get("snapshot_version", "2026.10.1")),
            "hashes": [
                {
                    "alg": "SHA-256",
                    "content": str(snap_data.get("checksum_sha256", "")),
                }
            ],
        }
    )

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "ssra-cx",
                "version": "0.1.0",
            },
            "properties": [
                {
                    "name": "ssra:ai_governance:standard",
                    "value": "ISO/IEC 42001:2023 & NIST AI 600-1",
                },
                {"name": "ssra:sovereign_hosting", "value": "NCA South Sudan (In-Country)"},
            ],
        },
        "components": components,
    }


def main() -> None:
    """Write deterministic CycloneDX 1.6 SBOM + ML-BOM and SLSA v1.0 provenance statement."""
    sbom = build_sbom()
    OUT_SBOM.parent.mkdir(parents=True, exist_ok=True)
    sbom_bytes = (json.dumps(sbom, indent=2, sort_keys=True) + "\n").encode("utf-8")
    OUT_SBOM.write_bytes(sbom_bytes)
    sbom_sha256 = hashlib.sha256(sbom_bytes).hexdigest()
    snap_sha256 = hashlib.sha256(SNAPSHOT_MANIFEST.read_bytes()).hexdigest()
    openapi_sha256 = hashlib.sha256(OPENAPI_JSON.read_bytes()).hexdigest()

    from ssra_core import SCHEMA_BUNDLE_SHA256

    slsa_statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {
                "name": "infra/observability/cyclonedx-sbom.json",
                "digest": {"sha256": sbom_sha256},
            },
            {
                "name": "knowledge/snapshot-manifest-2026.10.1.json",
                "digest": {"sha256": snap_sha256},
            },
            {
                "name": "services/api/openapi.json",
                "digest": {"sha256": openapi_sha256},
            },
            {
                "name": "packages/contracts/schemas",
                "digest": {"sha256": SCHEMA_BUNDLE_SHA256},
            },
        ],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://ssra.gov.ss/slsa/taskfile-build/v1",
                "externalParameters": {
                    "workflow": ".github/workflows/ci.yml",
                    "entryPoint": "task gen",
                    "cooldownMinimumReleaseAgeMinutes": 10080,
                },
            },
            "runDetails": {
                "builder": {
                    "id": "https://github.com/mpairwe7/SSRA-CX/.github/workflows/ci.yml@refs/heads/main"
                }
            },
        },
    }
    OUT_SLSA.write_text(
        json.dumps(slsa_statement, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    comps = sbom["components"]
    assert isinstance(comps, list)
    print(
        f"Generated CycloneDX 1.6 SBOM + ML-BOM ({len(comps)} pinned components) & SLSA v1.0 provenance -> {OUT_SBOM.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
