# custom_components/hcu_integration/config_flow.py
"""Config flow for the Homematic IP Local (HCU) integration."""
import hashlib
import ipaddress
import logging
import aiohttp
import asyncio
import uuid
import voluptuous as vol
from pprint import pformat
import json
from urllib.parse import quote, unquote
from typing import Any, TYPE_CHECKING
from datetime import datetime, timedelta

from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, ATTR_TEMPERATURE
from homeassistant.core import callback, HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, device_registry as dr
from homeassistant.helpers import selector, translation
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import dt as dt_util

from .api import HcuApiClient, HcuApiError
from .const import (
    DOMAIN,
    PLUGIN_ID,
    PLUGIN_FRIENDLY_NAME,
    MANUFACTURER_EQ3,
    MANUFACTURER_HUE,
    HUE_MODEL_TOKEN,
    CONF_COMFORT_TEMPERATURE,
    DEFAULT_COMFORT_TEMPERATURE,
    CONF_AUTH_TYPE,
    AUTH_TYPE_PLUGIN,
    AUTH_TYPE_APP,
    AUTH_TYPE_DUAL,
    HCU_REST_PORT,
    HCU_PLUGIN_WS_PORT,
    CONF_APP_TOKEN,
    CONF_APP_CLIENT_ID,
    CONF_PLUGIN_TOKEN,
    CONF_PLUGIN_CLIENT_ID,
    CONF_HCU_SGTIN,
    CONF_ZEROCONF_NAME,
    CONF_ZEROCONF_TYPE,
    CONF_ENTITY_PREFIX,
    CONF_PLATFORM_OVERRIDES,
    CONF_ADVANCED_DEBUGGING,
    CONF_ADVANCED_ATTRIBUTES,
    CONF_DISABLE_UNCONFIGURED_CHANNELS,
    DEFAULT_ADVANCED_DEBUGGING,
    DEFAULT_ADVANCED_ATTRIBUTES,
    DEFAULT_DISABLE_UNCONFIGURED_CHANNELS,
    CONF_DISABLED_GROUPS,
    CONF_DISABLED_OEMS,
    CONF_AUTO_RELOAD_ON_DEVICE_CHANGE,
    DEFAULT_AUTO_RELOAD_ON_DEVICE_CHANGE,
    ATTR_END_TIME,
    SUPPORTED_GROUP_TYPES,
    CONF_DEV,
    DEFAULT_DEV,
    CONF_HA_DEVICES,
    HA_FEATURE_DOMAINS,
    HA_DEVICE_TYPE_FEATURES,
    HA_MAINTENANCE_FEATURE_KEYS,
    determine_ha_device_type,
)
from .util import create_unverified_ssl_context, get_device_manufacturer, get_group_type

