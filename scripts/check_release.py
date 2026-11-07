#!/usr/bin/env python3
"""Check a release before its zip asset is uploaded.

HACS and the Home Assistant Marketplace show the release tag as the version
and install the zip asset named in hacs.json. This script fails the release
job when the tag does not match the version in manifest.json and
const.PLUGIN_VERSION, or when the built zip would not install as
custom_components/<domain>/.

Usage:
    check_release.py --tag 2.7.1 [--root DIR] [--zip hcu_integration.zip]

Only the standard library is used, so the workflow needs no extra setup.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile

INTEGRATION_DIR = Path("custom_components") / "hcu_integration"
# Top-level folders of the repository that must never end up in the asset.
FORBIDDEN_TOP_LEVEL = {"tests", ".github"}


def _read_manifest(root: Path) -> dict:
    return json.loads(
        (root / INTEGRATION_DIR / "manifest.json").read_text(encoding="utf-8")
    )


def read_plugin_version(root: Path) -> str | None:
    """Return the literal PLUGIN_VERSION from const.py without importing it."""
    tree = ast.parse((root / INTEGRATION_DIR / "const.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "PLUGIN_VERSION"
                for target in node.targets
            )
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    return None


def check_versions(root: Path, tag: str) -> list[str]:
    """Return an error for each version source that differs from the tag."""
    errors = []
    manifest_version = _read_manifest(root).get("version")
    if manifest_version != tag:
        errors.append(
            f"Release tag {tag} does not match manifest.json version "
            f"{manifest_version}. Bump the version or fix the tag."
        )
    plugin_version = read_plugin_version(root)
    if plugin_version is None:
        errors.append("const.py has no string literal PLUGIN_VERSION.")
    elif plugin_version != tag:
        errors.append(
            f"Release tag {tag} does not match const.PLUGIN_VERSION "
            f"{plugin_version}. Bump the version or fix the tag."
        )
    return errors


def _bad_member(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        path.is_absolute()
        or ".." in path.parts
        or path.parts[0] in FORBIDDEN_TOP_LEVEL
        or "__pycache__" in path.parts
        or path.suffix == ".pyc"
    )


def check_zip(zip_path: Path, root: Path, tag: str) -> list[str]:
    """Return an error for each problem that would break the install from the zip."""
    try:
        with zipfile.ZipFile(zip_path) as archive:
            names = archive.namelist()
            manifest_raw = (
                archive.read("manifest.json") if "manifest.json" in names else None
            )
    except zipfile.BadZipFile:
        return [f"{zip_path.name} is not a valid zip archive."]

    errors = [
        f"{zip_path.name} contains {name}, which does not belong in the release."
        for name in names
        if _bad_member(name)
    ]

    if manifest_raw is None:
        errors.append(
            f"manifest.json is not at the root of {zip_path.name}. HACS extracts "
            "the zip into custom_components/<domain>/, so the integration files "
            "must not be in a subfolder."
        )
        return errors

    try:
        zip_manifest = json.loads(manifest_raw)
    except ValueError:
        errors.append(f"manifest.json in {zip_path.name} is not valid JSON.")
        return errors

    domain = _read_manifest(root).get("domain")
    if zip_manifest.get("domain") != domain:
        errors.append(
            f"manifest.json in {zip_path.name} has domain "
            f"{zip_manifest.get('domain')}, expected {domain}."
        )
    if zip_manifest.get("version") != tag:
        errors.append(
            f"manifest.json in {zip_path.name} has version "
            f"{zip_manifest.get('version')}, expected {tag}."
        )
    return errors


def main(argv: list[str] | None = None) -> int:
    """Run the checks and print GitHub Actions error annotations."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="release tag, e.g. 2.7.1")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
        help="checkout of the release tag (default: current directory)",
    )
    parser.add_argument("--zip", type=Path, help="built release asset to check")
    args = parser.parse_args(argv)

    errors = check_versions(args.root, args.tag)
    if args.zip is not None:
        errors += check_zip(args.zip, args.root, args.tag)

    for error in errors:
        print(f"::error::{error}")
    if errors:
        return 1
    checked = f"versions and {args.zip.name}" if args.zip else "versions"
    print(f"Release {args.tag}: {checked} OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
