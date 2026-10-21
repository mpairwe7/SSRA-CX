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
wheels = [{{ hash = "sha256:{wheel_hash}" }}]
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

    with pytest.raises(AssertionError, match="reviewed checksum"):
        _uv_cooldown_policy_verifier()(tmp_path)
