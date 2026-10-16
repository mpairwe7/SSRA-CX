#!/usr/bin/env python3
"""PEP 669 (`sys.monitoring`) Coverage Gate Verifier for SSRA Assist (Section 10.5: Domain >= 90%, Overall >= 80%).

Uses Python 3.12+ `sys.monitoring` on an independent tool slot (`TOOL_ID = 4`) so Hypothesis
never resets tracing, and returns `sys.monitoring.DISABLE` on third-party code objects for
near-zero overhead.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import CodeType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL_ID = 4


def _executable_lines(py_file: Path) -> set[int]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    lines: set[int] = set()
    for fn_node in ast.walk(tree):
        if isinstance(fn_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(fn_node):
                if isinstance(
                    child,
                    (
                        ast.Assign,
                        ast.AugAssign,
                        ast.Return,
                        ast.Raise,
                        ast.Assert,
                        ast.If,
                        ast.For,
                        ast.While,
                    ),
                ) and hasattr(child, "lineno"):
                    lines.add(int(child.lineno))
    return lines


def _module_key(path: Path) -> str:
    parts = path.parts
    for marker in ("src", "site-packages"):
        if marker in parts:
            idx = len(parts) - 1 - parts[::-1].index(marker)
            return "/".join(parts[idx + 1 :])
    for idx in range(len(parts) - 1, -1, -1):
        if parts[idx].startswith("ssra_"):
            return "/".join(parts[idx:])
    return path.name


def main() -> None:
    executed_by_mod: dict[str, set[int]] = {}
    mon = sys.monitoring

    def _on_line(code: CodeType, line_number: int) -> Any:
        filename = code.co_filename
        if "ssra_" not in filename or "test_" in filename:
            return mon.DISABLE
        key = _module_key(Path(filename))
        executed_by_mod.setdefault(key, set()).add(line_number)
        return None

    mon.use_tool_id(TOOL_ID, "ssra_coverage_gate")
    mon.register_callback(TOOL_ID, mon.events.LINE, _on_line)
    mon.set_events(TOOL_ID, mon.events.LINE)
    try:
        exit_code = pytest.main(
            [
                "-q",
                "--ignore=evals/suites/test_golden_qa.py",
                "libs",
                "services",
                "mcp-servers",
                "evals",
            ]
        )
    finally:
        mon.set_events(TOOL_ID, 0)
        mon.register_callback(TOOL_ID, mon.events.LINE, None)
        mon.free_tool_id(TOOL_ID)

    if exit_code != 0:
        raise SystemExit(f"pytest failed during coverage check with exit code {exit_code}")

    domain_files = [
        *(ROOT / "services" / "api" / "src").glob("**/domain/*.py"),
        *(ROOT / "services" / "api" / "src").glob("**/application/*.py"),
        ROOT / "libs" / "ssra_rules" / "src" / "ssra_rules" / "engine.py",
        ROOT / "libs" / "ssra_core" / "src" / "ssra_core" / "clock.py",
        ROOT / "libs" / "ssra_core" / "src" / "ssra_core" / "ids.py",
        ROOT / "libs" / "ssra_security" / "src" / "ssra_security" / "audit.py",
        ROOT / "libs" / "ssra_security" / "src" / "ssra_security" / "redaction.py",
    ]
    overall_files = [
        *(ROOT / "libs").glob("**/src/**/*.py"),
        *(ROOT / "services").glob("**/src/**/*.py"),
        *(ROOT / "mcp-servers").glob("**/src/**/*.py"),
    ]

    dom_total = 0
    dom_hit = 0
    for f in domain_files:
        exec_set = _executable_lines(f)
        hits = exec_set & executed_by_mod.get(_module_key(f), set())
        dom_total += len(exec_set)
        dom_hit += len(hits)

    ov_total = 0
    ov_hit = 0
    for f in overall_files:
        exec_set = _executable_lines(f)
        hits = exec_set & executed_by_mod.get(_module_key(f), set())
        ov_total += len(exec_set)
        ov_hit += len(hits)

    dom_pct = (dom_hit / max(1, dom_total)) * 100.0
    ov_pct = (ov_hit / max(1, ov_total)) * 100.0

    assert dom_pct >= 90.0, f"Domain layer coverage {dom_pct:.1f}% < 90.0% gate"
    assert ov_pct >= 80.0, f"Overall Python coverage {ov_pct:.1f}% < 80.0% gate"
    print(
        f"Coverage gates passed: domain={dom_pct:.1f}% (>= 90.0%), overall={ov_pct:.1f}% (>= 80.0%)."
    )


if __name__ == "__main__":
    main()
