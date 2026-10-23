"""Regression tests for repository-owned CI supply-chain policy checks."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
VERIFY_SUPPLY_CHAIN_PATH = REPOSITORY_ROOT / "tools" / "verify_supply_chain_and_signatures.py"


def _workflow_verifier() -> Callable[[Path], None]:
    """Load the policy function without making tools a runtime package."""
    spec = importlib.util.spec_from_file_location("supply_chain_verifier", VERIFY_SUPPLY_CHAIN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(Callable[[Path], None], module.__dict__["verify_workflow_integrity"])


def _write_workflow(
    tmp_path: Path,
    uses: str,
    *,
    include_permissions: bool = True,
    filename: str = "fixture.yml",
) -> Path:
    """Create the smallest representative workflow fixture for policy validation."""
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    permissions = "permissions: {}\n" if include_permissions else ""
    (workflows_dir / filename).write_text(
        "\n".join(
            (
                "name: fixture",
                permissions.rstrip(),
                "jobs:",
                "  verify:",
                "    permissions: {}",
                "    runs-on: ubuntu-latest",
                "    steps:",
                f"      - uses: {uses}",
                "        with:",
                "          persist-credentials: false",
                "",
            )
        ),
        encoding="utf-8",
    )
    return workflows_dir


def _dependabot_verifier() -> Callable[[Path], None]:
    """Load the Dependabot policy check without making tools a runtime package."""
    spec = importlib.util.spec_from_file_location("supply_chain_verifier", VERIFY_SUPPLY_CHAIN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(Callable[[Path], None], module.__dict__["verify_dependabot_policy"])


def _ci_security_policy_verifier() -> Callable[[Path], None]:
    """Load the CI-specific policy check without making tools a runtime package."""
    spec = importlib.util.spec_from_file_location("supply_chain_verifier", VERIFY_SUPPLY_CHAIN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(Callable[[Path], None], module.__dict__["verify_ci_security_policy"])


def _uv_cooldown_policy_verifier() -> Callable[[Path], None]:
    """Load the uv cooldown policy check without making tools a runtime package."""
    spec = importlib.util.spec_from_file_location("supply_chain_verifier", VERIFY_SUPPLY_CHAIN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(Callable[[Path], None], module.__dict__["verify_uv_cooldown_policy"])


def _write_uv_policy_fixture(
    tmp_path: Path,
    *,
    package_name: str = "certifi",
    wheel_hash: str = "42d35340cc5b9ba78e818ddbff0c5b1c2b779de448a340fd1b989f5fa8670e1b",
    extra_wheel_hash: str | None = None,
) -> None:
    """Create the smallest lock pair that satisfies the reviewed uv exception."""
    cutoff = "2026-10-21T00:00:00Z"
    (tmp_path / "pyproject.toml").write_text(
        f'''[tool.uv]
required-version = "==0.13.4"
exclude-newer = "1 week"
exclude-newer-package = {{ {package_name} = "{cutoff}" }}
''',
        encoding="utf-8",
    )
    wheels = f'{{ hash = "sha256:{wheel_hash}" }}'
    if extra_wheel_hash is not None:
        wheels += f', {{ hash = "sha256:{extra_wheel_hash}" }}'
    (tmp_path / "uv.lock").write_text(
        f'''version = 1

[options]
exclude-newer-span = "P1W"

[options.exclude-newer-package]
certifi = "{cutoff}"

[[package]]
name = "certifi"
version = "2026.10.19"
source = {{ registry = "https://pypi.org/simple" }}
sdist = {{ hash = "sha256:035c1e85572b141bf1c3a3eff0e33a8eb74917522f2559075ff8d2fea780a1ae" }}
wheels = [{wheels}]
''',
        encoding="utf-8",
    )


def test_workflow_policy_rejects_tag_pinned_action(tmp_path: Path) -> None:
    """A mutable action tag must fail before an unsafe workflow can merge."""
    workflows_dir = _write_workflow(tmp_path, "actions/checkout@v4")

    with pytest.raises(AssertionError, match="Unpinned GitHub Action"):
        _workflow_verifier()(workflows_dir)


def test_workflow_policy_requires_default_permissions(tmp_path: Path) -> None:
    """Every workflow must deny token scopes until a job opts in explicitly."""
    workflows_dir = _write_workflow(
        tmp_path,
        "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
        include_permissions=False,
    )

    with pytest.raises(AssertionError, match="permissions"):
        _workflow_verifier()(workflows_dir)


@pytest.mark.parametrize(
    "trigger",
    (
        "on: pull_request_target",
        "on: [pull_request, pull_request_target]",
        "on:\n  pull_request_target: {}",
    ),
)
def test_workflow_policy_rejects_all_pull_request_target_trigger_forms(
    tmp_path: Path, trigger: str
) -> None:
    """The forbidden trigger must fail for each valid GitHub Actions YAML form."""
    workflows_dir = _write_workflow(
        tmp_path,
        "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
    )
    workflow_path = workflows_dir / "fixture.yml"
    workflow_path.write_text(
        f"{trigger}\n{workflow_path.read_text(encoding='utf-8')}", encoding="utf-8"
    )

    with pytest.raises(AssertionError, match="pull_request_target"):
        _workflow_verifier()(workflows_dir)


def test_workflow_policy_checks_yaml_extension(tmp_path: Path) -> None:
    """A `.yaml` workflow must receive the same immutable-action validation as `.yml`."""
    workflows_dir = _write_workflow(tmp_path, "actions/checkout@v4", filename="fixture.yaml")

    with pytest.raises(AssertionError, match="Unpinned GitHub Action"):
        _workflow_verifier()(workflows_dir)


def test_dependabot_policy_rejects_a_short_cooldown(tmp_path: Path) -> None:
    """Dependency update automation must retain the repository's seven-day holdback."""
    dependabot_dir = tmp_path / ".github"
    dependabot_dir.mkdir()
    (dependabot_dir / "dependabot.yml").write_text(
        """version: 2
updates:
  - package-ecosystem: npm
    directory: /
    schedule: {interval: weekly}
    cooldown: {default-days: 6}
  - package-ecosystem: uv
    directory: /
    schedule: {interval: weekly}
    cooldown: {default-days: 7}
  - package-ecosystem: github-actions
    directory: /
    schedule: {interval: weekly}
    cooldown: {default-days: 7}
""",
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match="seven-day cooldown"):
        _dependabot_verifier()(tmp_path)


