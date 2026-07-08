"""CLI smoke tests for import-time regressions."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_help(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, script, "--help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_root_cli_help_imports() -> None:
    """The root CLI should show usage without import-time errors."""
    result = _run_help("convert_to_vrs.py")

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()
    assert "--imu" in result.stdout
    assert "--compression" in result.stdout


def test_legacy_cli_help_imports_or_deprecates_cleanly() -> None:
    """The legacy CLI should either work or fail with an intentional deprecation."""
    result = _run_help("scripts/convert_rosbag_to_vrs.py")
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "usage:" in output.lower() or "deprecated" in output.lower()
    assert "create_phase_4a_config" not in output
