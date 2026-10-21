#!/usr/bin/env python3
"""Supply-Chain Hardening Verifier (Section 12.4 & ADR-015).

Verifies:
1. Every `uses:` action in `.github/workflows/*.yml` is pinned by an immutable 40-char commit SHA.
2. `pnpm-workspace.yaml` enforces `minimumReleaseAge >= 10080` (7 days).
3. `pyproject.toml` enforces `[tool.uv] exclude-newer`.
4. `ai/routing/model-routing.yaml` keeps `external_providers.enabled: false` by default (`OQ-004`).
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
_ACTION_SHA_RE = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def main() -> None:
    """Verify CI action SHA pinning, 7-day cooldowns, contract SHA parity, and Docker Compose hardening."""
    # 1. Verify GitHub Actions 40-char SHA pinning & persist-credentials: false (March 2026 LiteLLM/Trivy lesson)
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
                    if str(uses).startswith("actions/checkout@"):
                        assert step.get("with", {}).get("persist-credentials") is False, (
                            f"actions/checkout in {wf_path.name} must set persist-credentials: false"
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
    assert "ports" not in base_compose.get("services", {}).get("agent-runtime", {}), (
        "agent-runtime on sovereign_internal_net must not publish host ports"
    )
    assert "agentgateway" in base_compose.get("services", {}), (
        "docker-compose.yml must define governed agentgateway service on sovereign_internal_net"
    )
    assert (
        base_compose.get("services", {})
        .get("api", {})
        .get("depends_on", {})
        .get("nats", {})
        .get("condition")
        == "service_healthy"
    ), "api.depends_on.nats must require service_healthy"
    assert "vllm-sovereign" in prod_compose.get("services", {}), (
        "docker-compose.prod.yml must define hardened vllm-sovereign service"
    )
    assert "secrets" in prod_compose, (
        "docker-compose.prod.yml must define top-level file-based secrets"
    )
    _digest_re = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")
    for comp_name, comp_doc in (
        ("docker-compose.yml", base_compose),
        ("docker-compose.prod.yml", prod_compose),
    ):
        for s_name, s_cfg in comp_doc.get("services", {}).items():
            img = s_cfg.get("image")
            if img:
                assert _digest_re.match(str(img)), (
                    f"Unpinned image '{img}' in {comp_name} service '{s_name}'; must include @sha256:<64-hex>"
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
    try:
        primary = routing["hf_cache"]["models"]["llm_primary"]
        primary_repo = str(primary["repo_id"])
        primary_rev = str(primary["revision"])
    except (KeyError, TypeError) as exc:
        raise AssertionError(
            "model-routing.yaml is missing hf_cache.models.llm_primary.repo_id or revision"
        ) from exc
    model_cards_txt = (ROOT / "docs" / "ai-governance" / "model-cards-and-datasheet.md").read_text(
        encoding="utf-8"
    )
    sbom = json.loads(
        (ROOT / "infra" / "observability" / "cyclonedx-sbom.json").read_text(encoding="utf-8")
    )
    sbom_ok = any(
        comp.get("type") == "machine-learning-model"
        and comp.get("name") == primary_repo
        and comp.get("version") == primary_rev
        for comp in sbom.get("components", [])
    )
    assert primary_repo in model_cards_txt and primary_rev in model_cards_txt and sbom_ok, (
        f"Primary LLM '{primary_repo}@{primary_rev}' out of sync between model-routing.yaml, model-cards-and-datasheet.md, and cyclonedx-sbom.json"
    )
    slsa_path = ROOT / "infra" / "observability" / "slsa-provenance-v1.json"
    assert slsa_path.is_file(), "Missing SLSA v1.0 provenance statement (slsa-provenance-v1.json)"
    slsa_doc = json.loads(slsa_path.read_text(encoding="utf-8"))
    assert slsa_doc.get("predicateType") == "https://slsa.dev/provenance/v1", (
        "slsa-provenance-v1.json must declare SLSA v1.0 predicateType"
    )

    # 8. Verify CIS Docker Benchmark v1.7 Non-Root Dockerfiles, .dockerignore, Seccomp, Gateway 11-MCP Catalog & OTel memory_limiter
    assert (ROOT / ".dockerignore").is_file(), "Missing .dockerignore"
    for df_rel in (
        "services/api/Dockerfile",
        "services/agent-runtime/Dockerfile",
        "services/channel-gateway/Dockerfile",
        "services/workers/Dockerfile",
        "services/voice/Dockerfile",
        "infra/keycloak/Dockerfile",
        "apps/web/Dockerfile",
        "apps/console/Dockerfile",
    ):
        df_txt = (ROOT / df_rel).read_text(encoding="utf-8")
        assert "USER 10001:10001" in df_txt, (
            f"Dockerfile {df_rel} must run as non-root USER 10001:10001"
        )
        assert "HEALTHCHECK" in df_txt, f"Dockerfile {df_rel} must define a HEALTHCHECK"

    kc_df_txt = (ROOT / "infra" / "keycloak" / "Dockerfile").read_text(encoding="utf-8")
    assert "kc.sh build" in kc_df_txt and "--optimized" in kc_df_txt, (
        "infra/keycloak/Dockerfile must pre-build Quarkus image with kc.sh build and start --optimized"
    )
    assert (
        "@sha256:" in kc_df_txt
        and "/opt/keycloak/data/tmp" in kc_df_txt
        and "KC_HTTP_MANAGEMENT_PORT=9000" in kc_df_txt
        and "--transaction-xa-enabled=false" in kc_df_txt
        and "KC_HTTP_MAX_QUEUED_REQUESTS=256" in kc_df_txt
        and "-Djava.net.preferIPv4Stack=true" in kc_df_txt
    ), (
        "infra/keycloak/Dockerfile must pin @sha256:, pre-create /opt/keycloak/data/tmp, disable XA, bound queued requests, and set preferIPv4Stack"
    )
    assert "keycloak" in prod_compose.get("services", {}), (
        "docker-compose.prod.yml must define hardened keycloak production overlay"
    )
    kc_realm = json.loads(
        (ROOT / "infra" / "keycloak" / "ssra-realm.json").read_text(encoding="utf-8")
    )
    from ssra_security import validate_keycloak_realm_export

    assert validate_keycloak_realm_export(kc_realm) is True

    assert (ROOT / "infra" / "policies" / "seccomp-sovereign-default.json").is_file(), (
        "Missing infra/policies/seccomp-sovereign-default.json"
    )
    assert not (ROOT / "infra" / "k8s").exists() and not (ROOT / "infra" / "helm").exists(), (
        "Decommissioned Kubernetes directories infra/k8s and infra/helm must not exist"
    )

    gw_routes = yaml.safe_load(
        (ROOT / "infra" / "gateway" / "routes.yaml").read_text(encoding="utf-8")
    )
    mcp_servers = gw_routes.get("spec", {}).get("mcp", {}).get("servers", [])
    assert len(mcp_servers) == 11, (
        f"Expected 11 MCP servers in routes.yaml, found {len(mcp_servers)}"
    )
    assert (
        gw_routes.get("spec", {}).get("spendLimits", {}).get("perConversationMaxToolCalls") == 16
    ), "routes.yaml perConversationMaxToolCalls must equal 16"

    for srv_entry in mcp_servers:
        srv_name = str(srv_entry["name"])
        srv_url = str(srv_entry["url"])
        port_match = re.search(r":(\d+)/mcp$", srv_url)
        assert port_match is not None, f"Invalid MCP server URL '{srv_url}' in routes.yaml"
        expected_port = port_match.group(1)
        mcp_df = ROOT / "mcp-servers" / srv_name / "Dockerfile"
        assert mcp_df.is_file(), f"Missing Dockerfile for MCP server '{srv_name}'"
        mcp_df_txt = mcp_df.read_text(encoding="utf-8")
        assert "USER 10001:10001" in mcp_df_txt, (
            f"MCP Dockerfile {mcp_df} must run as non-root USER 10001:10001"
        )
        assert "HEALTHCHECK" in mcp_df_txt, f"MCP Dockerfile {mcp_df} must define a HEALTHCHECK"
        assert (
            f"EXPOSE {expected_port}" in mcp_df_txt and f'"--port", "{expected_port}"' in mcp_df_txt
        ), f"MCP Dockerfile {mcp_df} port mismatch with routes.yaml (expected {expected_port})"

    from ssra_runtime.tools import GovernedMcpGatewayClient

    risk_tiers_cfg = yaml.safe_load(
        (ROOT / "ai" / "policies" / "risk-tiers.yaml").read_text(encoding="utf-8")
    )
    canonical_tool_tiers: dict[str, str] = risk_tiers_cfg.get("tool_tiers", {})
    gw_client = GovernedMcpGatewayClient()
    discovered_tools: dict[str, str] = {}
    for s_name, s_inst in gw_client.servers.items():
        for t_name, t_reg in s_inst.tools.items():
            t_key = f"{s_name}.{t_name}"
            discovered_tools[t_key] = t_reg.tier.value
            assert t_reg.input_schema.get("additionalProperties") is False, (
                f"MCP tool '{t_key}' input_schema must set additionalProperties: False"
            )
            assert t_reg.output_schema.get("additionalProperties") is False, (
                f"MCP tool '{t_key}' output_schema must set additionalProperties: False"
            )
    assert discovered_tools == canonical_tool_tiers, (
        "MCP tool catalog / tier drift between mcp-servers/* (33 tools) and ai/policies/risk-tiers.yaml"
    )

    otel_cfg = yaml.safe_load(
        (ROOT / "infra" / "observability" / "otel-collector-config.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert "memory_limiter" in otel_cfg.get("processors", {}), (
        "otel-collector-config.yaml must configure memory_limiter processor"
    )

    print(
        "Supply-chain, infra & living-docs traceability verification passed: 40-char SHA CI actions, 7-day cooldowns, contract SHA parity, non-root Dockerfiles, Seccomp, OTel memory_limiter, 11-server gateway, ADR catalog, and ML-BOM verified."
    )


if __name__ == "__main__":
    main()
