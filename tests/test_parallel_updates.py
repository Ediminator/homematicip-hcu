"""Every platform declares PARALLEL_UPDATES (Silver rule parallel-updates)."""

from __future__ import annotations

from importlib import import_module

import pytest

from custom_components.hcu_integration.const import PLATFORMS


@pytest.mark.parametrize("platform", PLATFORMS, ids=str)
def test_platform_allows_parallel_updates(platform: str) -> None:
    module = import_module(f"custom_components.hcu_integration.{platform}")

    # The HCU pushes state changes, so there is no polling to limit.
    assert module.PARALLEL_UPDATES == 0
