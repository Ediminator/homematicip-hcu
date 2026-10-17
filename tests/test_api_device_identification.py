"""Test for Issue 120: HmIP-WLAN-HAP device identification."""

import pytest
from custom_components.hcu_integration.api import HcuApiClient


@pytest.mark.parametrize("model_type", ["HmIP-WLAN-HAP", "HmIP-HAP", "HmIP-DRAP"])
async def test_hcu_part_device_ids_excludes_auxiliary_aps(
    api_client: HcuApiClient, model_type: str
):
    """Test that auxiliary access points (HAP, DRAP, WLAN-HAP) are excluded from HCU part device IDs."""
    api_client._state = {
        "home": {
            "accessPointId": "hcu_device",
        },
        "devices": {
            "hcu_device": {
                "type": "HOME_CONTROL_ACCESS_POINT",
                "modelType": "HmIP-HCU-1",
                "id": "hcu_device",
            },
            "aux_ap_device": {
                "type": "HOME_CONTROL_ACCESS_POINT"
                if "DRAP" not in model_type
                else "WIRED_ACCESS_POINT",
                "modelType": model_type,
                "id": "aux_ap_device",
            },
        },
    }

    api_client._update_hcu_device_ids()

    assert api_client.hcu_device_id == "hcu_device"
    assert "hcu_device" in api_client.hcu_part_device_ids
    assert "aux_ap_device" not in api_client.hcu_part_device_ids
