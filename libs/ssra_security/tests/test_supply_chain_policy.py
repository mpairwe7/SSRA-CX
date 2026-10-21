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


def _write_workflow(tmp_path: Path, uses: str, *, include_permissions: bool = True) -> Path:
    """Create the smallest representative workflow fixture for policy validation."""
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    permissions = "permissions: {}\n" if include_permissions else ""
    (workflows_dir / "fixture.yml").write_text(
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
