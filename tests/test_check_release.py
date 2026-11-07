"""Tests for scripts/check_release.py, the release asset guard used by release.yaml."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import runpy
import sys
import zipfile

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_release.py"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "release.yaml"
DOMAIN = "hcu_integration"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_release", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(name="check_release")
def fixture_check_release():
    """Load the script as a module."""
    return _load_module()


def _write_repo(
    root: Path, manifest_version: str, plugin_version: str | None = None
) -> Path:
    """Create the two version sources the script reads in a fake repository."""
    integration = root / "custom_components" / DOMAIN
    integration.mkdir(parents=True)
    manifest = {"domain": DOMAIN, "name": "Test", "version": manifest_version}
    (integration / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (integration / "const.py").write_text(
        f'DOMAIN = "{DOMAIN}"\nPLUGIN_VERSION = "{plugin_version or manifest_version}"\n',
        encoding="utf-8",
    )
    return root


def _write_zip(path: Path, members: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return path


def _good_members(version: str) -> dict[str, str]:
    return {
        "manifest.json": json.dumps({"domain": DOMAIN, "version": version}),
        "__init__.py": "",
        "brand/icon.png": "png",
        "translations/en.json": "{}",
    }


def test_matching_versions_and_zip_pass(tmp_path: Path, check_release) -> None:
    """Tag, manifest, PLUGIN_VERSION and the zip all agree: no errors, exit 0."""
    root = _write_repo(tmp_path / "repo", "2.7.1")
    asset = _write_zip(tmp_path / "hcu_integration.zip", _good_members("2.7.1"))

    assert check_release.check_versions(root, "2.7.1") == []
    assert check_release.check_zip(asset, root, "2.7.1") == []
    assert (
        check_release.main(["--tag", "2.7.1", "--root", str(root), "--zip", str(asset)])
        == 0
    )


def test_tag_differs_from_manifest(tmp_path: Path, check_release, capsys) -> None:
    """A release tag that is not the manifest version fails the job."""
    root = _write_repo(tmp_path / "repo", "2.7.0")

    errors = check_release.check_versions(root, "2.7.1")

    assert len(errors) == 2
    assert "manifest.json" in errors[0]
    assert "2.7.0" in errors[0]
    assert "2.7.1" in errors[0]
    assert "PLUGIN_VERSION" in errors[1]
    assert check_release.main(["--tag", "2.7.1", "--root", str(root)]) == 1
    assert "::error::" in capsys.readouterr().out


def test_plugin_version_differs_from_tag(tmp_path: Path, check_release) -> None:
    """const.PLUGIN_VERSION left behind on a release bump fails the job."""
    root = _write_repo(tmp_path / "repo", "2.7.1", plugin_version="2.7.0")

    errors = check_release.check_versions(root, "2.7.1")

    assert len(errors) == 1
    assert "PLUGIN_VERSION" in errors[0]
    assert "2.7.0" in errors[0]


def test_v_prefixed_tag_is_rejected(tmp_path: Path, check_release) -> None:
    """HACS shows the tag as the version, so 'v2.7.1' does not match '2.7.1'."""
    root = _write_repo(tmp_path / "repo", "2.7.1")

    assert len(check_release.check_versions(root, "v2.7.1")) == 2


def test_missing_plugin_version_is_reported(tmp_path: Path, check_release) -> None:
    """A const.py without a literal PLUGIN_VERSION is an error, not a silent pass."""
    root = _write_repo(tmp_path / "repo", "2.7.1")
    (root / "custom_components" / DOMAIN / "const.py").write_text(
        'DOMAIN = "hcu_integration"\n', encoding="utf-8"
    )

    errors = check_release.check_versions(root, "2.7.1")

    assert len(errors) == 1
    assert "PLUGIN_VERSION" in errors[0]


@pytest.mark.parametrize(
    ("members", "expected"),
    [
        pytest.param(
            {
                f"custom_components/{DOMAIN}/manifest.json": json.dumps(
                    {"domain": DOMAIN, "version": "2.7.1"}
                ),
                f"custom_components/{DOMAIN}/__init__.py": "",
            },
            "manifest.json is not at the root",
            id="nested-directory",
        ),
        pytest.param(
            {**_good_members("2.7.1"), "tests/test_api.py": ""},
            "tests/test_api.py",
            id="tests-included",
        ),
        pytest.param(
            {**_good_members("2.7.1"), ".github/workflows/release.yaml": ""},
            ".github/workflows/release.yaml",
            id="github-included",
        ),
        pytest.param(
            {**_good_members("2.7.1"), "__pycache__/api.cpython-314.pyc": ""},
            "__pycache__/api.cpython-314.pyc",
            id="bytecode-included",
        ),
        pytest.param(
            {**_good_members("2.7.1"), "../evil.py": ""},
            "../evil.py",
            id="path-outside-folder",
        ),
        pytest.param(
            _good_members("2.7.0"),
            "version 2.7.0",
            id="stale-manifest-version",
        ),
        pytest.param(
            {
                **_good_members("2.7.1"),
                "manifest.json": json.dumps({"domain": "other", "version": "2.7.1"}),
            },
            "domain other",
            id="wrong-domain",
        ),
        pytest.param(
            {**_good_members("2.7.1"), "manifest.json": "{not json"},
            "not valid JSON",
            id="broken-manifest",
        ),
    ],
)
def test_bad_zip_is_rejected(
    tmp_path: Path, check_release, members: dict[str, str], expected: str
) -> None:
    """Each kind of broken asset gives an error naming the problem."""
    root = _write_repo(tmp_path / "repo", "2.7.1")
    asset = _write_zip(tmp_path / "hcu_integration.zip", members)

    errors = check_release.check_zip(asset, root, "2.7.1")

    assert any(expected in error for error in errors), errors
    assert (
        check_release.main(["--tag", "2.7.1", "--root", str(root), "--zip", str(asset)])
        == 1
    )


def test_file_that_is_not_a_zip(tmp_path: Path, check_release) -> None:
    """An upload that is not a zip archive is reported instead of crashing."""
    root = _write_repo(tmp_path / "repo", "2.7.1")
    asset = tmp_path / "hcu_integration.zip"
    asset.write_text("not a zip", encoding="utf-8")

    errors = check_release.check_zip(asset, root, "2.7.1")

    assert len(errors) == 1
    assert "not a valid zip" in errors[0]


def test_current_repository_versions_agree(check_release) -> None:
    """The real manifest and PLUGIN_VERSION pass the check for their own version."""
    manifest = json.loads(
        (REPO_ROOT / "custom_components" / DOMAIN / "manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert check_release.check_versions(REPO_ROOT, manifest["version"]) == []


def test_script_entry_point_exit_code(tmp_path: Path, monkeypatch, capsys) -> None:
    """Run as a script, a mismatch ends the process with exit code 1."""
    root = _write_repo(tmp_path / "repo", "2.7.0")
    monkeypatch.setattr(
        sys, "argv", [str(SCRIPT_PATH), "--tag", "2.7.1", "--root", str(root)]
    )

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

    assert exc_info.value.code == 1
    assert "::error::Release tag 2.7.1" in capsys.readouterr().out


def test_release_workflow_runs_the_checks_before_upload() -> None:
    """release.yaml checks the versions before building and the zip before uploading."""
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["package-release"]["steps"]
    runs = [step.get("run", "") for step in steps]

    def index_of(matches_step) -> int:
        matches = [i for i, run in enumerate(runs) if matches_step(run)]
        assert len(matches) == 1, runs
        return matches[0]

    version_check = index_of(
        lambda run: "scripts/check_release.py" in run and "--zip" not in run
    )
    build = index_of(lambda run: "zip -r" in run)
    zip_check = index_of(
        lambda run: (
            "scripts/check_release.py" in run and "--zip hcu_integration.zip" in run
        )
    )
    upload = index_of(lambda run: "gh release upload" in run)

    assert version_check < build < zip_check < upload