def test_ci_policy_rejects_duplicate_pnpm_version_source(tmp_path: Path) -> None:
    """CI must use the integrity-pinned packageManager declaration as its only pnpm source."""
    source = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    action = "uses: pnpm/action-setup@a7487c7e89a18df4991f7f222e4898a00d66ddda # v4.1.0"
    assert action in source
    fixture = source.replace(
        action,
        f'{action}\n        with:\n          version: "10.33.0"',
        1,
    )
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "ci.yml").write_text(fixture, encoding="utf-8")
    (tmp_path / ".github" / "CODEOWNERS").write_text(
        "/.github/workflows/** @ssra-org/secops\n/.github/dependabot.yml @ssra-org/secops\n",
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match="derive pnpm"):
        _ci_security_policy_verifier()(tmp_path)


def test_uv_policy_rejects_an_unreviewed_package_cooldown_exception(tmp_path: Path) -> None:
    """Only the short-lived, reviewed certifi cutoff may bypass uv's age holdback."""
    _write_uv_policy_fixture(tmp_path, package_name="requests")

    with pytest.raises(AssertionError, match="DEP-EXC-002"):
        _uv_cooldown_policy_verifier()(tmp_path)


def test_uv_policy_rejects_an_unverified_certifi_wheel(tmp_path: Path) -> None:
    """The exception must pin the reviewed certifi artifact, not merely its version."""
    _write_uv_policy_fixture(tmp_path, wheel_hash="0" * 64)

    with pytest.raises(AssertionError, match="reviewed artifact set"):
        _uv_cooldown_policy_verifier()(tmp_path)


def test_uv_policy_rejects_an_additional_certifi_wheel(tmp_path: Path) -> None:
    """The reviewed exception permits exactly the expected certifi wheel artifact."""
    _write_uv_policy_fixture(tmp_path, extra_wheel_hash="0" * 64)

    with pytest.raises(AssertionError, match="reviewed artifact set"):
        _uv_cooldown_policy_verifier()(tmp_path)


def _sec_pipeline_module() -> dict[str, object]:
    """Load `tools/run_sast_dast_sec_pipeline.py` for direct regression testing."""
    sec_path = REPOSITORY_ROOT / "tools" / "run_sast_dast_sec_pipeline.py"
    spec = importlib.util.spec_from_file_location("sec_pipeline_runner", sec_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.__dict__


def test_ci_policy_rejects_compromised_trivy_v0694_in_workflow(tmp_path: Path) -> None:
    """CI policy must block the March 2026 compromised Trivy v0.69.4 release."""
    source = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    fixture = source.replace("v0.69.3", "v0.69.4")
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "ci.yml").write_text(fixture, encoding="utf-8")
    (tmp_path / ".github" / "CODEOWNERS").write_text(
        "/.github/workflows/** @ssra-org/secops\n/.github/dependabot.yml @ssra-org/secops\n",
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match=r"Trivy v0\.69\.3"):
        _ci_security_policy_verifier()(tmp_path)


def test_ci_policy_rejects_missing_trufflehog_verification_in_secret_history(
    tmp_path: Path,
) -> None:
    """secret-history must retain SHA-256 verified TruffleHog v3 with --no-update."""
    source = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    fixture = source.replace(
        "trufflehog git file://. --results=verified --fail --no-update",
        "trufflehog git file://. --results=verified --fail",
    )
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "ci.yml").write_text(fixture, encoding="utf-8")
    (tmp_path / ".github" / "CODEOWNERS").write_text(
        "/.github/workflows/** @ssra-org/secops\n/.github/dependabot.yml @ssra-org/secops\n",
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match="TruffleHog v3"):
        _ci_security_policy_verifier()(tmp_path)


