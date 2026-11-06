"""Acceptance tests for HACS release asset download tracking and analytics badges (EAC-hacs-download-stats)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_update_stats_module():
    script_path = REPO_ROOT / ".github" / "scripts" / "update_download_stats.py"
    spec = importlib.util.spec_from_file_location("update_download_stats", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hacs_json_enables_zip_release() -> None:
    """Verify hacs.json configures zip_release and filename for HACS download counting."""
    hacs_path = REPO_ROOT / "hacs.json"
    data = json.loads(hacs_path.read_text(encoding="utf-8"))

    assert data.get("zip_release") is True
    assert data.get("filename") == "hcu_integration.zip"
    assert data.get("content_in_root") is False
    assert data.get("render_readme") is True


def test_release_workflow_packages_and_uploads_zip() -> None:
    """Verify .github/workflows/release.yaml builds hcu_integration.zip from custom_components/hcu_integration."""
    workflow_path = REPO_ROOT / ".github" / "workflows" / "release.yaml"
    assert workflow_path.exists(), "Missing .github/workflows/release.yaml"

    content = workflow_path.read_text(encoding="utf-8")
    assert "release:" in content
    assert "published" in content
    assert "hcu_integration.zip" in content
    assert "custom_components/hcu_integration" in content
    assert "gh release upload" in content


def test_update_download_stats_writes_shields_badge(tmp_path: Path) -> None:
    """Verify update_download_stats.py writes a valid Shields.io endpoint badge.json and preserves it."""
    mod = _load_update_stats_module()

    out_dir = tmp_path / ".docs" / "downloads"
    out_dir.mkdir(parents=True)
    stale_file = out_dir / "stale.txt"
    stale_file.write_text("stale", encoding="utf-8")

    output_md = out_dir / "download_stats.md"
    history_json = out_dir / "history.json"
    chart_svg = out_dir / "chart.svg"
    badge_json = out_dir / "badge.json"

    assert hasattr(mod, "BADGE_PATH"), "update_download_stats.py must define BADGE_PATH"
    assert "badge.json" in mod.KEEP_FILES

    fake_analytics = {
        "hcu_integration": {
            "total": 370,
            "versions": {"2.7.0": 82, "2.6.1": 288},
        }
    }

    with (
        patch.object(mod, "OUTPUT_PATH", output_md),
        patch.object(mod, "HISTORY_PATH", history_json),
        patch.object(mod, "CHART_PATH", chart_svg),
        patch.object(mod, "BADGE_PATH", badge_json),
        patch.object(mod, "fetch_analytics", return_value=fake_analytics),
    ):
        mod.main()

    assert not stale_file.exists(), "Stale files not in KEEP_FILES should be cleaned up"
    assert badge_json.exists(), "badge.json must be generated"

    badge_data = json.loads(badge_json.read_text(encoding="utf-8"))
    assert badge_data == {
        "schemaVersion": 1,
        "label": "active installations",
        "message": "370",
        "color": "blue",
    }


def test_readme_contains_download_and_installation_badges() -> None:
    """Verify README.md displays both the active installations badge and GitHub downloads badge."""
    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "img.shields.io/endpoint" in readme_text
    assert ".docs/downloads/badge.json" in readme_text
    assert ".docs/downloads/download_stats.md" in readme_text
    assert (
        "img.shields.io/github/downloads/Ediminator/homematicip-hcu/total"
        in readme_text
    )
