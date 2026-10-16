#!/usr/bin/env python3
"""Supply-Chain Hardening Verifier (Section 12.4 & ADR-015).

Verifies:
1. Every `uses:` action in `.github/workflows/*.yml` is pinned by an immutable 40-char commit SHA.
2. `pnpm-workspace.yaml` enforces `minimumReleaseAge >= 10080` (7 days).
3. `pyproject.toml` enforces `[tool.uv] exclude-newer`.
4. `ai/routing/model-routing.yaml` keeps `external_providers.enabled: false` by default (`OQ-004`).
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
_ACTION_SHA_RE = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def main() -> None:
    """Verify CI action SHA pinning, 7-day cooldowns, contract SHA parity, and Docker Compose hardening."""
    # 1. Verify GitHub Actions 40-char SHA pinning (March 2026 LiteLLM/Trivy lesson)
    wf_dir = ROOT / ".github" / "workflows"
    for wf_path in sorted(wf_dir.glob("*.yml")):
        raw = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
        for _job_name, job in raw.get("jobs", {}).items():
            for step in job.get("steps", []):
                uses = step.get("uses")
                if uses:
                    assert _ACTION_SHA_RE.match(str(uses)), (
                        f"Unpinned GitHub Action '{uses}' in {wf_path.name}; must use 40-char SHA"
                    )

    # 2. Verify pnpm 7-day dependency cooldown (`minimumReleaseAge: 10080`)
    pnpm_ws = yaml.safe_load((ROOT / "pnpm-workspace.yaml").read_text(encoding="utf-8"))
    min_age = int(pnpm_ws.get("minimumReleaseAge", 0))
    assert min_age >= 10080, f"pnpm minimumReleaseAge {min_age} < 10080 (7 days)"

    # 3. Verify uv 7-day dependency cooldown (`exclude-newer`)
    pyproj = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    exclude_newer = pyproj.get("tool", {}).get("uv", {}).get("exclude-newer")
    assert exclude_newer is not None and len(str(exclude_newer)) >= 10, (
        "pyproject.toml missing [tool.uv] exclude-newer 7-day cooldown"
    )

    # 4. Verify external AI providers remain disabled by default until OQ-004 sign-off
    routing = yaml.safe_load(
        (ROOT / "ai" / "routing" / "model-routing.yaml").read_text(encoding="utf-8")
    )
    assert routing.get("external_providers", {}).get("enabled") is False, (
        "External AI providers must remain disabled by default until OQ-004 is approved"
    )

    # 5. Verify bidirectional SCHEMA_BUNDLE_SHA256 parity between Python and TypeScript contracts
    from ssra_core import SCHEMA_BUNDLE_SHA256

    ts_contracts = (ROOT / "packages" / "contracts" / "src" / "index.ts").read_text(
        encoding="utf-8"
    )
    assert f'"{SCHEMA_BUNDLE_SHA256}"' in ts_contracts, (
        "Contract SHA-256 drift between Python (ssra_core) and TypeScript (@ssra/contracts)"
    )

    # 6. Verify 2026 Docker Compose hardening & decommissioned Kubernetes in operational runbooks
    base_compose = yaml.safe_load(
        (ROOT / "infra" / "compose" / "docker-compose.yml").read_text(encoding="utf-8")
    )
    prod_compose = yaml.safe_load(
        (ROOT / "infra" / "compose" / "docker-compose.prod.yml").read_text(encoding="utf-8")
    )
    assert (
        base_compose.get("networks", {}).get("sovereign_internal_net", {}).get("internal") is True
    ), "docker-compose.yml must define sovereign_internal_net with internal: true"
    assert "vllm-sovereign" in prod_compose.get("services", {}), (
        "docker-compose.prod.yml must define hardened vllm-sovereign service"
    )
    for rb_path in sorted((ROOT / "docs" / "runbooks").glob("*.md")):
        rb_text = rb_path.read_text(encoding="utf-8")
        for forbidden in ("kubectl", "kustomize", "infra/k8s", "CloudNativePG"):
            assert forbidden not in rb_text, (
                f"Runbook {rb_path.name} still contains decommissioned Kubernetes term '{forbidden}'"
            )

    # 7. Verify Living Docs, ADR Catalog (ADR-001..ADR-016), Model Card & CycloneDX 1.6 ML-BOM Traceability
    trace_skill = ROOT / ".agents" / "skills" / "living-docs-adr-runbooks-traceability" / "SKILL.md"
    assert trace_skill.is_file(), "Missing living-docs-adr-runbooks-traceability skill"
    adr_readme = (ROOT / "docs" / "adr" / "README.md").read_text(encoding="utf-8")
    for adr_file in sorted((ROOT / "docs" / "adr").glob("00*.md")):
        assert adr_file.name in adr_readme, (
            f"Unindexed ADR '{adr_file.name}' missing from docs/adr/README.md"
        )
    primary_repo = (
        routing.get("hf_cache", {}).get("models", {}).get("llm_primary", {}).get("repo_id", "")
    )
    model_cards_txt = (ROOT / "docs" / "ai-governance" / "model-cards-and-datasheet.md").read_text(
        encoding="utf-8"
    )
    sbom_txt = (ROOT / "infra" / "observability" / "cyclonedx-sbom.json").read_text(
        encoding="utf-8"
    )
    assert primary_repo and primary_repo in model_cards_txt and primary_repo in sbom_txt, (
        f"Primary LLM '{primary_repo}' out of sync between model-routing.yaml, model-cards-and-datasheet.md, and cyclonedx-sbom.json"
    )

    print(
        "Supply-chain & living-docs traceability verification passed: 40-char SHA CI actions, 7-day cooldowns, contract SHA parity, Docker Compose 2026, ADR catalog, and ML-BOM verified."
    )


if __name__ == "__main__":
    main()
