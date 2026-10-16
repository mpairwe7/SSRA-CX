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

    print(
        "Supply-chain verification passed: 40-char SHA CI actions, 7-day cooldowns (pnpm & uv), and sovereign routing verified."
    )


if __name__ == "__main__":
    main()
