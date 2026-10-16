#!/usr/bin/env python3
"""Deterministic CycloneDX 1.5 SBOM generator for SSRA Assist (Section 12.4 & 15)."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
PACKAGE_JSON = ROOT / "package.json"
OUT_SBOM = ROOT / "infra" / "observability" / "cyclonedx-sbom.json"


def build_sbom() -> dict[str, object]:
    py_data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    js_data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))

    components: list[dict[str, str]] = []
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

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "ssra-cx",
                "version": "0.1.0",
            }
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
        f"Generated CycloneDX 1.5 SBOM ({len(comps)} pinned components) -> {OUT_SBOM.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
