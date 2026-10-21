#!/usr/bin/env python3
"""Supply-Chain Hardening Verifier (Section 12.4 & ADR-015).

Verifies:
1. GitHub Actions workflows have explicit least-privilege permissions, immutable action SHAs,
   safe checkout settings, no `pull_request_target`, and required R1 scanner jobs.
2. `pnpm-workspace.yaml`, `pyproject.toml`, and Dependabot enforce a rolling seven-day
   cooldown and the selected package-manager trust policies.
3. The deployed frontend is the explicit Node BFF runtime, without stale Next.js configuration.
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
_ZIZMOR_ACTION = "zizmorcore/zizmor-action@cc914d7f3750a2d13d75c7f184a1060aa0e9d482"
_GITLEAKS_ARCHIVE_SHA256 = "5bc41815076e6ed6ef8fbecc9d9b75bcae31f39029ceb55da08086315316e3ba"
_PNPM_VERSION = "10.33.0"
_PNPM_INTEGRITY = (
    "sha512.10568bb4a6afb58c9eb3630da90cc9516417abebd3fabbe6739f0ae795728da1491e9db5a544"
    "c76ad8eb7570f5c4bb3d6c637b2cb41bfdcdb47fa823c8649319"
)
_UV_VERSION = "0.13.4"
_UV_ARCHIVE_SHA256 = "2b428396f12572d4429cf210ca234dd599a33b3af0958a4d5ed569d63e3f344f"
_CERTIFI_VERSION = "2026.10.19"
_CERTIFI_EXCLUDE_NEWER_CUTOFF = "2026-10-21T00:00:00Z"
_CERTIFI_SDIST_SHA256 = "035c1e85572b141bf1c3a3eff0e33a8eb74917522f2559075ff8d2fea780a1ae"
_CERTIFI_WHEEL_SHA256 = "42d35340cc5b9ba78e818ddbff0c5b1c2b779de448a340fd1b989f5fa8670e1b"
_DEPENDABOT_ECOSYSTEMS = ("npm", "uv", "github-actions")
_NODE_ENGINE = ">=24.0.0 <25.0.0"


def _load_workflow(workflow_path: Path) -> dict[object, object]:
    """Load one workflow and fail with a useful message when its shape is invalid."""
    raw = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict), f"Workflow {workflow_path.name} must be a YAML mapping"
    return raw


def _workflow_triggers(workflow: dict[object, object]) -> object:
    """Return a workflow's trigger declaration despite PyYAML's YAML 1.1 `on` coercion."""
    if "on" in workflow:
        return workflow["on"]
    return workflow.get(True)


def _uses_pull_request_target(triggers: object) -> bool:
    """Identify the forbidden trigger in string, list, and mapping GitHub Actions forms."""
    if isinstance(triggers, str):
        return triggers == "pull_request_target"
    if isinstance(triggers, list):
        return any(trigger == "pull_request_target" for trigger in triggers)
    return isinstance(triggers, dict) and "pull_request_target" in triggers


def _workflow_steps(
    job: object, workflow_path: Path, job_name: object
) -> list[dict[object, object]]:
    """Return typed workflow steps while keeping policy failures actionable."""
    assert isinstance(job, dict), f"Job '{job_name}' in {workflow_path.name} must be a mapping"
    steps = job.get("steps", [])
    assert isinstance(steps, list), f"Job '{job_name}' in {workflow_path.name} must list steps"
    assert all(isinstance(step, dict) for step in steps), (
        f"Job '{job_name}' in {workflow_path.name} contains an invalid step"
    )
    return steps


def verify_workflow_integrity(workflows_dir: Path) -> None:
    """Enforce immutable GitHub Actions and least-privilege workflow defaults.

    This function accepts a directory so the regression suite can prove that a
    tag-pinned action or a missing permissions declaration is rejected.
    """
    workflow_paths = sorted(
        path for pattern in ("*.yml", "*.yaml") for path in workflows_dir.glob(pattern)
    )
    assert workflow_paths, f"No GitHub Actions workflows found in {workflows_dir}"
    for workflow_path in workflow_paths:
        workflow = _load_workflow(workflow_path)
        assert not _uses_pull_request_target(_workflow_triggers(workflow)), (
            f"Workflow {workflow_path.name} must not use pull_request_target"
        )
        assert workflow.get("permissions") == {}, (
            f"Workflow {workflow_path.name} must set permissions: {{}} at workflow scope"
        )
        jobs = workflow.get("jobs")
        assert isinstance(jobs, dict) and jobs, f"Workflow {workflow_path.name} must define jobs"
        for job_name, job in jobs.items():
            assert isinstance(job, dict), (
                f"Job '{job_name}' in {workflow_path.name} must be a mapping"
            )
            assert isinstance(job.get("permissions"), dict), (
                f"Job '{job_name}' in {workflow_path.name} must declare explicit permissions"
            )
            for step in _workflow_steps(job, workflow_path, job_name):
                uses = step.get("uses")
                if uses:
                    assert _ACTION_SHA_RE.fullmatch(str(uses)), (
                        f"Unpinned GitHub Action '{uses}' in {workflow_path.name}; must use 40-char SHA"
                    )
                    if str(uses).startswith("actions/checkout@"):
                        step_with = step.get("with", {})
                        assert (
                            isinstance(step_with, dict)
                            and step_with.get("persist-credentials") is False
                        ), (
                            f"actions/checkout in {workflow_path.name} must set persist-credentials: false"
                        )


def _find_step_with_uses(
    steps: list[dict[object, object]], action: str, workflow_name: str
) -> dict[object, object]:
    """Find an exact action reference in a required workflow job."""
    for step in steps:
        if step.get("uses") == action:
            return step
    raise AssertionError(f"{workflow_name} must use {action}")


def verify_ci_security_policy(repo_root: Path) -> None:
    """Verify the blocking R1 CI controls and workflow CODEOWNERS protection."""
    ci_path = repo_root / ".github" / "workflows" / "ci.yml"
    ci_workflow = _load_workflow(ci_path)
    jobs = ci_workflow.get("jobs")
    assert isinstance(jobs, dict), "ci.yml must define jobs"

    expected_permissions = {
        "verify": {"contents": "read"},
        "secret-history": {"contents": "read"},
        "workflow-security": {"actions": "read", "contents": "read"},
    }
    for job_name, expected in expected_permissions.items():
        job = jobs.get(job_name)
        assert isinstance(job, dict), f"ci.yml must define the '{job_name}' blocking job"
        assert job.get("permissions") == expected, (
            f"ci.yml job '{job_name}' must use only {expected} permissions"
        )

    verify_steps = _workflow_steps(jobs["verify"], ci_path, "verify")
    pnpm_step = _find_step_with_uses(
        verify_steps,
        "pnpm/action-setup@a7487c7e89a18df4991f7f222e4898a00d66ddda",
        "verify",
    )
    assert pnpm_step.get("with") in (None, {}), (
        "verify must derive pnpm from the integrity-pinned packageManager field instead of "
        "declaring a second action version"
    )
    uv_step = _find_step_with_uses(
        verify_steps,
        "astral-sh/setup-uv@6b9c6063abd6010835644d4c2e1bef4cf5cd0fca",
        "verify",
    )
    uv_with = uv_step.get("with", {})
    assert isinstance(uv_with, dict) and uv_with.get("version") == _UV_VERSION, (
        f"verify must pin uv {_UV_VERSION}"
    )
    assert uv_with.get("checksum") == _UV_ARCHIVE_SHA256, (
        "verify must validate the pinned uv release archive checksum"
    )

    history_job = jobs["secret-history"]
    history_steps = _workflow_steps(history_job, ci_path, "secret-history")
    checkout = _find_step_with_uses(
        history_steps,
        "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
        "secret-history",
    )
    checkout_with = checkout.get("with", {})
    assert isinstance(checkout_with, dict) and checkout_with.get("fetch-depth") == 0, (
        "secret-history must checkout full reachable history with fetch-depth: 0"
    )
    history_run = "\n".join(str(step.get("run", "")) for step in history_steps)
    assert _GITLEAKS_ARCHIVE_SHA256 in history_run and "sha256sum --check" in history_run, (
        "secret-history must verify the pinned Gitleaks archive checksum"
    )
    assert 'gitleaks detect --redact --log-opts="--all"' in history_run, (
        "secret-history must scan all reachable Git history with redacted output"
    )

    workflow_security = jobs["workflow-security"]
    security_steps = _workflow_steps(workflow_security, ci_path, "workflow-security")
    zizmor_step = _find_step_with_uses(security_steps, _ZIZMOR_ACTION, "workflow-security")
    zizmor_with = zizmor_step.get("with", {})
    assert isinstance(zizmor_with, dict), "workflow-security must configure zizmor"
    assert zizmor_with.get("advanced-security") is False, (
        "workflow-security must fail directly instead of relying on optional Advanced Security"
    )
    assert zizmor_with.get("online-audits") is True, (
        "workflow-security must explicitly enable zizmor online audits"
    )
    assert zizmor_with.get("version") == "1.30.1", (
        "workflow-security must pin the zizmor engine version"
    )

    codeowners_path = repo_root / ".github" / "CODEOWNERS"
    codeowners_rules = codeowners_path.read_text(encoding="utf-8").splitlines()
    assert any(
        rule.startswith("/.github/workflows/**") and "@ssra-org/secops" in rule.split()
        for rule in codeowners_rules
    ), "CODEOWNERS must require SSRA SecOps review for .github/workflows/**"
    assert any(
        rule.startswith("/.github/dependabot.yml") and "@ssra-org/secops" in rule.split()
        for rule in codeowners_rules
    ), "CODEOWNERS must require SSRA SecOps review for .github/dependabot.yml"


def verify_dependabot_policy(repo_root: Path) -> None:
    """Require a seven-day Dependabot cooldown for managed repository ecosystems."""
    dependabot_path = repo_root / ".github" / "dependabot.yml"
    raw = yaml.safe_load(dependabot_path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict), ".github/dependabot.yml must be a YAML mapping"
    assert raw.get("version") == 2, ".github/dependabot.yml must declare version: 2"
    updates = raw.get("updates")
    assert isinstance(updates, list), ".github/dependabot.yml must list update policies"

    by_ecosystem: dict[str, dict[object, object]] = {}
    for update in updates:
        assert isinstance(update, dict), "Each Dependabot update policy must be a mapping"
        ecosystem = update.get("package-ecosystem")
        if isinstance(ecosystem, str):
            by_ecosystem[ecosystem] = update

    for ecosystem in _DEPENDABOT_ECOSYSTEMS:
        policy = by_ecosystem.get(ecosystem)
        assert policy is not None, f".github/dependabot.yml must manage the '{ecosystem}' ecosystem"
        assert policy.get("directory") == "/", (
            f"Dependabot '{ecosystem}' updates must be rooted at the repository root"
        )
        schedule = policy.get("schedule")
        assert isinstance(schedule, dict) and schedule.get("interval") == "weekly", (
            f"Dependabot '{ecosystem}' updates must run weekly"
        )
        cooldown = policy.get("cooldown")
        assert isinstance(cooldown, dict) and int(cooldown.get("default-days", 0)) >= 7, (
            f"Dependabot '{ecosystem}' updates must enforce a seven-day cooldown"
        )


def verify_uv_cooldown_policy(repo_root: Path) -> None:
    """Require the rolling uv cooldown and only the reviewed certifi exception."""
    pyproj = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    uv_settings = pyproj.get("tool", {}).get("uv", {})
    assert isinstance(uv_settings, dict), "pyproject.toml must define [tool.uv]"
    assert uv_settings.get("required-version") == f"=={_UV_VERSION}", (
        f"pyproject.toml must pin uv to =={_UV_VERSION}"
    )
    assert uv_settings.get("exclude-newer") == "1 week", (
        "pyproject.toml must set a rolling seven-day uv exclude-newer cooldown"
    )

    expected_package_cutoffs = {"certifi": _CERTIFI_EXCLUDE_NEWER_CUTOFF}
    assert uv_settings.get("exclude-newer-package") == expected_package_cutoffs, (
        "uv cooldown exceptions must be limited to the documented DEP-EXC-002 certifi cutoff"
    )

    uv_lock = tomllib.loads((repo_root / "uv.lock").read_text(encoding="utf-8"))
    lock_options = uv_lock.get("options", {})
    assert isinstance(lock_options, dict), "uv.lock must define [options]"
    assert lock_options.get("exclude-newer-span") == "P1W", (
        "uv.lock must retain the rolling one-week cooldown span"
    )
    assert lock_options.get("exclude-newer-package") == expected_package_cutoffs, (
        "uv.lock must retain only the documented DEP-EXC-002 certifi cutoff"
    )

    certifi_packages = [
        package
        for package in uv_lock.get("package", [])
        if isinstance(package, dict) and package.get("name") == "certifi"
    ]
    assert len(certifi_packages) == 1, "uv.lock must contain exactly one certifi package record"
    certifi_package = certifi_packages[0]
    assert certifi_package.get("version") == _CERTIFI_VERSION, (
        f"uv.lock must pin certifi to {_CERTIFI_VERSION} for DEP-EXC-002"
    )
    assert certifi_package.get("source") == {"registry": "https://pypi.org/simple"}, (
        "uv.lock must resolve certifi from the reviewed PyPI registry"
    )
    sdist = certifi_package.get("sdist")
    assert isinstance(sdist, dict) and sdist.get("hash") == f"sha256:{_CERTIFI_SDIST_SHA256}", (
        "uv.lock certifi sdist must match the DEP-EXC-002 reviewed checksum"
    )
    wheels = certifi_package.get("wheels")
    assert isinstance(wheels, list) and any(
        isinstance(wheel, dict) and wheel.get("hash") == f"sha256:{_CERTIFI_WHEEL_SHA256}"
        for wheel in wheels
    ), "uv.lock certifi wheel must match the DEP-EXC-002 reviewed checksum"


def main() -> None:
    """Verify CI action SHA pinning, 7-day cooldowns, contract SHA parity, and Docker Compose hardening."""
    # 1. Verify GitHub Actions integrity, explicit token scopes, scanners, and workflow ownership.
    wf_dir = ROOT / ".github" / "workflows"
    verify_workflow_integrity(wf_dir)
    verify_ci_security_policy(ROOT)
    verify_dependabot_policy(ROOT)

    # 2. Verify pnpm's 7-day cooldown, provenance downgrade protection, and build-script deny-list.
    pnpm_ws = yaml.safe_load((ROOT / "pnpm-workspace.yaml").read_text(encoding="utf-8"))
    min_age = int(pnpm_ws.get("minimumReleaseAge", 0))
    assert min_age >= 10080, f"pnpm minimumReleaseAge {min_age} < 10080 (7 days)"
    assert pnpm_ws.get("trustPolicy") == "no-downgrade", (
        "pnpm-workspace.yaml must set trustPolicy: no-downgrade"
    )
    assert pnpm_ws.get("blockExoticSubdeps") is True, (
        "pnpm-workspace.yaml must set blockExoticSubdeps: true"
    )
    assert pnpm_ws.get("allowBuilds") == {}, (
        "pnpm-workspace.yaml must deny dependency build scripts until individually reviewed"
    )
    assert not pnpm_ws.get("minimumReleaseAgeExclude"), (
        "pnpm cooldown exclusions require a reviewed, time-bounded exception before use"
    )
    root_package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert root_package.get("packageManager") == f"pnpm@{_PNPM_VERSION}+{_PNPM_INTEGRITY}", (
        "package.json must pin the verified pnpm package-manager artifact"
    )
    engines = root_package.get("engines")
    assert isinstance(engines, dict) and engines.get("node") == _NODE_ENGINE, (
        f"package.json must bound Node.js to the Corepack-compatible {_NODE_ENGINE} range"
    )
    taskfile = (ROOT / "Taskfile.yml").read_text(encoding="utf-8")
    assert "node tools/verify_node_runtime.mjs" in taskfile, (
        "Taskfile.yml must fail before JavaScript gates run on an unsupported Node.js runtime"
    )
    for command in ("lint", "typecheck", "test"):
        assert f"corepack pnpm run {command}" in taskfile, (
            f"Taskfile.yml must invoke the project-pinned pnpm through Corepack for {command}"
        )

    # 3. Verify uv's pinned feature level, rolling cooldown, and sole reviewed exception.
    verify_uv_cooldown_policy(ROOT)

    # 4. The deployed applications are Node BFF servers. Fail if stale Next.js configuration resurfaces.
    for config_rel in ("apps/web/next.config.ts", "apps/console/next.config.ts"):
        assert not (ROOT / config_rel).exists(), (
            f"{config_rel} is stale: the deployed application runs its Node BFF server directly"
        )
    for package_rel in ("apps/web/package.json", "apps/console/package.json"):
        package = json.loads((ROOT / package_rel).read_text(encoding="utf-8"))
        declared = {
            dependency
            for field in (
                "dependencies",
                "devDependencies",
                "peerDependencies",
                "optionalDependencies",
            )
            for dependency in package.get(field, {})
        }
        assert "next" not in declared, (
            f"{package_rel} must not declare Next.js without an explicit runtime decision"
        )
    for dockerfile_rel, command in (
        ("apps/web/Dockerfile", 'CMD ["node", "apps/web/server.js"]'),
        ("apps/console/Dockerfile", 'CMD ["node", "apps/console/server.js"]'),
    ):
        dockerfile = (ROOT / dockerfile_rel).read_text(encoding="utf-8")
        assert command in dockerfile and "NEXT_TELEMETRY_DISABLED" not in dockerfile, (
            f"{dockerfile_rel} must identify the Node BFF server as its deployed runtime"
        )

    # 5. Verify external AI providers remain disabled by default until OQ-004 sign-off.
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

    # 7. Verify Living Docs, ADR catalog, phase evidence, model card, and CycloneDX 1.6 ML-BOM traceability.
    trace_skill = ROOT / ".agents" / "skills" / "living-docs-adr-runbooks-traceability" / "SKILL.md"
    assert trace_skill.is_file(), "Missing living-docs-adr-runbooks-traceability skill"
    r1_report = ROOT / "docs" / "audit" / "phase-R1-report.md"
    assert r1_report.is_file(), "Missing R1 assurance evidence report"
    r1_report_text = r1_report.read_text(encoding="utf-8")
    assert "Gate R1" in r1_report_text and "OQ-018" in r1_report_text, (
        "R1 assurance report must retain gate and artifact-trust disposition"
    )
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
        "Supply-chain, infra & living-docs traceability verification passed: 40-char SHA CI actions, "
        "Dependabot and package-manager 7-day cooldowns, contract SHA parity, non-root Dockerfiles, "
        "Seccomp, OTel memory_limiter, 11-server gateway, ADR catalog, and ML-BOM verified."
    )


if __name__ == "__main__":
    main()
