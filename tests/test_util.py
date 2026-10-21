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


class TestGetSecurityHome:
    def test_security_home_found(self):
        """Test returning the SECURITY_AND_ALARM functional home."""
        from custom_components.hcu_integration.util import get_security_home

        home = {
            "functionalHomes": {
                "INDOOR_CLIMATE": {"solution": "INDOOR_CLIMATE"},
                "SECURITY_AND_ALARM": {
                    "solution": "SECURITY_AND_ALARM",
                    "alarmActive": False,
                },
            }
        }
        sec_home = get_security_home(home)
        assert sec_home == {"solution": "SECURITY_AND_ALARM", "alarmActive": False}

    def test_security_home_not_found(self):
        """Test returning empty dict when no SECURITY_AND_ALARM exists."""
        from custom_components.hcu_integration.util import get_security_home

        home = {
            "functionalHomes": {
                "INDOOR_CLIMATE": {"solution": "INDOOR_CLIMATE"},
            }
        }
        assert get_security_home(home) == {}

    def test_security_home_none_or_malformed(self):
        """Test handling None or malformed functionalHomes dict."""
        from custom_components.hcu_integration.util import get_security_home

        assert get_security_home({}) == {}
        assert get_security_home({"functionalHomes": None}) == {}
        assert get_security_home({"functionalHomes": {"INVALID": "not a dict"}}) == {}


class TestGetGroupType:
    def test_get_group_type(self):
        """Test extracting group type from group data."""
        from custom_components.hcu_integration.util import get_group_type

        assert get_group_type({"type": "HEATING"}) == "HEATING"
        assert get_group_type({}) is None


class TestHandleLockApiError:
    def test_invalid_pin_without_pin(self, caplog):
        """Test invalid pin error without configured pin logs warning and returns invalid_pin."""
        import logging

        from custom_components.hcu_integration.util import handle_lock_api_error

        with caplog.at_level(logging.WARNING):
            res = handle_lock_api_error(
                Exception("Error: INVALID_PIN provided"), "Front Door", None
            )
        assert res == "invalid_pin"
        assert any(
            "Lock 'Front Door' requires a PIN to function" in r.message
            for r in caplog.records
            if r.levelname == "WARNING"
        )

    def test_invalid_pin_with_pin(self, caplog):
        """Test invalid pin error with pin does not log warning and returns invalid_pin."""
        import logging

        from custom_components.hcu_integration.util import handle_lock_api_error

        with caplog.at_level(logging.WARNING):
            res = handle_lock_api_error(
                Exception("Wrong pin entered: invalid_pin"), "Front Door", "1234"
            )
        assert res == "invalid_pin"
        assert not any(
            "Lock 'Front Door' requires a PIN to function" in r.message
            for r in caplog.records
            if r.levelname == "WARNING"
        )

    def test_access_denied_error(self, caplog):
        """Test access denied error logs error and returns access_denied."""
        import logging

        from custom_components.hcu_integration.util import handle_lock_api_error

        with caplog.at_level(logging.ERROR):
            res = handle_lock_api_error(
                Exception("CLIENT_ACCESS_DENIED"), "Front Door", "1234"
            )
        assert res == "access_denied"
        assert any(
            "Front Door" in r.message for r in caplog.records if r.levelname == "ERROR"
        )

    def test_no_permission_error(self, caplog):
        """Test no permission error logs error and returns access_denied."""
        import logging

        from custom_components.hcu_integration.util import handle_lock_api_error

        with caplog.at_level(logging.ERROR):
            res = handle_lock_api_error(
                Exception("User has no permission to perform action"),
                "Back Door",
                "1234",
            )
        assert res == "access_denied"
        assert any(
            "Back Door" in r.message for r in caplog.records if r.levelname == "ERROR"
        )

    def test_jammed_error(self, caplog):
        """Test jam error logs error and returns jammed."""
        import logging

        from custom_components.hcu_integration.util import handle_lock_api_error

        with caplog.at_level(logging.ERROR):
            res = handle_lock_api_error(
                Exception("Motor is jammed"), "Garage Lock", None
            )
        assert res == "jammed"
        assert any(
            "Lock 'Garage Lock' is jammed" in r.message
            for r in caplog.records
            if r.levelname == "ERROR"
        )

    def test_unhandled_error(self):
        """Test unhandled error returns None without error log."""
        from custom_components.hcu_integration.util import handle_lock_api_error

        res = handle_lock_api_error(
            ValueError("Something completely different"), "Front Door", "1234"
        )
        assert res is None