def test_python_sast_rejects_eval_and_unbounded_httpx_client(tmp_path: Path) -> None:
    """Python AST SAST must block dangerous sinks (including import aliases), SQL +, and unbounded httpx."""
    mod = _sec_pipeline_module()
    sast_fn = cast(Callable[[Path], list[dict[str, str]]], mod["run_python_ast_and_agentic_sast"])

    libs_dir = tmp_path / "libs" / "sample"
    libs_dir.mkdir(parents=True)
    bad_file = libs_dir / "bad.py"
    bad_file.write_text("x = eval('1 + 1')\n", encoding="utf-8")

    with pytest.raises(AssertionError, match="SAST-PY-01"):
        sast_fn(tmp_path)

    bad_file.write_text(
        "from pickle import loads as decode_blob\nx = decode_blob(b'123')\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="SAST-PY-01"):
        sast_fn(tmp_path)

    bad_file.write_text(
        'def q(session, uid):\n    return session.execute("SELECT * FROM t WHERE id = " + uid)\n',
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="SAST-PY-02"):
        sast_fn(tmp_path)

    bad_file.write_text("import httpx\nclient = httpx.Client()\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="SAST-PY-03"):
        sast_fn(tmp_path)

    bad_file.write_text('import httpx\nres = httpx.get("https://example.com")\n', encoding="utf-8")
    with pytest.raises(AssertionError, match="SAST-PY-03"):
        sast_fn(tmp_path)


def test_frontend_sast_rejects_raw_innerhtml_assignment(tmp_path: Path) -> None:
    """Frontend SAST must reject raw innerHTML, +=, and insertAdjacentHTML sinks while allowing ==."""
    mod = _sec_pipeline_module()
    fe_sast_fn = cast(Callable[[Path], list[dict[str, str]]], mod["run_frontend_and_bff_sast"])

    web_src = tmp_path / "apps" / "web" / "src"
    web_src.mkdir(parents=True)
    target = web_src / "xss.ts"
    target.write_text(
        "export function render(el: HTMLElement, html: string) { el.innerHTML += html; }\n",
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match="SAST-FE-01"):
        fe_sast_fn(tmp_path)

    target.write_text(
        'export function render(el: HTMLElement, html: string) { el.insertAdjacentHTML("beforeend", html); }\n',
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="SAST-FE-01"):
        fe_sast_fn(tmp_path)


def test_scanner_runner_rejects_unverified_path_binary(tmp_path: Path) -> None:
    """Scanner command runner must reject binaries outside the SHA-256 verified cache root or with wrong digest."""
    mod = _sec_pipeline_module()
    run_cmd = cast(Callable[..., None], mod["_run_verified_scanner_cmd"])
    cache_root_fn = cast(Callable[[], Path], mod["_get_owner_safe_scanner_cache_root"])

    with pytest.raises(AssertionError, match="ssra-verified-scanners"):
        run_cmd(
            ["/usr/bin/gitleaks", "detect"],
            cwd=tmp_path,
            expected_binary_sha256="0" * 64,
        )

    cache_root = cache_root_fn()
    fake_bin = cache_root / "tampered-scanner"
    fake_bin.write_bytes(b"#!/bin/sh\nexit 0\n")
    fake_bin.chmod(0o700)
    try:
        with pytest.raises(AssertionError, match="TOCTOU binary SHA-256 mismatch"):
            run_cmd(
                [str(fake_bin)],
                cwd=tmp_path,
                expected_binary_sha256="f" * 64,
            )
    finally:
        fake_bin.unlink(missing_ok=True)


def test_cicd_pipeline_model_and_live_asgi_dast_suite_pass() -> None:
    """Repository CI/CD model parity, Python/Frontend SAST, Live ASGI/BFF DAST, and SARIF builder must pass."""
    mod = _sec_pipeline_module()
    verify_model = cast(Callable[[Path], list[dict[str, str]]], mod["verify_cicd_pipeline_model"])
    py_sast = cast(Callable[[Path], list[dict[str, str]]], mod["run_python_ast_and_agentic_sast"])
    fe_sast = cast(Callable[[Path], list[dict[str, str]]], mod["run_frontend_and_bff_sast"])
    live_dast = cast(Callable[[], list[dict[str, str]]], mod["run_live_in_process_dast"])
    build_sarif = cast(
        Callable[[list[dict[str, str]]], dict[str, object]], mod["build_sarif_report"]
    )

    summaries = [
        *verify_model(REPOSITORY_ROOT),
        *py_sast(REPOSITORY_ROOT),
        *fe_sast(REPOSITORY_ROOT),
        *live_dast(),
    ]
    assert len(summaries) == 6
    sarif = build_sarif(summaries)
    assert sarif["version"] == "2.1.0"
    runs = sarif["runs"]
    assert isinstance(runs, list) and len(runs) == 1
    run_obj = runs[0]
    assert isinstance(run_obj, dict)
    assert isinstance(run_obj.get("invocations"), list) and len(run_obj["invocations"]) == 1
    assert isinstance(run_obj.get("artifacts"), list) and len(run_obj["artifacts"]) == 6
