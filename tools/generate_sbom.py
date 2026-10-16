#!/usr/bin/env python3
"""Deterministic CycloneDX 1.6 Software + AI/ML-BOM Generator for SSRA Assist (Section 12.4, 15, ISO/IEC 42001, OWASP ASI04)."""

from __future__ import annotations

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
OUT_SBOM = ROOT / "infra" / "observability" / "cyclonedx-sbom.json"


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
        if repo_id:
            components.append(
                {
                    "type": "machine-learning-model",
                    "name": str(repo_id),
                    "version": "2026.10.1",
                    "purl": f"pkg:huggingface/{repo_id}@2026.10.1",
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
        if isinstance(checkpoints, dict):
            for ck_repo in sorted(set(checkpoints.values())):
                components.append(
                    {
                        "type": "machine-learning-model",
                        "name": str(ck_repo),
                        "version": "2026.10.1",
                        "purl": f"pkg:huggingface/{ck_repo}@2026.10.1",
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
    sbom = build_sbom()
    OUT_SBOM.parent.mkdir(parents=True, exist_ok=True)
    OUT_SBOM.write_text(json.dumps(sbom, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    comps = sbom["components"]
    assert isinstance(comps, list)
    print(
        f"Generated CycloneDX 1.6 SBOM + ML-BOM ({len(comps)} pinned components) -> {OUT_SBOM.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
