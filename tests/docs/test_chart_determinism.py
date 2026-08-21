"""The no-drift rule for generated charts, enforced rather than stated.

A2 established the rule that CI fails if regenerating a chart produces a diff.
Its charts embed a creation timestamp, so the rule could not actually run. A3
strips the timestamp and pins matplotlib's SVG hash salt, which makes the check
executable — and an executable check is the only kind worth having.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("matplotlib")

ASSETS_DIR = Path(__file__).resolve().parents[2] / "docs" / "assets"


def _digests() -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(ASSETS_DIR.glob("*.svg"))
    }


def test_regenerating_charts_produces_no_diff(repo_root: Path, tmp_path: Path) -> None:
    before = _digests()
    assert before, "no generated charts found"

    backup = tmp_path / "assets"
    shutil.copytree(ASSETS_DIR, backup)
    try:
        # Same invocation as `make docs-assets`: the script imports the fixture
        # builder, so the repo root has to be importable.
        environment = dict(os.environ, PYTHONPATH=str(repo_root))
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [sys.executable, str(repo_root / "docs" / "generate_plots.py")],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )
        assert result.returncode == 0, result.stderr
        assert _digests() == before, (
            "Regenerating the charts changed them. Either the data moved and the "
            "committed charts are stale, or chart generation is not deterministic."
        )
    finally:
        for path in backup.glob("*.svg"):
            shutil.copy2(path, ASSETS_DIR / path.name)
