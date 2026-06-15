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
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
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
    CONF_ENTITY_PREFIX,
    CONF_PLATFORM_OVERRIDES,
    CONF_ADVANCED_DEBUGGING,
    CONF_ADVANCED_ATTRIBUTES,
    CONF_DISABLE_UNCONFIGURED_CHANNELS,
    DEFAULT_ADVANCED_DEBUGGING,
    DEFAULT_ADVANCED_ATTRIBUTES,
    DEFAULT_DISABLE_UNCONFIGURED_CHANNELS,
    CONF_DISABLED_GROUPS,
    CONF_SELECTED_OEMS,
    CONF_DISABLED_OEMS,
    CONF_AUTO_RELOAD_ON_DEVICE_CHANGE,
    DEFAULT_AUTO_RELOAD_ON_DEVICE_CHANGE,
    ATTR_END_TIME,
    SUPPORTED_GROUP_TYPES,
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

    VERSION = 4
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

        self._async_abort_entries_match({CONF_HOST: host})

        self._config_data = {
            CONF_HOST: host,
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
        """App User setup: verify button press and fetch token."""
        errors: dict[str, str] = {}
        host = self._config_data[CONF_HOST]
        auth_port = HCU_REST_PORT

        if user_input is not None:
            session = aiohttp_client.async_get_clientsession(self.hass)
            ssl_context = await create_unverified_ssl_context(self.hass)
            try:
                acknowledged = await self._async_is_request_acknowledged(
                    session, host, auth_port, self._app_client_id, self._app_client_auth,
                    self._app_access_point_id, ssl_context,
                )
                if not acknowledged:
                    errors["base"] = "button_not_pressed"
                else:
                    new_token = await self._async_request_app_auth_token(
                        session, host, auth_port, self._app_client_id, self._app_client_auth,
                        self._app_access_point_id, ssl_context,
                    )
                    new_client_id = await self._async_confirm_app_auth_token(
                        session, host, auth_port, self._app_client_id, self._app_client_auth,
                        new_token, self._app_access_point_id, ssl_context,
                    )
                    self._app_new_token = new_token
                    self._app_new_client_id = new_client_id
                    # Store App User data; auth_type + plugin fields set after Plugin step (if dual)
                    self._config_data[CONF_APP_TOKEN] = self._app_new_token
                    self._config_data[CONF_HCU_SGTIN] = self._app_access_point_id
                    self._config_data[CONF_APP_CLIENT_ID] = self._app_new_client_id
                    if self._is_dual_setup:
                        return await self.async_step_auth()
                    self._config_data.pop(CONF_PLUGIN_TOKEN, None)
                    self._config_data.pop(CONF_PLUGIN_CLIENT_ID, None)
                    self._config_data[CONF_AUTH_TYPE] = AUTH_TYPE_APP
                    return await self.async_step_select_oems()
            except (aiohttp.ClientError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"
            except ValueError:
                errors["base"] = "invalid_key"
            except Exception:
                _LOGGER.exception("Unexpected error during App User token confirmation")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="app_auth_confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"hcu_ip": host},
            errors=errors,
        )

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
            # User input contains 'selected_oems' (list of strings).
            # Convert to disabled_oems (those NOT selected).
            selected = set(user_input.get("selected_oems", []))
            disabled_oems = list(third_party_oems - selected)

            return self.async_create_entry(
                title="Homematic IP Local (HCU)",
                data=self._config_data,
                options={"disabled_oems": disabled_oems},
            )

        third_party_oems_list = sorted(third_party_oems)

        # Default: All selected (IMPORT everything by default)
        default_selected = third_party_oems_list

        schema = {
            vol.Required(
                "selected_oems",
                default=default_selected,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=third_party_oems_list,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
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
                self.hass.config_entries.async_update_entry(entry, data=updated_data)
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
            self.hass.config_entries.async_update_entry(entry, data=self._config_data)
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
        """Confirm App User auth: check button press, then fetch and store token."""
        errors = {}
        host = self._config_data[CONF_HOST]
        auth_port = HCU_REST_PORT

        if user_input is not None:
            session = aiohttp_client.async_get_clientsession(self.hass)
            ssl_context = await create_unverified_ssl_context(self.hass)
            try:
                acknowledged = await self._async_is_request_acknowledged(
                    session, host, auth_port, self._app_client_id, self._app_client_auth,
                    self._app_access_point_id, ssl_context
                )
                if not acknowledged:
                    errors["base"] = "button_not_pressed"
                else:
                    new_token = await self._async_request_app_auth_token(
                        session, host, auth_port, self._app_client_id, self._app_client_auth,
                        self._app_access_point_id, ssl_context
                    )
                    new_client_id = await self._async_confirm_app_auth_token(
                        session, host, auth_port, self._app_client_id, self._app_client_auth,
                        new_token, self._app_access_point_id, ssl_context
                    )
                    self._app_new_token = new_token
                    self._app_new_client_id = new_client_id
                    # Store app data in _config_data for use by reconfigure_auth if dual
                    self._config_data[CONF_APP_TOKEN] = self._app_new_token
                    self._config_data[CONF_HCU_SGTIN] = self._app_access_point_id
                    self._config_data[CONF_APP_CLIENT_ID] = self._app_new_client_id
                    if self._is_dual_setup and not self._keep_plugin_token:
                        return await self.async_step_reconfigure_auth()
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
                    self.hass.config_entries.async_update_entry(entry, data=updated_data)
                    return self.async_abort(reason="reconfigure_successful")

            except (aiohttp.ClientError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"
            except ValueError:
                errors["base"] = "invalid_key"
            except Exception:
                _LOGGER.exception("Unexpected error during App User token confirmation.")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reconfigure_app_auth_confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"hcu_ip": host},
            errors=errors,
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
            "deviceName": PLUGIN_FRIENDLY_NAME.get("en", "Home Assistant Integration"),
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
        body = {
            "activationKey": key,
            "pluginId": PLUGIN_ID,
            "friendlyName": PLUGIN_FRIENDLY_NAME,
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
        return self.async_show_menu(
            step_id="init",
            menu_options=["connection_status", "global_settings", "developer_settings", "vacation"],
        )

    async def async_step_connection_status(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show current connection status (read-only)."""
        if user_input is not None:
            return self.async_create_entry(title="", data={})

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
            # Calculate disabled OEMs from inverted selection
            selected = set(user_input.get(CONF_SELECTED_OEMS, []))
            disabled_oems = list(third_party_oems - selected)

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

        # Pre-select everything that is NOT disabled
        default_selected = [oem for oem in third_party_oems_list if oem not in disabled_oems]
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
            vol.Required(
                CONF_SELECTED_OEMS,
                default=default_selected,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=third_party_oems_list,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
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

                return self.async_create_entry(title="", data={})

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