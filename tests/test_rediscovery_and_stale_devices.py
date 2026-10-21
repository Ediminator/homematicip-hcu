"""Tests for host updates on rediscovery and manual removal of stale devices."""

from __future__ import annotations

import ipaddress
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration import (
    async_reload_entry,
    async_remove_config_entry_device,
)
from custom_components.hcu_integration.const import (
    CONF_ZEROCONF_NAME,
    CONF_ZEROCONF_TYPE,
    DOMAIN,
)

pytestmark = pytest.mark.usefixtures("mock_async_zeroconf")

ZC_NAME = "hcu1-0815._ssh._tcp.local."
ZC_TYPE = "_ssh._tcp.local."


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Keep entries from setting up for real when a flow touches them."""
    with patch(
        "custom_components.hcu_integration.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        yield


def _discovery(ip: str, name: str = ZC_NAME) -> ZeroconfServiceInfo:
    return ZeroconfServiceInfo(
        ip_address=ipaddress.ip_address(ip),
        ip_addresses=[ipaddress.ip_address(ip)],
        port=22,
        hostname="hcu1-0815.local.",
        type=ZC_TYPE,
        name=name,
        properties={},
    )


async def _discover(hass: HomeAssistant, ip: str, name: str = ZC_NAME):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "zeroconf"}, data=_discovery(ip, name)
    )


# --- discovery-update-info ---


async def test_known_hcu_at_new_address_asks_before_switching(
    hass: HomeAssistant,
) -> None:
    """A known HCU at a new address is only used after the user confirms it.

    The saved token is sent to the new address on the next connection, and
    the zeroconf name alone does not prove that the HCU answers there.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="3014F711A0000000000000AA",
        title="My HCU",
        data={
            CONF_HOST: "192.0.2.10",
            CONF_ZEROCONF_NAME: ZC_NAME,
            CONF_ZEROCONF_TYPE: ZC_TYPE,
        },
    )
    entry.add_to_hass(hass)

    result = await _discover(hass, "192.0.2.77")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm_new_address"
    assert result["description_placeholders"] == {
        "title": "My HCU",
        "old_host": "192.0.2.10",
        "host": "192.0.2.77",
    }
    assert entry.data[CONF_HOST] == "192.0.2.10"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "address_updated"
    assert entry.data[CONF_HOST] == "192.0.2.77"


async def test_confirmed_new_address_reloads_entry_waiting_for_retry(
    hass: HomeAssistant,
) -> None:
    """An entry that cannot connect to the old address is retried at once."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="3014F711A0000000000000AA",
        data={CONF_HOST: "192.0.2.10", CONF_ZEROCONF_NAME: ZC_NAME},
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.SETUP_RETRY)

    result = await _discover(hass, "192.0.2.77")
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await hass.config_entries.flow.async_configure(result["flow_id"], {})

    reload.assert_called_once_with(entry.entry_id)
    assert entry.data[CONF_HOST] == "192.0.2.77"


async def test_confirmed_new_address_of_loaded_entry_leaves_reload_to_listener(
    hass: HomeAssistant,
) -> None:
    """A loaded entry reloads through its update listener, not a second time here."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="3014F711A0000000000000AA",
        data={CONF_HOST: "192.0.2.10", CONF_ZEROCONF_NAME: ZC_NAME},
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)

    result = await _discover(hass, "192.0.2.77")
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await hass.config_entries.flow.async_configure(result["flow_id"], {})

    reload.assert_not_called()
    assert entry.data[CONF_HOST] == "192.0.2.77"


async def test_new_address_prompt_aborts_if_entry_was_removed(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="3014F711A0000000000000AA",
        data={CONF_HOST: "192.0.2.10", CONF_ZEROCONF_NAME: ZC_NAME},
    )
    entry.add_to_hass(hass)
    result = await _discover(hass, "192.0.2.77")

    await hass.config_entries.async_remove(entry.entry_id)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_new_address_prompt_is_not_repeated_while_open(
    hass: HomeAssistant,
) -> None:
    """Repeated announcements do not stack up identical prompts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="3014F711A0000000000000AA",
        data={CONF_HOST: "192.0.2.10", CONF_ZEROCONF_NAME: ZC_NAME},
    )
    entry.add_to_hass(hass)

    first = await _discover(hass, "192.0.2.77")
    second = await _discover(hass, "192.0.2.77")

    assert first["type"] is FlowResultType.FORM
    assert second["type"] is FlowResultType.ABORT
    assert second["reason"] == "already_in_progress"


async def test_other_hcu_at_old_address_does_not_take_over_entry(
    hass: HomeAssistant,
) -> None:
    """Another HCU that got an entry's old address must not overwrite its saved name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="3014F711A0000000000000AA",
        data={CONF_HOST: "192.0.2.10", CONF_ZEROCONF_NAME: ZC_NAME},
    )
    entry.add_to_hass(hass)

    result = await _discover(hass, "192.0.2.10", name="hcu1-4711._ssh._tcp.local.")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert entry.data[CONF_ZEROCONF_NAME] == ZC_NAME
    assert entry.data[CONF_HOST] == "192.0.2.10"