class TestCoordinatorHelpers:
    def test_get_entry_coordinator(self):
        """Test getting coordinator from entry in various states."""
        from unittest.mock import MagicMock

        from homeassistant.config_entries import ConfigEntryState

        from custom_components.hcu_integration.util import get_entry_coordinator

        assert get_entry_coordinator(None) is None

        mock_entry = MagicMock()
        mock_entry.state = ConfigEntryState.NOT_LOADED
        mock_entry.runtime_data = "coordinator"
        assert get_entry_coordinator(mock_entry) is None

        mock_entry.state = ConfigEntryState.LOADED
        assert get_entry_coordinator(mock_entry) == "coordinator"

        mock_entry.state = ConfigEntryState.SETUP_IN_PROGRESS
        assert get_entry_coordinator(mock_entry) == "coordinator"

    def test_iter_coordinators(self):
        """Test iterating over coordinators of loaded entries."""
        from unittest.mock import MagicMock

        from homeassistant.config_entries import ConfigEntryState

        from custom_components.hcu_integration.const import DOMAIN
        from custom_components.hcu_integration.util import iter_coordinators

        hass = MagicMock()
        entry1 = MagicMock()
        entry1.state = ConfigEntryState.LOADED
        entry1.runtime_data = "coord1"

        entry2 = MagicMock()
        entry2.state = ConfigEntryState.NOT_LOADED
        entry2.runtime_data = None

        entry3 = MagicMock()
        entry3.state = ConfigEntryState.SETUP_IN_PROGRESS
        entry3.runtime_data = "coord3"

        hass.config_entries.async_entries.return_value = [entry1, entry2, entry3]

        coordinators = list(iter_coordinators(hass))
        hass.config_entries.async_entries.assert_called_once_with(DOMAIN)
        assert coordinators == ["coord1", "coord3"]


class TestCreateUnverifiedSslContext:
    async def test_create_unverified_ssl_context(self, hass):
        """Test SSL context creation and caching."""
        import ssl

        from custom_components.hcu_integration.util import (
            _SSL_CONTEXT_CACHE_KEY,
            create_unverified_ssl_context,
        )

        assert _SSL_CONTEXT_CACHE_KEY not in hass.data
        context1 = await create_unverified_ssl_context(hass)
        assert isinstance(context1, ssl.SSLContext)
        assert context1.check_hostname is False
        assert context1.verify_mode == ssl.CERT_NONE
        assert _SSL_CONTEXT_CACHE_KEY in hass.data

        # Second call returns cached instance
        context2 = await create_unverified_ssl_context(hass)
        assert context2 is context1


class TestErrorTranslationHelpers:
    def test_lock_error_to_exception_access_denied_and_jammed(self):
        """Test lock_error_to_exception translates access_denied and jammed."""
        from custom_components.hcu_integration.const import DOMAIN
        from custom_components.hcu_integration.util import lock_error_to_exception

        exc_denied = lock_error_to_exception(
            "access_denied", "Front Door", Exception("denied")
        )
        assert exc_denied.translation_domain == DOMAIN
        assert exc_denied.translation_key == "lock_access_denied"
        assert exc_denied.translation_placeholders == {"entity": "Front Door"}

        exc_jammed = lock_error_to_exception(
            "jammed", "Front Door", Exception("jammed")
        )
        assert exc_jammed.translation_domain == DOMAIN
        assert exc_jammed.translation_key == "lock_jammed"
        assert exc_jammed.translation_placeholders == {"entity": "Front Door"}


class TestUtilHelperCoverage:
    def test_format_hcu_end_time(self):
        """Test format_hcu_end_time parses various formats and raises error on invalid."""
        from homeassistant.exceptions import ServiceValidationError
        import pytest

        from custom_components.hcu_integration.util import format_hcu_end_time

        # Valid ISO format
        assert format_hcu_end_time("2026-12-31 18:00") == "2026_12_31 18:00"
        # Valid HCU format
        assert format_hcu_end_time("2026_12_31 18:00") == "2026_12_31 18:00"

        # Invalid format
        with pytest.raises(ServiceValidationError):
            format_hcu_end_time("invalid-datetime")

    def test_command_failed_and_lock_error_fallback(self):
        """command_failed carries the entity id and error; unknown lock errors fall back to it."""
        from custom_components.hcu_integration.util import (
            command_failed,
            lock_error_to_exception,
        )

        err = command_failed("switch.1", Exception("boom"))
        assert err.translation_key == "command_failed"
        assert err.translation_placeholders == {"entity": "switch.1", "error": "boom"}

        inv_err = lock_error_to_exception("invalid_pin", "lock.1", Exception("bad pin"))
        assert inv_err.translation_key == "lock_invalid_pin"
        assert inv_err.translation_placeholders == {"entity": "lock.1"}

        def_err = lock_error_to_exception(None, "lock.1", Exception("fallback"))
        assert def_err.translation_key == "command_failed"
        assert def_err.translation_placeholders == {
            "entity": "lock.1",
            "error": "fallback",
        }
