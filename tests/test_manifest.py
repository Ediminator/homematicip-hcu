"""Tests for custom_components/hcu_integration/manifest.json metadata and pins."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import getmac.getmac
import homeassistant
from packaging.requirements import Requirement

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "custom_components" / "hcu_integration" / "manifest.json"


def _load_manifest() -> dict[str, Any]:
    """Load the integration manifest as a dictionary."""
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_declares_category_and_loggers() -> None:
    """Verify manifest.json declares the Marketplace category and getmac logger."""
    manifest = _load_manifest()

    assert manifest["categories"] == ["hubs_protocols.smart_home_hubs"]
    assert manifest["loggers"] == ["getmac"]


def test_manifest_loggers_match_the_library() -> None:
    """Verify every manifest logger name matches the getmac logger name."""
    manifest = _load_manifest()
    loggers = manifest["loggers"]

    assert loggers
    assert all(name == getmac.getmac.log.name for name in loggers)


def test_manifest_keys_are_sorted() -> None:
    """Verify manifest.json keeps domain and name first, then alphabetical keys."""
    pairs = json.loads(
        MANIFEST_PATH.read_text(encoding="utf-8"), object_pairs_hook=list
    )
    keys = [key for key, _value in pairs]

    assert keys[:2] == ["domain", "name"]
    assert keys[2:] == sorted(keys[2:])


def test_manifest_requirements_fit_home_assistant_pins() -> None:
    """Verify our getmac requirement allows versions pinned by core integrations."""
    ha_components = Path(homeassistant.__file__).resolve().parent / "components"
    pinned_versions = [
        (comp_manifest.parent.name, spec.version)
        for comp_manifest in sorted(ha_components.glob("*/manifest.json"))
        for raw_req in json.loads(comp_manifest.read_text(encoding="utf-8")).get(
            "requirements", []
        )
        if (req := Requirement(raw_req)).name.lower() == "getmac"
        for spec in req.specifier
        if spec.operator == "=="
    ]

    assert pinned_versions, "Expected core integrations pinning getmac in installed HA"

    manifest = _load_manifest()
    getmac_reqs = [
        Requirement(raw_req)
        for raw_req in manifest.get("requirements", [])
        if Requirement(raw_req).name.lower() == "getmac"
    ]
    assert len(getmac_reqs) == 1
    our_specifier = getmac_reqs[0].specifier

    for component, pinned in pinned_versions:
        assert our_specifier.contains(pinned), (
            f"Our getmac requirement '{getmac_reqs[0]}' excludes "
            f"'{component}' pin 'getmac=={pinned}'"
        )