async def test_rediscovery_at_same_host_learns_zeroconf_name(
    hass: HomeAssistant,
) -> None:
    """A manually added entry learns the HCU's zeroconf name for later address changes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="3014F711A0000000000000AA",
        data={CONF_HOST: "192.0.2.10"},
    )
    entry.add_to_hass(hass)

    result = await _discover(hass, "192.0.2.10")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_ZEROCONF_NAME] == ZC_NAME
    assert entry.data[CONF_ZEROCONF_TYPE] == ZC_TYPE
    assert entry.data[CONF_HOST] == "192.0.2.10"


async def test_rediscovery_without_changes_does_not_touch_entry(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="3014F711A0000000000000AA",
        data={
            CONF_HOST: "192.0.2.10",
            CONF_ZEROCONF_NAME: ZC_NAME,
            CONF_ZEROCONF_TYPE: ZC_TYPE,
        },
    )
    entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_update_entry") as update:
        result = await _discover(hass, "192.0.2.10")

    assert result["reason"] == "already_configured"
    update.assert_not_called()


async def test_discovery_of_another_hcu_starts_a_new_flow(
    hass: HomeAssistant,
) -> None:
    """A different HCU (other name, other address) is offered for setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="3014F711A0000000000000AA",
        data={CONF_HOST: "192.0.2.10", CONF_ZEROCONF_NAME: ZC_NAME},
    )
    entry.add_to_hass(hass)

    result = await _discover(hass, "192.0.2.99", name="hcu1-4711._ssh._tcp.local.")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert entry.data[CONF_HOST] == "192.0.2.10"


async def test_zeroconf_metadata_change_does_not_reload(hass: HomeAssistant) -> None:
    """Learning the zeroconf name must not reload the running integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        data={CONF_HOST: "192.0.2.10", CONF_ZEROCONF_NAME: ZC_NAME},
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    coordinator = MagicMock()
    coordinator._previous_data = {CONF_HOST: "192.0.2.10"}
    coordinator._previous_options = {}
    entry.runtime_data = coordinator

    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as reload:
        await async_reload_entry(hass, entry)
    reload.assert_not_called()

    # A host change still reloads.
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_HOST: "192.0.2.77"}
    )
    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as reload:
        await async_reload_entry(hass, entry)
    reload.assert_awaited_once_with(entry.entry_id)


# --- stale-devices ---


def _loaded_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.10"})
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    coordinator = MagicMock()
    coordinator.client.state = {
        "devices": {"hcu-id": {"id": "hcu-id"}, "dev-1": {"id": "dev-1"}},
        "groups": {"grp-1": {"id": "grp-1"}},
        "home": {"id": "home-1"},
    }
    entry.runtime_data = coordinator
    return entry


def _device(hass: HomeAssistant, entry: MockConfigEntry, ident: str):
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, ident)}
    )


async def test_device_gone_from_hcu_can_be_removed(hass: HomeAssistant) -> None:
    entry = _loaded_entry(hass)
    device = _device(hass, entry, "dev-removed")

    assert await async_remove_config_entry_device(hass, entry, device) is True


@pytest.mark.parametrize("ident", ["dev-1", "grp-1", "hcu-id"])
async def test_device_still_on_hcu_cannot_be_removed(
    hass: HomeAssistant, ident: str
) -> None:
    """Devices, groups and the HCU itself come back on the next start, so keep them."""
    entry = _loaded_entry(hass)
    device = _device(hass, entry, ident)

    assert await async_remove_config_entry_device(hass, entry, device) is False


async def test_device_of_other_integration_identifier_is_ignored(
    hass: HomeAssistant,
) -> None:
    """Only identifiers of this integration decide; foreign ones do not block removal."""
    entry = _loaded_entry(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "dev-removed"), ("other_domain", "dev-1")},
    )

    assert await async_remove_config_entry_device(hass, entry, device) is True


async def test_device_can_be_removed_while_entry_is_not_loaded(
    hass: HomeAssistant,
) -> None:
    """Without a connection the integration cannot check; it lets the user decide."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.10"})
    entry.add_to_hass(hass)
    device = _device(hass, entry, "dev-1")

    assert await async_remove_config_entry_device(hass, entry, device) is True
