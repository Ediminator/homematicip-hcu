import pytest
from custom_components.hcu_integration.util import get_device_manufacturer


class TestGetDeviceManufacturer:
    def test_explicit_oem(self):
        """Test that explicit OEM is returned if not eQ-3."""
        device = {"oem": "SomeManufacturer", "modelType": "HmIP-SWDO"}
        assert get_device_manufacturer(device) == "SomeManufacturer"

    def test_eq3_oem_ignored_if_hue_model(self):
        """Test that eQ-3 OEM is ignored if model type indicates Hue."""
        device = {"oem": "eQ-3", "modelType": "Hue ExtendedColorLight"}
        assert get_device_manufacturer(device) == "Philips Hue"

    def test_plugin_id_hue(self):
        """Test that de.eq3.plugin.hue returns Philips Hue."""
        device = {
            "type": "PLUGIN_EXTERNAL",
            "pluginId": "de.eq3.plugin.hue",
            "modelType": "915005987201",
        }
        assert get_device_manufacturer(device) == "Philips Hue"

    def test_plugin_external_generic(self):
        """Test that other PLUGIN_EXTERNAL devices are identified as 3rd Party."""
        device = {
            "type": "PLUGIN_EXTERNAL",
            "pluginId": "some.other.plugin",
            "modelType": "GenericThing",
        }
        assert get_device_manufacturer(device) == "3rd Party"

    def test_eq3_oem_ignored_if_plugin_id_hue(self):
        """Test that eQ-3 OEM is ignored if pluginId matches Hue."""
        device = {"oem": "eQ-3", "pluginId": "de.eq3.plugin.hue"}
        assert get_device_manufacturer(device) == "Philips Hue"

    def test_hue_in_model_type(self):
        """Test that Hue in model type returns Philips Hue (legacy fallback)."""
        device = {"modelType": "Philips Hue White"}
        assert get_device_manufacturer(device) == "Philips Hue"

    def test_standard_hmip_device(self):
        """Test that standard HmIP devices are identified as eQ-3."""
        device = {"modelType": "HmIP-eTRV-2"}
        assert get_device_manufacturer(device) == "eQ-3"

    def test_standard_hm_device(self):
        """Test that standard HM devices are identified as eQ-3."""
        device = {"modelType": "HM-Sec-MDIR"}
        assert get_device_manufacturer(device) == "eQ-3"

    def test_standard_alpha_device(self):
        """Test that ALPHA devices are identified as eQ-3."""
        device = {"modelType": "ALPHA-IP-RBG"}
        assert get_device_manufacturer(device) == "eQ-3"

    def test_unknown_device_defaults_eq3(self):
        """Test that unknown devices without markers default to eQ-3 (match existing behavior)."""
        device = {"modelType": "GenericSwitch"}
        assert get_device_manufacturer(device) == "eQ-3"

    def test_model_type_is_none(self):
        """Test that a device with modelType: None does not crash."""
        device = {"modelType": None}
        assert get_device_manufacturer(device) == "eQ-3"

    def test_model_type_is_missing(self):
        """Test that a device with a missing modelType does not crash."""
        device = {}
        assert get_device_manufacturer(device) == "eQ-3"