if TYPE_CHECKING:
    from . import HcuCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_will_remove_config_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Handle removal of a config entry."""
    _LOGGER.warning(
        "The HCU integration has been removed. For security, please manually delete the "
        "'Home Assistant Integration' client from your Homematic IP smartphone app "
        "or HCUweb to revoke the old API token."
    )


def get_third_party_oems(client: "HcuApiClient | None") -> set[str]:
    """Discover third-party OEMs from the HCU state."""
    third_party_oems = set()
    if client and client.state:
        for device in client.state.get("devices", {}).values():
            manufacturer = get_device_manufacturer(device)
            if manufacturer != MANUFACTURER_EQ3:
                third_party_oems.add(manufacturer)
    return third_party_oems

def get_groups(client: "HcuApiClient | None") -> set[str]:
    """Return group types that exist in HCU state and are mapped to HA entities."""
    group_types: set[str] = set()

    if client and client.state:
        for group in client.state.get("groups", {}).values():
            group_type = get_group_type(group)
            if group_type and group_type in SUPPORTED_GROUP_TYPES:
                group_types.add(group_type)

    return group_types
    
class HcuConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Homematic IP HCU Integration."""

    VERSION = 6
    reauth_entry: ConfigEntry | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._config_data: dict[str, Any] = {}
        self._app_client_id: str = ""
        self._app_client_auth: str = ""
        self._app_access_point_id: str = ""
        self._app_new_token: str = ""
        self._app_new_client_id: str = ""
        self._is_dual_setup: bool = False
        self._plugin_new_token: str = ""
        self._plugin_new_client_id: str = ""
        self._keep_app_token: bool = False
        self._keep_plugin_token: bool = False
        self._refresh_app_token: bool = False
        self._refresh_plugin_token: bool = False
        self._keep_tokens: bool = False
        self._confirm_task: asyncio.Task | None = None


    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> "HcuOptionsFlowHandler":
        """Get the options flow for this handler."""
        return HcuOptionsFlowHandler()

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery of a Homematic IP HCU."""
        host = None
        for addr in discovery_info.addresses:
            try:
                ip_addr = ipaddress.ip_address(addr)
                if ip_addr.version == 4:
                    host = str(ip_addr)
                    break
            except ValueError:
                continue

        if not host:
            return self.async_abort(reason="no_ipv4_address")

        # Setting a unique_id lets Home Assistant deduplicate concurrent
        # discovery flows for the same device and enables the "Ignore" option,
        # which is otherwise unavailable for discovery flows without one.
        await self.async_set_unique_id(discovery_info.hostname)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self._async_abort_entries_match({CONF_HOST: host})

        self._config_data = {
            CONF_HOST: host,
            # Recorded so the integration can later re-query zeroconf for all
            # of the HCU's currently known addresses (e.g. when it's reachable
            # over both WLAN and Ethernet) and register a MAC for each.
            CONF_ZEROCONF_NAME: discovery_info.name,
            CONF_ZEROCONF_TYPE: discovery_info.type,
        }

        self.context["title_placeholders"] = {"host": host}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm setup of a discovered HCU."""
        if user_input is not None:
            return await self.async_step_auth_type_selection()

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"host": self._config_data[CONF_HOST]},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial setup step where the user provides the host and ports."""
        if user_input is not None:
            host = user_input[CONF_HOST]
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

            self._config_data = user_input

            return await self.async_step_auth_type_selection()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("host", default=self.context.get("host", "")): str,
                }
            ),
        )

    async def async_step_auth_type_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose which connections to set up: App User, Plugin User, or both."""
        errors: dict[str, str] = {}

        if user_input is not None:
            use_app = user_input.get("use_app_user", False)
            use_plugin = user_input.get("use_plugin_user", False)
            if not use_app and not use_plugin:
                errors["base"] = "select_at_least_one"
            else:
                self._is_dual_setup = use_app and use_plugin
                if use_app:
                    return await self.async_step_app_auth_init()
                return await self.async_step_auth()

        return self.async_show_form(
            step_id="auth_type_selection",
            data_schema=vol.Schema({
                vol.Required("use_app_user", default=True): BooleanSelector(),
                vol.Required("use_plugin_user", default=True): BooleanSelector(),
            }),
            errors=errors,
        )

    async def async_step_app_auth_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """App User setup: send connectionRequest, then prompt button press."""
        errors: dict[str, str] = {}
        debug_info = ""
        host = self._config_data[CONF_HOST]
        auth_port = HCU_REST_PORT

        entry_id = self.context.get("entry_id")
        entry = self.hass.config_entries.async_get_entry(entry_id) if entry_id else None
        coordinator = self.hass.data.get(DOMAIN, {}).get(entry.entry_id) if entry else None
        api_client = coordinator.client if coordinator else None
        sgtin_from_client = (
            (api_client.hcu_device_id or api_client.state.get("home", {}).get("accessPointId", "")) or ""
            if api_client else ""
        )
        sgtin_default = sgtin_from_client or (entry.data.get(CONF_HCU_SGTIN, "") if entry else "")

        if user_input is not None:
            self._app_client_id = str(uuid.uuid4())
            self._app_access_point_id = user_input.get("sgtin", "").strip() or sgtin_default
            self._app_client_auth = hashlib.sha512(
                (self._app_access_point_id + "jiLpVitHvWnIGD1yo7MA").encode("utf-8")
            ).hexdigest().upper()

            session = aiohttp_client.async_get_clientsession(self.hass)
            ssl_context = await create_unverified_ssl_context(self.hass)
            url = f"https://{host}:{auth_port}/hmip/auth/connectionRequest"
            try:
                await self._async_connection_request(
                    session, host, auth_port, self._app_client_id,
                    self._app_client_auth, self._app_access_point_id, ssl_context,
                )
                return await self.async_step_app_auth_confirm()
            except aiohttp.ClientResponseError as exc:
                errors["base"] = "cannot_connect"
                debug_info = f"HTTP {exc.status} at {url}: {exc.message}"
                _LOGGER.error("connectionRequest HTTP error: %s", debug_info)
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                errors["base"] = "cannot_connect"
                debug_info = f"{type(exc).__name__}: {exc}"
            except Exception as exc:
                _LOGGER.exception("Unexpected error during connectionRequest")
                errors["base"] = "unknown"
                debug_info = f"{type(exc).__name__}: {exc}"

        return self.async_show_form(
            step_id="app_auth_init",
            data_schema=vol.Schema({
                vol.Optional("sgtin", default=sgtin_default): str,
            }),
            description_placeholders={"hcu_ip": host, "debug_info": debug_info},
            errors=errors,
        )

    async def async_step_app_auth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """App User setup: wait for system button press via background polling."""
        host = self._config_data[CONF_HOST]

        if self._confirm_task is None:
            session = aiohttp_client.async_get_clientsession(self.hass)
            ssl_context = await create_unverified_ssl_context(self.hass)
            self._confirm_task = self.hass.async_create_task(
                self._wait_for_button(
                    session, host, HCU_REST_PORT,
                    self._app_client_id, self._app_client_auth,
                    self._app_access_point_id, ssl_context,
                )
            )

        if not self._confirm_task.done():
            return self.async_show_progress(
                step_id="app_auth_confirm",
                progress_action="wait_for_button",
                progress_task=self._confirm_task,
            )

        try:
            self._confirm_task.result()
        except Exception as exc:
            _LOGGER.error("System button confirmation failed: %s", exc)
            self._confirm_task = None
            return self.async_show_progress_done(next_step_id="button_timeout")

        self._confirm_task = None
        self._config_data[CONF_APP_TOKEN] = self._app_new_token
        self._config_data[CONF_HCU_SGTIN] = self._app_access_point_id
        self._config_data[CONF_APP_CLIENT_ID] = self._app_new_client_id

        if self._is_dual_setup:
            return self.async_show_progress_done(next_step_id="auth")

        self._config_data.pop(CONF_PLUGIN_TOKEN, None)
        self._config_data.pop(CONF_PLUGIN_CLIENT_ID, None)
        self._config_data[CONF_AUTH_TYPE] = AUTH_TYPE_APP
        return self.async_show_progress_done(next_step_id="select_oems")

    async def async_step_button_timeout(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Abort the flow when the system button was not pressed in time."""
        return self.async_abort(reason="button_timeout")

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the authentication step where the user provides an activation key."""
        errors = {}
        debug_info = ""
        host = self._config_data.get("host", "HOST_NOT_FOUND")

        if user_input is not None:
            activation_key = user_input["activation_key"]
            session = aiohttp_client.async_get_clientsession(self.hass)
            ssl_context = await create_unverified_ssl_context(self.hass)

            try:
                auth_token = await self._async_get_auth_token(
                    session, host, HCU_REST_PORT, activation_key, ssl_context
                )
                client_id = await self._async_confirm_auth_token(
                    session, host, HCU_REST_PORT, activation_key, auth_token, ssl_context
                )

                _LOGGER.info(
                    "Successfully received and confirmed auth token from HCU at %s",
                    host,
                )

                self._config_data[CONF_PLUGIN_TOKEN] = auth_token
                self._config_data[CONF_PLUGIN_CLIENT_ID] = client_id
                self._config_data[CONF_AUTH_TYPE] = AUTH_TYPE_DUAL if self._is_dual_setup else AUTH_TYPE_PLUGIN
                return await self.async_step_select_oems()

            except aiohttp.ClientResponseError as err:
                debug_info = f"\n\n`HTTP {err.status}: {err.message}`"
                errors["base"] = "cannot_connect"
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                debug_info = f"\n\n`{type(err).__name__}: {err}`"
                errors["base"] = "cannot_connect"
            except ValueError as err:
                _LOGGER.error("Invalid response from HCU: %s", err)
                debug_info = f"\n\n`{err}`"
                errors["base"] = "invalid_key"
            except Exception as err:
                _LOGGER.exception("An unexpected error occurred during handshake")
                debug_info = f"\n\n`{type(err).__name__}: {err}`"
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema({vol.Required("activation_key"): str}),
            description_placeholders={"hcu_ip": host, "debug_info": debug_info},
            errors=errors,
        )
    
    async def async_step_select_oems(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step to select third-party OEMs to import capabilities from."""
        host = self._config_data[CONF_HOST]
        token = self._config_data.get(CONF_PLUGIN_TOKEN, "")
        auth_type = self._config_data.get(CONF_AUTH_TYPE, "")
        app_token = self._config_data.get(CONF_APP_TOKEN, "")
        access_point_id = self._config_data.get(CONF_HCU_SGTIN, "")
        client_id_val = self._config_data.get(CONF_PLUGIN_CLIENT_ID, "")
        listener_task = None

        session = aiohttp_client.async_get_clientsession(self.hass)
        client = HcuApiClient(
            self.hass,
            host,
            token,
            session,
            client_id=client_id_val,
            auth_type=auth_type,
            access_point_id=access_point_id,
            app_token=app_token,
        )

        try:
            if auth_type in (AUTH_TYPE_APP, AUTH_TYPE_DUAL):
                # App/DualBridge: get_system_state uses REST — no WebSocket needed
                await client.get_system_state()
            else:
                # Plugin: get_system_state requires an active WebSocket connection
                await client.connect()
                listener_task = self.hass.async_create_task(client.listen())
                try:
                    await client.get_system_state()
                finally:
                    if client.is_connected:
                        await client.disconnect()
                    listener_task.cancel()
        except (HcuApiError, ConnectionError, asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.warning(
                "Failed to connect to HCU during OEM selection. Proceeding without selection."
            )
            return self.async_create_entry(
                title="Homematic IP Local (HCU)",
                data=self._config_data,
            )

        third_party_oems = get_third_party_oems(client)

        if client.hcu_device_id:
            await self.async_set_unique_id(client.hcu_device_id, raise_on_progress=False)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        if not third_party_oems:
            return self.async_create_entry(
                title="Homematic IP Local (HCU)",
                data=self._config_data,
            )

        if user_input is not None:
            disabled_oems = user_input.get("disabled_oems", [])

            return self.async_create_entry(
                title="Homematic IP Local (HCU)",
                data=self._config_data,
                options={"disabled_oems": disabled_oems},
            )

        third_party_oems_list = sorted(third_party_oems)

        schema = {
            vol.Optional(
                "disabled_oems",
                default=[],
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=third_party_oems_list,
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        }

        return self.async_show_form(
            step_id="select_oems",
            data_schema=vol.Schema(schema),
            description_placeholders={},
        )
    
    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a reauthentication flow — skip host step, go straight to auth."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        entry = self.reauth_entry
        self._config_data = dict(entry.data)
        self.context["title_placeholders"] = {"host": entry.data.get(CONF_HOST, "")}
        return await self.async_step_reconfigure_auth_type_selection()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration – step 1: host."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        errors = {}
        current_host = entry.data.get(CONF_HOST, "")
        self.context["title_placeholders"] = {"host": current_host}

        if user_input is not None:
            self._config_data = {
                **entry.data,
                CONF_HOST: user_input[CONF_HOST],
            }
            self.context["title_placeholders"] = {"host": user_input[CONF_HOST]}
            return await self.async_step_reconfigure_auth_type_selection()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=current_host): str,
                }
            ),
            description_placeholders={"hcu_ip": current_host},
            errors=errors,
        )
    
    
    async def async_step_reconfigure_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration – step 2: activation key and token renewal."""
        errors = {}
        debug_info = ""
        host = self._config_data[CONF_HOST]

        if user_input is not None:
            activation_key = user_input["activation_key"]
            session = aiohttp_client.async_get_clientsession(self.hass)
            ssl_context = await create_unverified_ssl_context(self.hass)

            try:
                new_token = await self._async_get_auth_token(
                    session, host, HCU_REST_PORT, activation_key, ssl_context
                )
                new_client_id = await self._async_confirm_auth_token(
                    session, host, HCU_REST_PORT, activation_key, new_token, ssl_context
                )

                entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
                updated_data = {
                    **entry.data,
                    CONF_HOST: self._config_data[CONF_HOST],
                    CONF_PLUGIN_TOKEN: new_token,
                    CONF_PLUGIN_CLIENT_ID: new_client_id,
                    CONF_AUTH_TYPE: AUTH_TYPE_DUAL if self._is_dual_setup else AUTH_TYPE_PLUGIN,
                }
                if self._is_dual_setup:
                    updated_data[CONF_APP_TOKEN] = self._config_data.get(CONF_APP_TOKEN, "")
                    updated_data[CONF_HCU_SGTIN] = self._config_data.get(CONF_HCU_SGTIN, "")
                    updated_data[CONF_APP_CLIENT_ID] = self._config_data.get(CONF_APP_CLIENT_ID, "")
                else:
                    updated_data.pop(CONF_APP_TOKEN, None)
                    updated_data.pop(CONF_APP_CLIENT_ID, None)
                    updated_data.pop(CONF_HCU_SGTIN, None)
                self._update_entry_and_reload_if_needed(entry, updated_data)
                return self.async_abort(reason="reconfigure_successful")

            except aiohttp.ClientResponseError as err:
                debug_info = f"\n\n`HTTP {err.status}: {err.message}`"
                errors["base"] = "cannot_connect"
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                debug_info = f"\n\n`{type(err).__name__}: {err}`"
                errors["base"] = "cannot_connect"
            except ValueError as err:
                debug_info = f"\n\n`{err}`"
                errors["base"] = "invalid_key"
            except Exception as err:
                _LOGGER.exception("Unexpected error during reconfiguration.")
                debug_info = f"\n\n`{type(err).__name__}: {err}`"
                errors["base"] = "unknown"
    
        return self.async_show_form(
            step_id="reconfigure_auth",
            data_schema=vol.Schema({vol.Required("activation_key"): str}),
            description_placeholders={"hcu_ip": host, "debug_info": debug_info},
            errors=errors,
        )

    async def async_step_reconfigure_auth_type_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Choose the new connection mode (auth type)."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        current_auth_type = entry.data.get(CONF_AUTH_TYPE, AUTH_TYPE_PLUGIN)
        if "title_placeholders" not in self.context:
            self.context["title_placeholders"] = {"host": self._config_data.get(CONF_HOST, entry.data.get(CONF_HOST, ""))}

        errors: dict[str, str] = {}

        if user_input is not None:
            new_auth_type = user_input.get("auth_type", current_auth_type)
            self._keep_tokens = user_input.get("keep_tokens", False)
            self._config_data[CONF_AUTH_TYPE] = new_auth_type
            self._is_dual_setup = new_auth_type == AUTH_TYPE_DUAL

            if not self._keep_tokens:
                # Tokens deleted — must re-auth all modes, skip token options
                self._config_data.pop(CONF_APP_TOKEN, None)
                self._config_data.pop(CONF_APP_CLIENT_ID, None)
                self._config_data.pop(CONF_HCU_SGTIN, None)
                self._config_data.pop(CONF_PLUGIN_TOKEN, None)
                self._config_data.pop(CONF_PLUGIN_CLIENT_ID, None)
                self._keep_app_token = False
                self._keep_plugin_token = False
                if new_auth_type in (AUTH_TYPE_APP, AUTH_TYPE_DUAL):
                    return await self.async_step_reconfigure_app_auth_init()
                return await self.async_step_reconfigure_auth()

            return await self.async_step_reconfigure_token_options()

        # Build connection status for description
        coordinator = self.hass.data.get(DOMAIN, {}).get(entry.entry_id) if entry else None
        client = coordinator.client if coordinator else None

        lang = self.hass.config.language
        translations_data = await translation.async_get_translations(
            self.hass, lang, "config", {DOMAIN}
        )
        prefix = f"component.{DOMAIN}.config.step.reconfigure_auth_type_selection.data."
        t_connected      = translations_data.get(f"{prefix}status_connected", "✓ Connected")
        t_not_connected  = translations_data.get(f"{prefix}status_not_connected", "✗ Not connected")
        t_not_configured = translations_data.get(f"{prefix}status_not_configured", "— Not configured")

        has_app    = current_auth_type in (AUTH_TYPE_APP, AUTH_TYPE_DUAL) and bool(entry.data.get(CONF_APP_TOKEN))
        has_plugin = current_auth_type in (AUTH_TYPE_PLUGIN, AUTH_TYPE_DUAL) and bool(entry.data.get(CONF_PLUGIN_TOKEN))

        if has_app:
            app_status = t_connected if (client and client.is_connected and client._app_token) else t_not_connected
        elif current_auth_type in (AUTH_TYPE_APP, AUTH_TYPE_DUAL):
            app_status = t_not_configured
        else:
            app_status = t_not_configured

        if has_plugin:
            plugin_status = t_connected if (
                client and (client.is_plugin_connected if current_auth_type == AUTH_TYPE_DUAL else client.is_connected)
            ) else t_not_connected
        else:
            plugin_status = t_not_configured

        return self.async_show_form(
            step_id="reconfigure_auth_type_selection",
            data_schema=vol.Schema({
                vol.Required("auth_type", default=current_auth_type): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": AUTH_TYPE_DUAL,   "label": "DualBridge (App + Plugin)"},
                            {"value": AUTH_TYPE_APP,    "label": "App User"},
                            {"value": AUTH_TYPE_PLUGIN, "label": "Plugin User"},
                        ],
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Required("keep_tokens", default=False): BooleanSelector(),
            }),
            description_placeholders={
                "app_status": app_status,
                "plugin_status": plugin_status,
            },
            errors=errors,
        )

    async def async_step_reconfigure_token_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Choose which tokens to refresh."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        current_auth_type = entry.data.get(CONF_AUTH_TYPE, AUTH_TYPE_PLUGIN)
        new_auth_type = self._config_data.get(CONF_AUTH_TYPE, current_auth_type)

        has_app    = current_auth_type in (AUTH_TYPE_APP, AUTH_TYPE_DUAL)
        has_plugin = current_auth_type in (AUTH_TYPE_PLUGIN, AUTH_TYPE_DUAL)
        needs_app    = new_auth_type in (AUTH_TYPE_APP, AUTH_TYPE_DUAL)
        needs_plugin = new_auth_type in (AUTH_TYPE_PLUGIN, AUTH_TYPE_DUAL)

        errors: dict[str, str] = {}

        if user_input is not None:
            refresh_app    = user_input.get("refresh_app_token", False)
            refresh_plugin = user_input.get("refresh_plugin_token", False)

            self._keep_app_token    = needs_app    and not refresh_app
            self._keep_plugin_token = needs_plugin and not refresh_plugin

            # Remove tokens for modes that are no longer active
            if not needs_app:
                self._config_data.pop(CONF_APP_TOKEN, None)
                self._config_data.pop(CONF_APP_CLIENT_ID, None)
                self._config_data.pop(CONF_HCU_SGTIN, None)
            if not needs_plugin:
                self._config_data.pop(CONF_PLUGIN_TOKEN, None)
                self._config_data.pop(CONF_PLUGIN_CLIENT_ID, None)

            if needs_app and refresh_app:
                return await self.async_step_reconfigure_app_auth_init()
            if needs_plugin and refresh_plugin:
                return await self.async_step_reconfigure_auth()

            # Nothing to re-auth — save immediately
            self._update_entry_and_reload_if_needed(entry, self._config_data)
            return self.async_abort(reason="reconfigure_successful")

        # Defaults based purely on selected auth_type
        default_refresh_app    = needs_app
        default_refresh_plugin = needs_plugin

        schema: dict = {}
        if needs_app:
            schema[vol.Required("refresh_app_token", default=default_refresh_app)] = BooleanSelector()
        if needs_plugin:
            schema[vol.Required("refresh_plugin_token", default=default_refresh_plugin)] = BooleanSelector()

        return self.async_show_form(
            step_id="reconfigure_token_options",
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    async def async_step_reconfigure_app_auth_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start App User auth: collect optional system PIN, then send connectionRequest."""
        errors = {}
        debug_info = ""
        host = self._config_data[CONF_HOST]
        auth_port = HCU_REST_PORT

        # Resolve sgtin for pre-fill: live coordinator → stored entry → empty
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        coordinator = self.hass.data.get(DOMAIN, {}).get(entry.entry_id) if entry else None
        api_client = coordinator.client if coordinator else None
        sgtin_from_client = (
            (api_client.hcu_device_id or api_client.state.get("home", {}).get("accessPointId", "")) or ""
            if api_client else ""
        )
        sgtin_default = sgtin_from_client or (entry.data.get(CONF_HCU_SGTIN, "") if entry else "")

        if user_input is not None:
            self._app_client_id = str(uuid.uuid4())
            self._app_access_point_id = user_input.get("sgtin", "").strip() or sgtin_default

            # Derive CLIENTAUTH from sgtin using the same algorithm as homematicip-rest-api
            self._app_client_auth = hashlib.sha512(
                (self._app_access_point_id + "jiLpVitHvWnIGD1yo7MA").encode("utf-8")
            ).hexdigest().upper()
            _LOGGER.debug(
                "App auth: sgtin='%s' client_auth_prefix=%s",
                self._app_access_point_id,
                self._app_client_auth[:8] if self._app_client_auth else "EMPTY",
            )

            session = aiohttp_client.async_get_clientsession(self.hass)
            ssl_context = await create_unverified_ssl_context(self.hass)
            url = f"https://{host}:{auth_port}/hmip/auth/connectionRequest"
            try:
                await self._async_connection_request(
                    session, host, auth_port, self._app_client_id,
                    self._app_client_auth, self._app_access_point_id, ssl_context,
                )
                return await self.async_step_reconfigure_app_auth_confirm()
            except aiohttp.ClientResponseError as exc:
                errors["base"] = "cannot_connect"
                debug_info = (
                    f"HTTP {exc.status} beim POST {url}\n"
                    f"sgtin: '{self._app_access_point_id}'\n"
                    f"Nachricht: {exc.message}"
                )
                _LOGGER.error("connectionRequest HTTP-Fehler: %s", debug_info)
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                errors["base"] = "cannot_connect"
                debug_info = f"Verbindungsfehler bei {url}: {type(exc).__name__}: {exc}"
                _LOGGER.error("connectionRequest Verbindungsfehler: %s", debug_info)
            except Exception as exc:
                _LOGGER.exception("Unexpected error during connectionRequest")
                errors["base"] = "unknown"
                debug_info = f"{type(exc).__name__}: {exc}"

        return self.async_show_form(
            step_id="reconfigure_app_auth_init",
            data_schema=vol.Schema({
                vol.Optional("sgtin", default=sgtin_default): str,
            }),
            description_placeholders={"hcu_ip": host, "debug_info": debug_info},
            errors=errors,
        )

    async def async_step_reconfigure_app_auth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reconfigure App User auth: wait for system button press via background polling."""
        host = self._config_data[CONF_HOST]

        if self._confirm_task is None:
            session = aiohttp_client.async_get_clientsession(self.hass)
            ssl_context = await create_unverified_ssl_context(self.hass)
            self._confirm_task = self.hass.async_create_task(
                self._wait_for_button(
                    session, host, HCU_REST_PORT,
                    self._app_client_id, self._app_client_auth,
                    self._app_access_point_id, ssl_context,
                )
            )

        if not self._confirm_task.done():
            return self.async_show_progress(
                step_id="reconfigure_app_auth_confirm",
                progress_action="wait_for_button",
                progress_task=self._confirm_task,
            )

        try:
            self._confirm_task.result()
        except Exception as exc:
            _LOGGER.error("System button confirmation failed during reconfigure: %s", exc)
            self._confirm_task = None
            return self.async_show_progress_done(next_step_id="reconfigure_button_timeout")

        self._confirm_task = None
        self._config_data[CONF_APP_TOKEN] = self._app_new_token
        self._config_data[CONF_HCU_SGTIN] = self._app_access_point_id
        self._config_data[CONF_APP_CLIENT_ID] = self._app_new_client_id

        if self._is_dual_setup and not self._keep_plugin_token:
            return self.async_show_progress_done(next_step_id="reconfigure_auth")

        return self.async_show_progress_done(next_step_id="reconfigure_app_auth_finalize")

    async def async_step_reconfigure_app_auth_finalize(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Save updated App User token and close the reconfigure flow."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        updated_data = {
            k: v for k, v in entry.data.items()
            if k not in (CONF_PLUGIN_TOKEN, CONF_PLUGIN_CLIENT_ID)
        }
        updated_data.update({
            CONF_HOST: self._config_data[CONF_HOST],
            CONF_APP_TOKEN: self._app_new_token,
            CONF_AUTH_TYPE: AUTH_TYPE_DUAL if self._is_dual_setup else AUTH_TYPE_APP,
            CONF_HCU_SGTIN: self._app_access_point_id,
            CONF_APP_CLIENT_ID: self._app_new_client_id,
        })
        if self._is_dual_setup and self._keep_plugin_token:
            updated_data[CONF_PLUGIN_TOKEN] = entry.data.get(CONF_PLUGIN_TOKEN, "")
            updated_data[CONF_PLUGIN_CLIENT_ID] = entry.data.get(CONF_PLUGIN_CLIENT_ID, "")
        self._update_entry_and_reload_if_needed(entry, updated_data)
        return self.async_abort(reason="reconfigure_successful")

    async def async_step_reconfigure_button_timeout(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Abort the reconfigure flow when the system button was not pressed in time."""
        return self.async_abort(reason="button_timeout")

    def _update_entry_and_reload_if_needed(self, entry: ConfigEntry, data: dict) -> None:
        """Update config entry and force reload when the entry is not currently loaded."""
        self.hass.config_entries.async_update_entry(entry, data=data)
        if entry.state is not ConfigEntryState.LOADED:
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(entry.entry_id)
            )

    def _get_device_name(self, with_timestamp: bool = False) -> str:
        """Build a device name based on dev mode: location_name in dev, else 'Home Assistant'."""
        entry = getattr(self, "config_entry", None) or getattr(self, "reauth_entry", None)
        if entry is None and (entry_id := self.context.get("entry_id")):
            entry = self.hass.config_entries.async_get_entry(entry_id)
        dev = entry.options.get(CONF_DEV, DEFAULT_DEV) if entry else DEFAULT_DEV
        name = (self.hass.config.location_name or "Home Assistant") if dev else "Home Assistant"
        if with_timestamp:
            timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
            return f"{name} - {timestamp}"
        return name

    async def _wait_for_button(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        client_id: str,
        client_auth: str,
        access_point_id: str,
        ssl_context,
        timeout: int = 60,
        interval: int = 2,
    ) -> None:
        """Poll isRequestAcknowledged, then fetch and store the App User token."""
        for _ in range(timeout // interval):
            if await self._async_is_request_acknowledged(
                session, host, port, client_id, client_auth, access_point_id, ssl_context
            ):
                new_token = await self._async_request_app_auth_token(
                    session, host, port, client_id, client_auth, access_point_id, ssl_context,
                )
                new_client_id = await self._async_confirm_app_auth_token(
                    session, host, port, client_id, client_auth, new_token, access_point_id, ssl_context,
                )
                self._app_new_token = new_token
                self._app_new_client_id = new_client_id
                return
            await asyncio.sleep(interval)
        raise asyncio.TimeoutError(
            f"System button on HCU at {host} was not pressed within {timeout} seconds."
        )

    async def _async_connection_request(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        client_id: str,
        client_auth: str,
        access_point_id: str,
        ssl_context,
        system_pin: str = "",
    ) -> None:
        """Send connectionRequest to start App User auth flow."""
        url = f"https://{host}:{port}/hmip/auth/connectionRequest"
        headers: dict[str, str] = {
            "VERSION": "12",
            "CLIENTAUTH": client_auth,
            "ACCESSPOINT-ID": access_point_id,
        }
        if system_pin:
            headers["PIN"] = system_pin
        body: dict[str, str] = {
            "deviceId": client_id,
            "deviceName": self._get_device_name(),
            "sgtin": access_point_id,
        }
        _LOGGER.debug("connectionRequest → %s | headers=%s | body=%s", url, list(headers), body)
        async with session.post(url, headers=headers, json=body, ssl=ssl_context) as response:
            if not response.ok:
                text = await response.text()
                _LOGGER.error("connectionRequest failed: HTTP %s – %s", response.status, text)
            response.raise_for_status()

    async def _async_is_request_acknowledged(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        client_id: str,
        client_auth: str,
        access_point_id: str,
        ssl_context,
    ) -> bool:
        """Check if the system button on the HCU has been pressed."""
        url = f"https://{host}:{port}/hmip/auth/isRequestAcknowledged"
        headers: dict[str, str] = {
            "VERSION": "12",
            "CLIENTAUTH": client_auth,
            "ACCESSPOINT-ID": access_point_id,
        }
        body: dict[str, str] = {"deviceId": client_id, "accessPointId": access_point_id}
        async with session.post(url, headers=headers, json=body, ssl=ssl_context) as response:
            _LOGGER.debug("isRequestAcknowledged: HTTP %s", response.status)
            return response.status == 200

    async def _async_request_app_auth_token(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        client_id: str,
        client_auth: str,
        access_point_id: str,
        ssl_context,
    ) -> str:
        """Request auth token in App User flow."""
        url = f"https://{host}:{port}/hmip/auth/requestAuthToken"
        headers: dict[str, str] = {
            "VERSION": "12",
            "CLIENTAUTH": client_auth,
            "ACCESSPOINT-ID": access_point_id,
        }
        body: dict[str, str] = {"deviceId": client_id}
        async with session.post(url, headers=headers, json=body, ssl=ssl_context) as response:
            if not response.ok:
                text = await response.text()
                _LOGGER.error("requestAuthToken failed: HTTP %s – %s", response.status, text)
            response.raise_for_status()
            data = await response.json()
            if not (token := data.get("authToken")):
                raise ValueError("No authToken in HCU response")
            return token

    async def _async_confirm_app_auth_token(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        client_id: str,
        client_auth: str,
        token: str,
        access_point_id: str,
        ssl_context,
    ) -> str:
        """Confirm auth token in App User flow."""
        url = f"https://{host}:{port}/hmip/auth/confirmAuthToken"
        headers: dict[str, str] = {
            "VERSION": "12",
            "CLIENTAUTH": client_auth,
            "ACCESSPOINT-ID": access_point_id,
        }
        body: dict[str, str] = {"deviceId": client_id, "authToken": token}
        async with session.post(url, headers=headers, json=body, ssl=ssl_context) as response:
            if not response.ok:
                text = await response.text()
                _LOGGER.error("confirmAuthToken failed: HTTP %s – %s", response.status, text)
            response.raise_for_status()
            data = await response.json()
            if not (cid := data.get("clientId")):
                raise ValueError("HCU did not confirm the authToken.")
            return cid

    async def _async_get_auth_token(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        key: str,
        ssl_context,
    ) -> str:
        """Request a new auth token from the HCU."""
        url = f"https://{host}:{port}/hmip/auth/requestConnectApiAuthToken"
        headers = {"VERSION": "12"}
        device_name = self._get_device_name(with_timestamp=True)
        body = {
            "activationKey": key,
            "pluginId": PLUGIN_ID,
            "friendlyName": {"de": device_name, "en": device_name},
        }

        _LOGGER.debug("requestConnectApiAuthToken → %s", url)
        async with session.post(
            url, headers=headers, json=body, ssl=ssl_context
        ) as response:
            _LOGGER.debug("requestConnectApiAuthToken ← HTTP %s", response.status)
            if not response.ok:
                text = await response.text()
                _LOGGER.error("requestConnectApiAuthToken failed: HTTP %s – %s", response.status, text[:300])
            response.raise_for_status()
            data = await response.json()
            if not (token := data.get("authToken")):
                raise ValueError("No authToken in HCU response")
            return token

    async def _async_confirm_auth_token(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        key: str,
        token: str,
        ssl_context,
    ) -> str:
        """Confirm the new auth token with the HCU."""
        url = f"https://{host}:{port}/hmip/auth/confirmConnectApiAuthToken"
        headers = {"VERSION": "12"}
        body = {"activationKey": key, "authToken": token}

        _LOGGER.debug("confirmConnectApiAuthToken → %s", url)
        async with session.post(
            url, headers=headers, json=body, ssl=ssl_context
        ) as response:
            _LOGGER.debug("confirmConnectApiAuthToken ← HTTP %s", response.status)
            if not response.ok:
                text = await response.text()
                _LOGGER.error("confirmConnectApiAuthToken failed: HTTP %s – %s", response.status, text[:300])
            response.raise_for_status()
            data = await response.json()
            if not (client_id := data.get("clientId")):
                raise ValueError("HCU did not confirm the authToken.")
            return client_id

class HcuOptionsFlowHandler(OptionsFlow):
    """Handle an options flow for the HCU integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options for the integration."""
        dev = self.config_entry.options.get(CONF_DEV, DEFAULT_DEV)
        menu_options = ["connection_status", "global_settings", "vacation", "ha_devices"]
        if dev:
            menu_options.insert(2, "developer_settings")
        return self.async_show_menu(step_id="init", menu_options=menu_options)

    async def async_step_connection_status(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show current connection status (read-only)."""
        if user_input is not None:
            return self.async_create_entry(title="", data=dict(self.config_entry.options))

        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        client = coordinator.client if coordinator else None
        auth_type = self.config_entry.data.get(CONF_AUTH_TYPE, AUTH_TYPE_PLUGIN)

        # Load labels from translations
        lang = self.hass.config.language
        translations_data = await translation.async_get_translations(
            self.hass, lang, "options", {DOMAIN}
        )
        prefix = f"component.{DOMAIN}.options.step.connection_status.data."
        t_connected     = translations_data.get(f"{prefix}status_connected", "✓ Connected")
        t_not_connected = translations_data.get(f"{prefix}status_not_connected", "✗ Not connected")
        t_not_configured= translations_data.get(f"{prefix}status_not_configured", "— not configured")
        t_mode_app      = translations_data.get(f"{prefix}mode_app", "App User")
        t_mode_plugin   = translations_data.get(f"{prefix}mode_plugin", "Plugin User")
        t_mode_dual     = translations_data.get(f"{prefix}mode_dual", "DualBridge (App + Plugin)")

        mode_labels = {
            AUTH_TYPE_APP: t_mode_app,
            AUTH_TYPE_PLUGIN: t_mode_plugin,
            AUTH_TYPE_DUAL: t_mode_dual,
        }
        auth_type_label = mode_labels.get(auth_type, auth_type)

        has_app_token    = bool(self.config_entry.data.get(CONF_APP_TOKEN))
        has_plugin_token = bool(self.config_entry.data.get(CONF_PLUGIN_TOKEN))

        if auth_type in (AUTH_TYPE_APP, AUTH_TYPE_DUAL) and has_app_token:
            app_status = t_connected if (client and client.is_connected and client._app_token) else t_not_connected
        elif auth_type in (AUTH_TYPE_APP, AUTH_TYPE_DUAL):
            app_status = t_not_configured
        else:
            app_status = t_not_configured

        if auth_type == AUTH_TYPE_DUAL and has_plugin_token:
            plugin_status = t_connected if (client and client.is_plugin_connected) else t_not_connected
        elif auth_type == AUTH_TYPE_PLUGIN and has_plugin_token:
            plugin_status = t_connected if (client and client.is_connected) else t_not_connected
        elif auth_type in (AUTH_TYPE_PLUGIN, AUTH_TYPE_DUAL):
            plugin_status = t_not_configured
        else:
            plugin_status = t_not_configured

        return self.async_show_form(
            step_id="connection_status",
            data_schema=vol.Schema({}),
            description_placeholders={
                "auth_type_label": auth_type_label,
                "app_status": app_status,
                "plugin_status": plugin_status,
            },
        )

    async def async_step_global_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the global settings (comfort temp and OEM toggles)."""
        coordinator: "HcuCoordinator" | None = self.hass.data.get(DOMAIN, {}).get(
            self.config_entry.entry_id
        )
        client: HcuApiClient | None = coordinator.client if coordinator else None
        
        third_party_oems = get_third_party_oems(client)
        third_party_oems_list = sorted(third_party_oems)
        groups = get_groups(client)
        groups_list = sorted(groups)

        if user_input is not None:
            disabled_oems = user_input.get(CONF_DISABLED_OEMS, [])
            disabled_groups = user_input.get(CONF_DISABLED_GROUPS, [])

            await self._handle_device_removal(disabled_oems)
            
            # Clean up old boolean keys if present to avoid clutter
            new_options = {**self.config_entry.options}
            # Remove old keys
            keys_to_remove = [k for k in new_options if k.startswith("import_")]
            for k in keys_to_remove:
                new_options.pop(k)

            # Update new values
            new_options[CONF_DISABLE_UNCONFIGURED_CHANNELS] = user_input[CONF_DISABLE_UNCONFIGURED_CHANNELS]
            new_options[CONF_AUTO_RELOAD_ON_DEVICE_CHANGE] = user_input[CONF_AUTO_RELOAD_ON_DEVICE_CHANGE]
            new_options[CONF_COMFORT_TEMPERATURE] = user_input[CONF_COMFORT_TEMPERATURE]
            new_options[CONF_DISABLED_OEMS] = disabled_oems
            new_options[CONF_DISABLED_GROUPS] = disabled_groups

            return self.async_create_entry(title="", data=new_options)

        # Determine currently enabled OEMs (for pre-selection)
        # Check for new list format first
        disabled_oems = set(self.config_entry.options.get(CONF_DISABLED_OEMS, []))
        selected_disabled_groups = set(self.config_entry.options.get(CONF_DISABLED_GROUPS, []))
        
        # Backward compatibility: Check old boolean keys if new list not found (or empty? no, empty is valid)
        # If "disabled_oems" key is missing entirely, check legacy keys.
        if CONF_DISABLED_OEMS not in self.config_entry.options:
             for oem in third_party_oems:
                option_key = f"import_{quote(oem)}"
                # Migration logic: Check for old keys
                # Format 1 (Round <9): lowercase with underscores
                old_key_v1 = f"import_{oem.lower().replace(' ', '_')}"
                # Format 2 (Round 9-12): original case with underscores (lossy)
                old_key_v2 = f"import_{oem.replace(' ', '_')}"

                is_enabled = self.config_entry.options.get(option_key, True)
                
                # Check for migration if the new key is missing
                if option_key not in self.config_entry.options:
                    if old_key_v2 in self.config_entry.options:
                        is_enabled = self.config_entry.options[old_key_v2]
                    elif old_key_v1 in self.config_entry.options:
                        is_enabled = self.config_entry.options[old_key_v1]
                
                if not is_enabled:
                    disabled_oems.add(oem)

        default_disabled_oems = [oem for oem in third_party_oems_list if oem in disabled_oems]
        default_disabled_groups = [g for g in groups_list if g in selected_disabled_groups]

        schema = {
            vol.Required(
                CONF_DISABLE_UNCONFIGURED_CHANNELS,
                default=self.config_entry.options.get(CONF_DISABLE_UNCONFIGURED_CHANNELS, DEFAULT_DISABLE_UNCONFIGURED_CHANNELS),
            ): BooleanSelector(),
            vol.Required(
                CONF_AUTO_RELOAD_ON_DEVICE_CHANGE,
                default=self.config_entry.options.get(CONF_AUTO_RELOAD_ON_DEVICE_CHANGE, DEFAULT_AUTO_RELOAD_ON_DEVICE_CHANGE),
            ): BooleanSelector(),
            vol.Optional(
                CONF_COMFORT_TEMPERATURE,
                default=self.config_entry.options.get(
                    CONF_COMFORT_TEMPERATURE, DEFAULT_COMFORT_TEMPERATURE
                ),
            ): vol.Coerce(float),
            **(
                {
                    vol.Optional(
                        CONF_DISABLED_OEMS,
                        default=default_disabled_oems,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=third_party_oems_list,
                            multiple=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
                if third_party_oems_list
                else {}
            ),
            vol.Optional(
                CONF_DISABLED_GROUPS,
                default=default_disabled_groups,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    multiple=True,
                    sort=False,
                    options=groups_list,
                )
            ),
        }

        return self.async_show_form(
            step_id="global_settings", data_schema=vol.Schema(schema)
        )

    async def async_step_vacation(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle activating vacation mode."""
        errors: dict[str, str] = {}

        coordinator: "HcuCoordinator" | None = self.hass.data.get(DOMAIN, {}).get(
            self.config_entry.entry_id
        )
        client: HcuApiClient | None = coordinator.client if coordinator else None

        if not client:
            _LOGGER.error("HCU client not available")
            return self.async_abort(reason="internal_error")

        if user_input is not None:
            try:
                end_time_str = user_input[ATTR_END_TIME]
                end_time_dt = datetime.fromisoformat(end_time_str)
                ha_tz = dt_util.get_time_zone(self.hass.config.time_zone)
                local_end_time = end_time_dt.astimezone(ha_tz)
                formatted_end_time = local_end_time.strftime("%Y_%m_%d %H:%M")
                temperature = user_input[ATTR_TEMPERATURE]

                await client.async_activate_vacation(
                    temperature=temperature, end_time=formatted_end_time
                )

                return self.async_create_entry(title="", data=dict(self.config_entry.options))

            except HcuApiError as err:
                _LOGGER.error("Failed to activate vacation mode: %s", err)
                errors["base"] = "api_error"
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except (ValueError, TypeError) as err:
                _LOGGER.error("Invalid date/time format or temperature: %s", err)
                errors["base"] = "invalid_data"
            except Exception:
                _LOGGER.exception("Unexpected error activating vacation mode")
                errors["base"] = "unknown"

        default_end_time = datetime.now() + timedelta(days=7)
        default_temp = self.config_entry.options.get(
            CONF_COMFORT_TEMPERATURE, DEFAULT_COMFORT_TEMPERATURE
        )

        return self.async_show_form(
            step_id="vacation",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        ATTR_TEMPERATURE,
                        default=default_temp,
                    ): vol.All(vol.Coerce(float), vol.Range(min=5.0, max=30.0)),
                    vol.Required(
                        ATTR_END_TIME,
                        default=default_end_time.strftime("%Y-%m-%d %H:%M"),
                    ): selector.DateTimeSelector(),
                }
            ),
            errors=errors,
        )

    # --- HA Entity Bridge (ha_devices) ---

    async def async_step_ha_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show HA device bridge management menu."""
        ha_devices = self.config_entry.options.get(CONF_HA_DEVICES, [])
        menu_options = ["ha_devices_add"]
        if ha_devices:
            menu_options += ["ha_devices_edit", "ha_devices_remove"]
        return self.async_show_menu(step_id="ha_devices", menu_options=menu_options)

    async def async_step_ha_devices_add(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new HA entity device mapping (two-phase: select type then configure)."""
        # Phase 1 result: user selected a device type
        if user_input is not None and "device_type" in user_input:
            self._adding_device_type: str | None = user_input["device_type"]
            user_input = None  # re-enter to show the configuration form

        device_type = getattr(self, "_adding_device_type", None)

        if not device_type:
            # Phase 1: ask which kind of device to add
            return self.async_show_form(
                step_id="ha_devices_add",
                data_schema=vol.Schema({
                    vol.Required("device_type"): SelectSelector(
                        SelectSelectorConfig(
                            options=await self._device_type_options(),
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }),
            )

        if user_input is not None:
            # Phase 2 result: save the new device
            ha_devices = list(self.config_entry.options.get(CONF_HA_DEVICES, []))
            ha_devices.append(self._extract_device_from_input(user_input, device_type=device_type))
            self._adding_device_type = None
            return self._save_ha_devices(ha_devices)

        # Phase 2: show configuration form limited to the chosen type's features
        spec = HA_DEVICE_TYPE_FEATURES[device_type]
        return self.async_show_form(
            step_id="ha_devices_add",
            data_schema=self._device_form_schema(
                required_keys=spec["required"], optional_keys=spec["optional"]
            ),
        )

    async def _device_type_options(self) -> list[dict[str, str]]:
        """Build the translated {value, label} list for the device-type selector."""
        lang = self.hass.config.language
        translations_data = await translation.async_get_translations(
            self.hass, lang, "options", {DOMAIN}
        )
        prefix = f"component.{DOMAIN}.options.step.ha_devices_add.device_type_options."
        return [
            {"value": device_type, "label": translations_data.get(f"{prefix}{device_type}", device_type)}
            for device_type in HA_DEVICE_TYPE_FEATURES
        ]

    async def async_step_ha_devices_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit an existing HA entity device mapping (two-phase: select then edit)."""
        ha_devices = self.config_entry.options.get(CONF_HA_DEVICES, [])
        if not ha_devices:
            return await self.async_step_ha_devices()

        # Phase 1 result: user selected a device from the dropdown
        if user_input is not None and "device_id" in user_input:
            self._editing_device_id: str | None = user_input["device_id"]
            user_input = None  # re-enter to show edit form

        editing_id = getattr(self, "_editing_device_id", None)

        if not editing_id:
            # Phase 1: show device selection
            options = [{"value": d["id"], "label": d.get("name", d["id"])} for d in ha_devices]
            return self.async_show_form(
                step_id="ha_devices_edit",
                data_schema=vol.Schema({
                    vol.Required("device_id"): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                    )
                }),
            )

        device = next((d for d in ha_devices if d["id"] == editing_id), None)

        # Devices saved before the explicit "type" field existed fall back to
        # best-effort inference from their configured features.
        device_type = device.get("type") or determine_ha_device_type(device.get("features", {}))
        spec = HA_DEVICE_TYPE_FEATURES[device_type]

        if user_input is not None:
            # Phase 2 result: save updated device
            updated = self._extract_device_from_input(user_input, device_id=editing_id, device_type=device_type)
            new_devices = [updated if d["id"] == editing_id else d for d in ha_devices]
            self._editing_device_id = None
            return self._save_ha_devices(new_devices)

        # Phase 2: show edit form pre-populated with existing values, limited
        # to the features relevant for the device's type
        return self.async_show_form(
            step_id="ha_devices_edit",
            data_schema=self._device_form_schema(
                existing=device, required_keys=spec["required"], optional_keys=spec["optional"]
            ),
        )

    async def async_step_ha_devices_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Remove one or more HA entity device mappings."""
        ha_devices = self.config_entry.options.get(CONF_HA_DEVICES, [])
        if not ha_devices:
            return await self.async_step_ha_devices()

        if user_input is not None:
            remove_ids = set(user_input.get("device_ids", []))
            new_devices = [d for d in ha_devices if d["id"] not in remove_ids]
            return self._save_ha_devices(new_devices)

        options = [{"value": d["id"], "label": d.get("name", d["id"])} for d in ha_devices]
        return self.async_show_form(
            step_id="ha_devices_remove",
            data_schema=vol.Schema({
                vol.Required("device_ids"): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.LIST,
                        multiple=True,
                    )
                )
            }),
        )

    def _device_form_schema(
        self,
        existing: dict | None = None,
        required_keys: list[str] | None = None,
        optional_keys: list[str] | None = None,
    ) -> vol.Schema:
        """Build the voluptuous schema for the add/edit device form.

        `required_keys`/`optional_keys` limit the shown entity selectors to
        those relevant for the chosen/detected device type. Maintenance
        (low_bat, sabotage, unreach) is always offered as optional.
        """
        features = (existing or {}).get("features", {})
        schema_dict: dict = {
            vol.Required("name", default=(existing or {}).get("name", "")): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
        }
        for feature_key in required_keys or []:
            current = features.get(feature_key)
            req_key = vol.Required(feature_key, default=current) if current else vol.Required(feature_key)
            schema_dict[req_key] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain=HA_FEATURE_DOMAINS[feature_key])
            )
        for feature_key in list(optional_keys or []) + list(HA_MAINTENANCE_FEATURE_KEYS):
            current = features.get(feature_key)
            opt_key = vol.Optional(feature_key, default=current) if current else vol.Optional(feature_key)
            schema_dict[opt_key] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain=HA_FEATURE_DOMAINS[feature_key])
            )
        return vol.Schema(schema_dict)

    def _extract_device_from_input(
        self, user_input: dict, device_id: str | None = None, device_type: str | None = None
    ) -> dict:
        """Build a device dict from validated form input."""
        features = {
            key: val
            for key in HA_FEATURE_DOMAINS
            if (val := user_input.get(key))
        }
        return {
            "id": device_id or str(uuid.uuid4()),
            "name": user_input["name"],
            "type": device_type,
            "features": features,
        }

    def _save_ha_devices(self, ha_devices: list) -> FlowResult:
        """Persist updated ha_devices list and close the options flow."""
        return self.async_create_entry(
            title="",
            data={**self.config_entry.options, CONF_HA_DEVICES: ha_devices},
        )

    async def _handle_device_removal(self, disabled_oems: list[str] | set[str]) -> None:
        """Remove devices from the registry for OEMs that have been disabled."""
        if not disabled_oems:
            return

        device_registry = dr.async_get(self.hass)
        
        # Get the HCU client to check actual device data
        # The registry might have stale manufacturer info (e.g. "eQ-3" for Hue devices)
        coordinator: "HcuCoordinator" | None = self.hass.data.get(DOMAIN, {}).get(
            self.config_entry.entry_id
        )
        client: HcuApiClient | None = coordinator.client if coordinator else None

        if not client:
            _LOGGER.warning("Cannot check device details for removal: HCU client not available")
            return
            
        disabled_oems_set = set(disabled_oems)

        all_devices = dr.async_entries_for_config_entry(
            device_registry, self.config_entry.entry_id
        )

        for device in all_devices:
            # Resolve the real manufacturer using live data from the HCU
            # Device registry identifiers are tuples like (DOMAIN, device_id)
            device_id = next(
                (x[1] for x in device.identifiers if x[0] == DOMAIN), None
            )
            
            manufacturer_to_check = None
            device_data = client.get_device_by_address(device_id) if device_id else None

            if device_data:
                manufacturer_to_check = get_device_manufacturer(device_data)
            else:
                # Fallback for devices not in current state (maybe disconnected?)
                # OR if device_id was not found in identifiers.
                # The registry manufacturer might be stale ("eQ-3" for a Hue device)
                # if registered with an older version.
                # As a secondary fallback, check the model name from the registry.
                if device.model and HUE_MODEL_TOKEN in device.model:
                    manufacturer_to_check = MANUFACTURER_HUE
                else:
                    manufacturer_to_check = device.manufacturer

            if manufacturer_to_check and manufacturer_to_check in disabled_oems_set:
                _LOGGER.info(
                    "Removing device %s (%s) as its manufacturer (%s) has been disabled via options.",
                    device.name,
                    device.id,
                    manufacturer_to_check,
                )
                device_registry.async_remove_device(device.id)

    async def async_step_developer_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage developer settings (advanced debugging and attributes)."""
        if user_input is not None:
            new_options = {**self.config_entry.options}
            new_options[CONF_ADVANCED_DEBUGGING] = user_input[CONF_ADVANCED_DEBUGGING]
            new_options[CONF_ADVANCED_ATTRIBUTES] = user_input[CONF_ADVANCED_ATTRIBUTES]
            return self.async_create_entry(title="", data=new_options)

        schema = {
            vol.Required(
                CONF_ADVANCED_DEBUGGING,
                default=self.config_entry.options.get(CONF_ADVANCED_DEBUGGING, DEFAULT_ADVANCED_DEBUGGING),
            ): BooleanSelector(),
            vol.Required(
                CONF_ADVANCED_ATTRIBUTES,
                default=self.config_entry.options.get(CONF_ADVANCED_ATTRIBUTES, DEFAULT_ADVANCED_ATTRIBUTES),
            ): BooleanSelector(),
        }

        return self.async_show_form(
            step_id="developer_settings", data_schema=vol.Schema(schema)
        )