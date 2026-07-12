# custom_components/hcu_integration/api.py
"""API client for communicating with the Homematic IP Home Control Unit (HCU)."""
import aiohttp
import hashlib
import json
import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Any
from uuid import uuid4

from homeassistant.core import HomeAssistant


@dataclass
class ProcessEventsResult:
    """Result of processing a batch of HCU push events."""
    updated: set[str] = field(default_factory=set)
    included: set[str] = field(default_factory=set)
    excluded: set[str] = field(default_factory=set)
    reload_required: set[str] = field(default_factory=set)

    @property
    def all_ids(self) -> set[str]:
        """All device/group IDs touched by this event batch."""
        return self.updated | self.included | self.excluded

from .const import (
    PLUGIN_ID,
    PLUGIN_FRIENDLY_NAME,
    PLUGIN_VERSION,
    PLUGIN_DOCUMENTATION_URL,
    PLUGIN_ISSUE_TRACKER_URL,
    AUTH_TYPE_APP,
    AUTH_TYPE_DUAL,
    AUTH_TYPE_PLUGIN,
    HCU_REST_PORT,
    HCU_PLUGIN_WS_PORT,
    HCU_APP_WS_PORT,
    HCU_DEVICE_TYPES,
    API_REQUEST_TIMEOUT,
    API_PATHS,
    API_MAX_RETRIES,
    API_RETRY_BASE_DELAY,
    WEBSOCKET_HEARTBEAT_INTERVAL,
    WEBSOCKET_RECEIVE_TIMEOUT,
)
from .util import create_unverified_ssl_context

_LOGGER = logging.getLogger(__name__)

# Model type prefixes for auxiliary access points (not primary HCU controllers)
HAP_DRAP_PREFIXES = ("HmIP-HAP", "HmIP-DRAP", "HmIP-WLAN-HAP", "HmIPW-DRAP")


class HcuApiError(Exception):
    """Custom exception for API errors returned by the HCU."""


class HcuApiClient:
    """
    Client for managing the WebSocket connection and communication with the HCU.

    This client handles the WebSocket connection lifecycle, bidirectional message
    exchange, state caching, and provides methods for controlling devices and groups.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        auth_token: str,
        session: aiohttp.ClientSession,
        client_id: str = "",
        auth_type: str = "",
        access_point_id: str = "",
        app_token: str = "",
        advanced_debugging: bool = False,
    ) -> None:
        """Initialize the API client."""
        self.hass = hass
        self._host = host
        self._auth_token = auth_token
        self._auth_type = auth_type
        self._access_point_id = access_point_id
        self._app_token = app_token
        self._advanced_debugging = advanced_debugging
        self._client_auth = (
            hashlib.sha512(
                (access_point_id + "jiLpVitHvWnIGD1yo7MA").encode("utf-8")
            ).hexdigest().upper()
            if access_point_id else ""
        )
        self.plugin_id = PLUGIN_ID
        self._session = session
        # Serializes App User REST commands: concurrent commands (e.g. from an HA
        # group) queue up and are sent one at a time instead of reaching the HCU in
        # parallel, which can cause RF collisions (see #411/#414).
        self._command_lock = asyncio.Lock()
        self._auth_port = HCU_REST_PORT
        # Primary WebSocket: App User (port 8888) or Plugin User (port 9001)
        self._websocket: aiohttp.ClientWebSocketResponse | None = None
        # Secondary WebSocket: Plugin User (port 9001) — only used in AUTH_TYPE_DUAL
        self._plugin_websocket: aiohttp.ClientWebSocketResponse | None = None
        self._state: dict[str, Any] = {"devices": {}, "groups": {}}

        self._pending_requests: dict[str, asyncio.Future[Any]] = {}
        self._event_callback: Callable[[dict[str, Any]], None] | None = None
        self._hcu_device_ids: set[str] = set()
        self._primary_hcu_device_id: str | None = None
        self._plugin_ready_event: asyncio.Event = asyncio.Event()

    @property
    def state(self) -> dict[str, Any]:
        """Return the current cached system state."""
        if not self._state:
            _LOGGER.warning("State cache accessed before initialization.")
        return self._state

    @property
    def hcu_device_id(self) -> str | None:
        """Return the primary HCU's device ID (SGTIN)."""
        return self._primary_hcu_device_id

    @property
    def hcu_part_device_ids(self) -> set[str]:
        """Return all device IDs that are part of the HCU hardware complex."""
        return self._hcu_device_ids

    def _update_hcu_device_ids(self) -> None:
        """Identify devices representing the HCU to correctly associate entities."""
        access_point_id = (self.state.get("home") or {}).get("accessPointId")

        # Collect all access point type devices (HCU, HAP, DRAP, etc.)
        hcu_ids = {
            device_id
            for device_id, device_data in self.state.get("devices", {}).items()
            if device_data.get("type") in HCU_DEVICE_TYPES
        }

        if not hcu_ids:
            _LOGGER.debug("No HCU found by device type, falling back to model type.")
            hcu_ids = {
                device_id
                for device_id, device_data in self.state.get("devices", {}).items()
                if device_data.get("modelType", "").startswith("HmIP-HCU")
            }

        if access_point_id:
            hcu_ids.add(access_point_id)

        self._hcu_device_ids = hcu_ids

        # Prioritize actual HCU models (HmIP-HCU-*) over auxiliary access points (HAP/DRAP)
        # This ensures home-level entities (alarm, vacation, duty cycle) link to the real HCU, not HAP/DRAP
        # The prioritization order is: actual HCU models -> accessPointId (if not HAP/DRAP) -> any access point
        # Rationale: In multi-access-point setups, home.accessPointId may point to an auxiliary HAP/DRAP
        # instead of the main HCU, causing incorrect device associations. By explicitly prioritizing
        # actual HCU model types and excluding HAP/DRAP patterns, we ensure the true central controller
        # is always the primary device.
        devices = self.state.get("devices", {})

        # Sort once and reuse to avoid redundant sorting operations
        sorted_hcu_ids = sorted(hcu_ids)

        # Single-pass candidate selection: build both lists in one iteration
        # This reduces redundant dictionary lookups and improves performance
        primary_hcu_candidates = []
        non_hap_candidates = []

        for device_id in sorted_hcu_ids:
            model_type = devices.get(device_id, {}).get("modelType", "")

            # Skip HAP/DRAP devices
            if model_type.startswith(HAP_DRAP_PREFIXES):
                continue

            # This is a non-HAP candidate
            non_hap_candidates.append(device_id)

            # Check if it's an HCU model (Strategy 1)
            if model_type.startswith("HmIP-HCU"):
                primary_hcu_candidates.append(device_id)

        # Update hcu_device_ids to exclude HAP/DRAP devices
        # HAP/DRAP are separate physical devices, not part of the HCU hardware complex
        # Only actual HCU devices should have their entities linked to the main HCU device
        self._hcu_device_ids = set(non_hap_candidates)

        if primary_hcu_candidates:
            # Use the actual HCU as primary (deterministically select first after sorting)
            self._primary_hcu_device_id = primary_hcu_candidates[0]
            _LOGGER.debug("Selected primary HCU by model type: %s", self._primary_hcu_device_id)
        elif access_point_id:
            # Strategy 2: Use home.accessPointId, but verify it's not a HAP/DRAP
            access_point_model = devices.get(access_point_id, {}).get("modelType", "")
            if not access_point_model.startswith(HAP_DRAP_PREFIXES):
                self._primary_hcu_device_id = access_point_id
                _LOGGER.debug("Selected primary HCU by accessPointId: %s", self._primary_hcu_device_id)
            else:
                # accessPointId is HAP/DRAP, try to find any non-HAP device
                if non_hap_candidates:
                    self._primary_hcu_device_id = non_hap_candidates[0]
                    _LOGGER.warning(
                        "home.accessPointId points to HAP/DRAP (%s), selected non-HAP device as primary: %s",
                        access_point_id, self._primary_hcu_device_id
                    )
                else:
                    # All devices are HAP/DRAP, fall back to access_point_id
                    self._primary_hcu_device_id = access_point_id
                    _LOGGER.warning("Only HAP/DRAP devices found, using accessPointId as primary: %s", access_point_id)
        elif hcu_ids:
            # Strategy 3: Last resort - pick any access point, preferring non-HAP
            if non_hap_candidates:
                self._primary_hcu_device_id = non_hap_candidates[0]
                _LOGGER.debug("Selected primary HCU from available access points: %s", self._primary_hcu_device_id)
            else:
                # All devices are HAP/DRAP, fall back to first available
                self._primary_hcu_device_id = sorted_hcu_ids[0]
                _LOGGER.warning("Only HAP/DRAP devices found, using first available device as primary: %s", self._primary_hcu_device_id)
        else:
            self._primary_hcu_device_id = None

        _LOGGER.debug(
            "Identified HCU parts. Primary ID: %s, All IDs: %s",
            self._primary_hcu_device_id,
            self._hcu_device_ids,
        )

    @property
    def is_connected(self) -> bool:
        """Return True if the primary WebSocket connection is active."""
        return self._websocket is not None and not self._websocket.closed

    @property
    def is_plugin_connected(self) -> bool:
        """Return True if the Plugin User WebSocket connection is active (Dual mode only)."""
        return self._plugin_websocket is not None and not self._plugin_websocket.closed

    @property
    def has_plugin_connection(self) -> bool:
        """Return True if a Plugin User WebSocket is available.

        Plugin-only: primary WS is the Plugin WS.
        DualBridge: secondary Plugin WS.
        App-only: no Plugin WS available.
        """
        if self._auth_type == AUTH_TYPE_DUAL:
            return self.is_plugin_connected
        if self._auth_type in (AUTH_TYPE_PLUGIN, ""):
            return self.is_connected
        return False

    async def connect(self) -> None:
        """Establish a WebSocket connection to the HCU."""
        if self.is_connected:
            await self.disconnect()

        ssl_context = await create_unverified_ssl_context(self.hass)

        if self._auth_type in (AUTH_TYPE_APP, AUTH_TYPE_DUAL) and self._app_token:
            app_headers = {
                "AUTHTOKEN": self._app_token,
                "CLIENTAUTH": self._client_auth,
                "ACCESSPOINT-ID": self._access_point_id,
            }
            # DualBridge always uses port 8888 (Plugin WS on 9001 is the secondary channel).
            # App-only falls back to 9001 if 8888 is unavailable.
            ports = (HCU_APP_WS_PORT,) if self._auth_type == AUTH_TYPE_DUAL else (HCU_APP_WS_PORT, HCU_PLUGIN_WS_PORT)
            for port in ports:
                url = f"wss://{self._host}:{port}"
                _LOGGER.debug("App User: trying WebSocket at %s", url)
                try:
                    self._websocket = await self._session.ws_connect(
                        url,
                        headers=app_headers,
                        ssl=ssl_context,
                        heartbeat=WEBSOCKET_HEARTBEAT_INTERVAL,
                        receive_timeout=WEBSOCKET_RECEIVE_TIMEOUT,
                    )
                    _LOGGER.info("App User WebSocket connected at %s", url)
                    return
                except Exception as e:
                    _LOGGER.debug("App User WebSocket port %d failed: %s", port, e)
                    self._websocket = None
            raise ConnectionError(
                f"App User WebSocket unavailable on port {HCU_APP_WS_PORT}"
                if self._auth_type == AUTH_TYPE_DUAL
                else f"App User WebSocket unavailable on ports {HCU_APP_WS_PORT} and {HCU_PLUGIN_WS_PORT}"
            )

        url = f"wss://{self._host}:{HCU_PLUGIN_WS_PORT}"
        headers = {
            "authtoken": self._auth_token,
            "plugin-id": self.plugin_id,
            "hmip-system-events": "true",
        }
        _LOGGER.info("Connecting to HCU WebSocket at %s", url)
        self._websocket = await self._session.ws_connect(
            url,
            headers=headers,
            ssl=ssl_context,
            heartbeat=WEBSOCKET_HEARTBEAT_INTERVAL,
            receive_timeout=WEBSOCKET_RECEIVE_TIMEOUT,
        )

    async def connect_plugin(self) -> None:
        """Establish the Plugin User WebSocket connection (DualBridge secondary channel)."""
        if self.is_plugin_connected:
            await self.disconnect_plugin()
        url = f"wss://{self._host}:{HCU_PLUGIN_WS_PORT}"
        headers = {
            "authtoken": self._auth_token,
            "plugin-id": self.plugin_id,
            "hmip-system-events": "true",
        }
        ssl_context = await create_unverified_ssl_context(self.hass)
        _LOGGER.info("DualBridge: connecting Plugin WebSocket at %s", url)
        self._plugin_websocket = await self._session.ws_connect(
            url,
            headers=headers,
            ssl=ssl_context,
            heartbeat=WEBSOCKET_HEARTBEAT_INTERVAL,
            receive_timeout=WEBSOCKET_RECEIVE_TIMEOUT,
        )

    async def disconnect_plugin(self) -> None:
        """Close the Plugin User WebSocket connection."""
        if self.is_plugin_connected and self._plugin_websocket:
            _LOGGER.info("DualBridge: closing Plugin WebSocket.")
            await self._plugin_websocket.close()
        self._plugin_websocket = None

    async def _async_get_current_state_rest(self) -> dict[str, Any]:
        """Fetch system state via REST for App Users (POST /hmip/home/getCurrentState).

        The cloud library uses this endpoint (not getSystemState) for App Users.
        Headers: AUTHTOKEN + CLIENTAUTH + ACCESSPOINT-ID
        Body: clientCharacteristics + id (sgtin)
        """
        url = f"https://{self._host}:{self._auth_port}/hmip/home/getCurrentState"
        headers: dict[str, str] = {
            "AUTHTOKEN": self._app_token,
            "VERSION": "12",
        }
        if self._client_auth:
            headers["CLIENTAUTH"] = self._client_auth
        if self._access_point_id:
            headers["ACCESSPOINT-ID"] = self._access_point_id
        body = {
            "clientCharacteristics": {
                "apiVersion": "10",
                "applicationIdentifier": "homematicip-python",
                "applicationVersion": "1.0",
                "deviceManufacturer": "none",
                "deviceType": "Computer",
                "language": "en_US",
                "osType": "Linux",
                "osVersion": "",
            },
            "id": self._access_point_id or "",
        }
        ssl_context = await create_unverified_ssl_context(self.hass)
        _LOGGER.info("App User: fetching state via REST POST %s", url)
        _LOGGER.debug("API → REST POST body=%s", body)
        try:
            async with self._session.post(url, headers=headers, json=body, ssl=ssl_context) as resp:
                if not resp.ok:
                    text = await resp.text()
                    _LOGGER.error(
                        "getCurrentState failed: HTTP %s – %s", resp.status, text[:300]
                    )
                    raise HcuApiError(f"getCurrentState HTTP {resp.status}: {text[:300]}")
                data = await resp.json()
        except (aiohttp.ClientError, ValueError) as err:
            raise HcuApiError(f"getCurrentState request failed: {err}") from err
        if not isinstance(data, dict):
            raise HcuApiError(f"getCurrentState: unexpected response type {type(data)}")

        # The cloud response wraps state under a "body" key; local HCU may not
        state = data.get("body", data)

        state.setdefault("devices", {})
        state.setdefault("groups", {})

        self._state = state
        self._update_hcu_device_ids()
        _LOGGER.debug(
            "getCurrentState OK: %d devices, %d groups",
            len(state.get("devices", {})), len(state.get("groups", {})),
        )
        return self._state

    async def _async_app_rest_call(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """Send a command via REST for App Users (POST https://<host>:<auth_port><path>).

        Used instead of WebSocket for App Users who authenticate on port 6969.

        Serialized via `_command_lock` so that commands to different devices/groups
        fired at the same time (e.g. by an HA group helper) are sent to the HCU one
        at a time instead of in parallel, which can cause RF collisions (#411/#414).
        """
        url = f"https://{self._host}:{self._auth_port}{path}"
        headers: dict[str, str] = {
            "AUTHTOKEN": self._app_token,
            "VERSION": "12",
        }
        if self._client_auth:
            headers["CLIENTAUTH"] = self._client_auth
        if self._access_point_id:
            headers["ACCESSPOINT-ID"] = self._access_point_id
        ssl_context = await create_unverified_ssl_context(self.hass)
        _LOGGER.debug("REST → POST %s  body=%s", path, body)
        async with self._command_lock:
            try:
                async with self._session.post(url, headers=headers, json=body, ssl=ssl_context) as response:
                    if not response.ok:
                        text = await response.text()
                        _LOGGER.error(
                            "App REST call failed: HTTP %s %s – %s", response.status, path, text[:300]
                        )
                        raise HcuApiError(f"HTTP {response.status} for {path}: {text[:300]}")
                    if not response.content_length or response.content_type != "application/json":
                        _LOGGER.debug("REST ← %s  HTTP %s (no body)", path, response.status)
                        return {}
                    result = await response.json()
                    _LOGGER.debug("REST ← %s  HTTP %s  result=%s", path, response.status, result)
                    return result
            except (aiohttp.ClientError, ValueError) as err:
                raise HcuApiError(f"REST call failed for {path}: {err}") from err

    async def async_set_power_up_switch_state(
        self, device_id: str, channel_index: int, state: str
    ) -> None:
        """Set the powerUpSwitchState for an actuator channel (App User REST only)."""
        body = {
            "deviceId": device_id,
            "channelIndex": channel_index,
            "powerUpSwitchState": state,
        }
        await self._async_app_rest_call(
            "/hmip/device/configuration/setPowerUpSwitchState", body
        )

    def register_event_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register a callback to handle incoming event messages."""
        self._event_callback = callback

    def _handle_incoming_message(self, msg: dict[str, Any]) -> None:
        """Route incoming WebSocket messages to appropriate handlers.

        This method processes all incoming messages from the HCU WebSocket and routes
        them to the appropriate handler based on message type:
        - HMIP_SYSTEM_RESPONSE: Resolves pending request futures
        - PLUGIN_*_REQUEST: Plugin lifecycle management
        - Other messages: Passed to the event callback for processing

        Args:
            msg: The incoming message dictionary from the WebSocket.
                 Expected to have 'type' and optionally 'id' fields.
        """
        if not isinstance(msg, dict):
            _LOGGER.warning("Received non-dict message, ignoring: %s", type(msg).__name__)
            return

        msg_type = msg.get("type")
        msg_id = msg.get("id")

        if self._advanced_debugging:
            _LOGGER.debug("API ← %s (id=%s): %s", msg_type, msg_id, msg)

        if msg_type == "HMIP_SYSTEM_RESPONSE" and msg_id in self._pending_requests:
            future = self._pending_requests.pop(msg_id)
            if not future.done():
                response_body = msg.get("body", {})

                # Validate response structure
                if not isinstance(response_body, dict):
                    _LOGGER.error(
                        "Invalid HMIP_SYSTEM_RESPONSE body for request ID %s: expected dict",
                        msg_id
                    )
                    future.set_exception(
                        HcuApiError(f"Invalid response structure: {type(response_body).__name__}")
                    )
                    return

                if response_body.get("code") != 200:
                    _LOGGER.error(
                        "HCU returned an error for request ID %s: %s", msg_id, response_body
                    )
                    future.set_exception(HcuApiError(f"HCU Error: {response_body}"))
                else:
                    pass
                    future.set_result(response_body.get("body"))
        elif msg_type in (
            "PLUGIN_STATE_REQUEST",
            "DISCOVER_REQUEST",
            "CONTROL_REQUEST",
            "CONFIG_TEMPLATE_REQUEST",
            "CONFIG_UPDATE_REQUEST",
        ):
            if not msg_id:
                _LOGGER.warning("Received %s without message ID, cannot respond", msg_type)
                return

            _LOGGER.debug("Received %s: %s", msg_type, msg)

            if msg_type == "CONTROL_REQUEST":
                asyncio.create_task(self._handle_control_request(msg))
            else:
                handler_map = {
                    "PLUGIN_STATE_REQUEST": self._send_plugin_ready,
                    "DISCOVER_REQUEST": self._send_discover_response,
                    "CONFIG_TEMPLATE_REQUEST": self._send_config_template_response,
                    "CONFIG_UPDATE_REQUEST": self._send_config_update_response,
                }
                asyncio.create_task(handler_map[msg_type](msg_id))
        elif self._event_callback:
            self._event_callback(msg)

    async def listen_plugin(self) -> None:
        """DualBridge: listen on the Plugin User WebSocket (port 9001, text frames)."""
        if not self.is_plugin_connected or self._plugin_websocket is None:
            raise ConnectionAbortedError("Plugin WebSocket is not connected.")

        is_dual = self._auth_type == AUTH_TYPE_DUAL

        async for msg in self._plugin_websocket:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = msg.json()
                    if is_dual and data.get("type") not in self._PLUGIN_WS_HANDLED_INCOMING_TYPES:
                        # App User has priority: ignore state events from Plugin WS
                        continue
                    self._handle_incoming_message(data)
                except ValueError as err:
                    _LOGGER.warning("Failed to parse plugin WS JSON: %s", err)
            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                _LOGGER.debug(
                    "WS(plugin) closed/error: type=%s data=%r",
                    msg.type, msg.data,
                )
                raise ConnectionAbortedError(f"Plugin WebSocket issue: {msg.data}")

    async def listen(self) -> None:
        """Listen for incoming WebSocket messages in a continuous loop."""
        if not self.is_connected or self._websocket is None:
            raise ConnectionAbortedError("WebSocket is not connected.")

        try:
            async for msg in self._websocket:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = msg.json()
                        self._handle_incoming_message(data)
                    except ValueError as err:
                        _LOGGER.warning("Failed to parse JSON from WebSocket: %s", err)
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    # App User WebSocket sends JSON-encoded events as binary frames
                    try:
                        data = json.loads(msg.data.decode("utf-8"))
                        self._handle_incoming_message(data)
                    except (ValueError, UnicodeDecodeError) as err:
                        _LOGGER.warning("Failed to parse binary WS message: %s", err)
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    _LOGGER.debug(
                        "WS closed/error: type=%s data=%r extra=%r",
                        msg.type, msg.data, getattr(msg, "extra", None),
                    )
                    raise ConnectionAbortedError(
                        f"WebSocket connection issue: {msg.data}"
                    )
        finally:
            # Clean up any pending requests if the listener stops unexpectedly
            for future in self._pending_requests.values():
                if not future.done():
                    future.set_exception(
                        ConnectionAbortedError("WebSocket listener stopped unexpectedly.")
                    )
            self._pending_requests.clear()

    # Plugin-only message types that must be sent via the Plugin User WebSocket
    _PLUGIN_ONLY_MESSAGE_TYPES: frozenset[str] = frozenset({
        "PLUGIN_STATE_RESPONSE",
        "DISCOVER_RESPONSE",
        "CONTROL_RESPONSE",
        "CONFIG_TEMPLATE_RESPONSE",
        "CONFIG_UPDATE_RESPONSE",
        "CREATE_USER_MESSAGE_REQUEST",
        "DELETE_USER_MESSAGE_REQUEST",
    })

    # In DualBridge mode, only these incoming types are processed from the Plugin WS.
    # All other messages (state events) are handled exclusively by the App User WS.
    _PLUGIN_WS_HANDLED_INCOMING_TYPES: frozenset[str] = frozenset({
        "HMIP_SYSTEM_RESPONSE",
        "PLUGIN_STATE_REQUEST",
        "DISCOVER_REQUEST",
        "CONTROL_REQUEST",
        "CONFIG_TEMPLATE_REQUEST",
        "CONFIG_UPDATE_REQUEST",
        "USER_MESSAGE_ACK_EVENT",
    })

    async def _send_message(self, message: dict[str, Any], log_body: bool = True) -> None:
        """Send a JSON message over the appropriate WebSocket.

        In DualBridge mode, Plugin-only message types are routed to the Plugin
        User WebSocket (port 9001); all other messages go to the primary socket.
        `log_body` can be set to False to suppress the body dump on retries of
        an already-logged message (e.g. from _send_hmip_request's retry loop).
        """
        msg_type = message.get("type")
        is_plugin_route = self._auth_type == AUTH_TYPE_DUAL and msg_type in self._PLUGIN_ONLY_MESSAGE_TYPES
        target = (
            "Plugin WS (DualBridge secondary)"
            if is_plugin_route
            else "App User WS" if self._auth_type in (AUTH_TYPE_APP, AUTH_TYPE_DUAL)
            else "Plugin User WS"
        )
        if log_body:
            _LOGGER.debug("API → %s (%s): %s", msg_type, target, message)
        if is_plugin_route:
            if not self.is_plugin_connected or self._plugin_websocket is None:
                raise ConnectionError("Plugin WebSocket not connected (DualBridge).")
            await self._plugin_websocket.send_json(message)
            return
        if not self.is_connected or self._websocket is None:
            raise ConnectionError("Not connected to HCU WebSocket.")
        await self._websocket.send_json(message)

    async def _send_hmip_request(
        self, path: str, body: dict[str, Any] | None = None, timeout: int = API_REQUEST_TIMEOUT
    ) -> dict[str, Any] | None:
        """
        Send a command to the HCU and wait for a response.

        Wraps the command in an HMIP_SYSTEM_REQUEST envelope over WebSocket.
        For App Users, sends commands via REST on port 6969 instead.
        """
        if self._auth_type in (AUTH_TYPE_APP, AUTH_TYPE_DUAL) and self._app_token:
            return await self._async_app_rest_call(path, body or {})

        message_id = str(uuid4())
        message = {
            "type": "HMIP_SYSTEM_REQUEST",
            "pluginId": self.plugin_id,
            "id": message_id,
            "body": {"path": path, "body": body or {}},
        }

        last_exception = None
        
        for attempt in range(API_MAX_RETRIES):
            future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
            self._pending_requests[message_id] = future

            try:
                await self._send_message(message, log_body=(attempt == 0))
                result = await asyncio.wait_for(future, timeout=timeout)
                if attempt > 0:
                    _LOGGER.info(
                        "Request succeeded on attempt %d/%d for path %s",
                        attempt + 1, API_MAX_RETRIES, path
                    )
                return result
            except (
                ConnectionError,
                ConnectionAbortedError,
                asyncio.TimeoutError,
            ) as err:
                _LOGGER.warning(
                    "Request failed on attempt %d/%d for path %s: %s",
                    attempt + 1, API_MAX_RETRIES, path, err
                )
                last_exception = err
                self._pending_requests.pop(message_id, None)

                # Apply exponential backoff with jitter for retries
                if attempt < API_MAX_RETRIES - 1:
                    delay = API_RETRY_BASE_DELAY * (2 ** attempt)
                    # Add small jitter (0-20% of delay) to prevent thundering herd
                    jitter = delay * 0.2 * (hash(message_id) % 100) / 100
                    total_delay = delay + jitter
                    _LOGGER.debug(
                        "Retrying request for path %s after %.2fs delay (attempt %d)",
                        path, total_delay, attempt + 2
                    )
                    await asyncio.sleep(total_delay)
            except HcuApiError as err:
                # Re-raise specific HcuApiError immediately to be handled by calling functions
                self._pending_requests.pop(message_id, None)
                raise err

        raise HcuApiError(
            f"Request failed after {API_MAX_RETRIES} retries for path {path}"
        ) from last_exception

    async def _send_plugin_ready(self, message_id: str) -> None:
        """Send plugin readiness status and display name to the HCU."""
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
        friendly_name = {lang: f"Home Assistant - {timestamp}" for lang in PLUGIN_FRIENDLY_NAME}
        message = {
            "id": message_id,
            "pluginId": self.plugin_id,
            "type": "PLUGIN_STATE_RESPONSE",
            "body": {
                "pluginReadinessStatus": "READY",
                "friendlyName": friendly_name,
            },
        }
        await self._send_message(message)
        self._plugin_ready_event.set()

    async def _send_discover_response(self, message_id: str) -> None:
        """Notify the HCU if there are devices that need to be registered with it."""
        message = {
            "id": message_id,
            "pluginId": self.plugin_id,
            "type": "DISCOVER_RESPONSE",
            "body": {"success": "true", "devices": []},
        }
        await self._send_message(message)
    
    async def _handle_control_request(self, msg: dict[str, Any]) -> None:
        """Handle control request and Notify the HCU that the control request was successful."""
        msg_id = msg.get("id")
        body = msg.get("body", {})
        device_id = body.get("deviceId")
        
        response = {
            "id": msg_id,
            "pluginId": self.plugin_id,
            "type": "CONTROL_RESPONSE",
            "body": {
                "success": "true",
                "devices": [
                    {
                        "deviceId": device_id,
                    }]
            },
        }
        await self._send_message(response)
    
    async def _send_config_template_response(self, message_id: str) -> None:
        """Respond with plugin configuration template for display on HCUweb.

        Provides read-only status information and useful links so the plugin
        configuration page on HCUweb shows meaningful content instead of a blank page.
        """
        devices = self._state.get("devices", {})
        # Filter out the HCU itself and any auxiliary access points (HAP/DRAP)
        # to show an accurate count of managed end devices.
        # We use prefix matching for robustness against newer hardware models.
        filtered_devices = [
            d
            for d in devices.values()
            if d.get("type") not in HCU_DEVICE_TYPES
            and not (d.get("modelType") or "").startswith(("HmIP-HCU", *HAP_DRAP_PREFIXES))
        ]
        device_count = len(filtered_devices)

        properties = {
            "status": {
                "friendlyName": "Status",
                "description": "Current plugin readiness status",
                "dataType": "READONLY",
                "currentValue": "READY",
                "groupId": "info",
                "order": 1,
            },
            "version": {
                "friendlyName": "Version",
                "description": "Installed integration version",
                "dataType": "READONLY",
                "currentValue": PLUGIN_VERSION,
                "groupId": "info",
                "order": 2,
            },
            "device_count": {
                "friendlyName": "Devices",
                "description": "Number of Homematic IP devices managed by this integration",
                "dataType": "READONLY",
                "currentValue": str(device_count),
                "groupId": "info",
                "order": 3,
            },
            "documentation": {
                "friendlyName": "Documentation",
                "description": "View the integration documentation on GitHub",
                "dataType": "WEBLINK",
                "currentValue": PLUGIN_DOCUMENTATION_URL,
                "defaultValue": "Open Documentation",
                "groupId": "links",
                "order": 1,
            },
            "issue_tracker": {
                "friendlyName": "Issue Tracker",
                "description": "Report bugs or request features",
                "dataType": "WEBLINK",
                "currentValue": PLUGIN_ISSUE_TRACKER_URL,
                "defaultValue": "Open Issue Tracker",
                "groupId": "links",
                "order": 2,
            },
        }

        groups = {
            "info": {
                "friendlyName": "Status",
                "description": "Current integration status",
                "order": 1,
            },
            "links": {
                "friendlyName": "Links",
                "description": "Useful resources",
                "order": 2,
            },
        }

        message = {
            "id": message_id,
            "pluginId": self.plugin_id,
            "type": "CONFIG_TEMPLATE_RESPONSE",
            "body": {"properties": properties, "groups": groups},
        }
        await self._send_message(message)

    async def _send_config_update_response(self, message_id: str) -> None:
        """Acknowledge a configuration update from HCUweb (read-only config, always APPLIED)."""
        message = {
            "id": message_id,
            "pluginId": self.plugin_id,
            "type": "CONFIG_UPDATE_RESPONSE",
            "body": {"status": "APPLIED"},
        }
        await self._send_message(message)

    async def get_system_state(self) -> dict[str, Any]:
        """Fetch the complete system state from the HCU.

        App Users call POST /hmip/home/getCurrentState via REST (same as cloud lib).
        Plugin Users send an HMIP_SYSTEM_REQUEST over WebSocket.
        """
        if self._auth_type in (AUTH_TYPE_APP, AUTH_TYPE_DUAL) and self._app_token:
            return await self._async_get_current_state_rest()

        response_body = await self._send_hmip_request(
            path=API_PATHS["GET_SYSTEM_STATE"], timeout=30
        )

        if not response_body:
            _LOGGER.error("Received empty response from get_system_state")
            return self._state

        # Validate that the response has the expected structure
        if not isinstance(response_body, dict):
            _LOGGER.error(
                "Invalid system state response: expected dict, got %s",
                type(response_body).__name__
            )
            return self._state

        # Ensure critical keys exist with proper defaults
        if "devices" not in response_body:
            _LOGGER.warning("System state missing 'devices' key, initializing empty dict")
            response_body["devices"] = {}

        if "groups" not in response_body:
            _LOGGER.warning("System state missing 'groups' key, initializing empty dict")
            response_body["groups"] = {}

        self._state = response_body
        self._update_hcu_device_ids()
        return self._state

    def get_device_by_address(self, address: str) -> dict[str, Any] | None:
        """Retrieve device data from the local cache by SGTIN (device ID)."""
        return self._state.get("devices", {}).get(address)

    def get_group_by_id(self, group_id: str) -> dict[str, Any] | None:
        """Retrieve group data from the local cache by group ID."""
        return self._state.get("groups", {}).get(group_id)

    def process_events(self, events: dict[str, Any]) -> ProcessEventsResult:
        """
        Process push events from the HCU and update the local state cache.

        Handles the following push event types:
        - DEVICE_CHANGED: Updates to device states and channels
        - GROUP_CHANGED: Updates to group configurations
        - HOME_CHANGED: Updates to home-level settings
        - INCLUSION_EVENT: A new device was paired with the HCU
        - EXCLUSION_EVENT: A device was removed from the HCU

        For devices, partial updates are merged with existing data to preserve
        channel information that wasn't included in the update.

        Args:
            events: Dictionary of event data from the HCU, where each event
                    contains a pushEventType and associated data

        Returns:
            ProcessEventsResult with sets of updated, included, and excluded IDs.
        """
        result = ProcessEventsResult()

        if not isinstance(events, dict):
            _LOGGER.warning("Invalid events parameter: expected dict, got %s", type(events).__name__)
            return result

        for event in sorted(events.values(), key=lambda e: e.get("index", 0)):
            if not isinstance(event, dict):
                _LOGGER.debug("Skipping non-dict event: %s", event)
                continue

            event_type = event.get("pushEventType")
            if event_type not in ("DEVICE_CHANGED", "GROUP_CHANGED", "HOME_CHANGED", "DEVICE_CHANNEL_EVENT", "DEVICE_REMOVED", "GROUP_REMOVED"):
                _LOGGER.debug("Received push event type: %s", event_type)

            if event_type == "DEVICE_REMOVED":
                device_id = event.get("deviceId") or event.get("id") or (event.get("device") or {}).get("id")
                if device_id:
                    self._state.get("devices", {}).pop(device_id, None)
                    result.excluded.add(device_id)
                    _LOGGER.info("Device removed: %s", device_id)
                else:
                    _LOGGER.warning("EXCLUSION event missing device ID")
                continue

            if event_type == "GROUP_REMOVED":
                group_id = event.get("groupId") or event.get("id") or (event.get("group") or {}).get("id")
                if group_id:
                    self._state.get("groups", {}).pop(group_id, None)
                    result.excluded.add(group_id)
                    _LOGGER.info("Group removed: %s", group_id)
                else:
                    _LOGGER.warning("GROUP_REMOVED missing group ID")
                continue


            data_key, data = None, None

            if event_type == "DEVICE_CHANGED":
                data_key, data = "devices", event.get("device")
            elif event_type == "GROUP_CHANGED":
                data_key, data = "groups", event.get("group")
            elif event_type == "HOME_CHANGED":
                data_key, data = "home", event.get("home")

            if not data_key or not data:
                if event_type:
                    _LOGGER.debug(
                        "Skipping event of type '%s' with missing or invalid data", event_type
                    )
                continue

            # Validate that data has required 'id' field
            if not isinstance(data, dict) or "id" not in data:
                _LOGGER.warning(
                    "Event type '%s' has invalid data structure (missing 'id' field)", event_type
                )
                continue

            data_id = data["id"]
            if data_key == "home":
                # Home data is always replaced completely
                self._state["home"] = data
            elif existing_entity := self._state.get(data_key, {}).get(data_id):
                # Detect reload-relevant changes before merging
                if data_key == "devices":
                    _RELOAD_DEVICE_FIELDS = {"label"}
                    _RELOAD_CHANNEL_FIELDS = {"switchVisualization", "channelRole", "label"}
                    for field in _RELOAD_DEVICE_FIELDS:
                        if data.get(field) != existing_entity.get(field):
                            _LOGGER.debug("Device %s field '%s' changed — marking for reload", data_id, field)
                            result.reload_required.add(data_id)
                    if data_id not in result.reload_required:
                        incoming_channels = data.get("functionalChannels", {})
                        existing_channels = existing_entity.get("functionalChannels", {})
                        for ch_idx, ch_data in incoming_channels.items():
                            existing_ch = existing_channels.get(ch_idx, {})
                            for field in _RELOAD_CHANNEL_FIELDS:
                                if ch_data.get(field) != existing_ch.get(field):
                                    _LOGGER.debug("Device %s channel %s field '%s' changed — marking for reload", data_id, ch_idx, field)
                                    result.reload_required.add(data_id)
                                    break
                            if data_id in result.reload_required:
                                break
                elif data_key == "groups":
                    for field in {"label"}:
                        if data.get(field) != existing_entity.get(field):
                            _LOGGER.debug("Group %s field '%s' changed — marking for reload", data_id, field)
                            result.reload_required.add(data_id)

                # Merge partial updates for existing devices/groups.
                # Preserves fields absent from the partial update (e.g., permanentlyReachable).
                for key, value in data.items():
                    if key == "functionalChannels":
                        # Merge channel data at the channel level
                        existing_entity.setdefault("functionalChannels", {})
                        for ch_idx, ch_data in value.items():
                            existing_entity["functionalChannels"].setdefault(ch_idx, {}).update(ch_data)
                    else:
                        existing_entity[key] = value
            else:
                self._state.setdefault(data_key, {})[data_id] = data

            result.updated.add(data_id)

        return result

    # --- Generic Control Methods ---
    async def async_device_control(
        self, path: str, device_id: str, channel_index: int, body: dict[str, Any] | None = None
    ) -> None:
        """Generic method to send a control command to a specific device channel."""
        payload = {"deviceId": device_id, "channelIndex": channel_index, **(body or {})}
        await self._send_hmip_request(path, payload)
    
    async def async_send_api_command(
        self, path: str, body: dict[str, Any] | None = None
    ) -> None:
        """Generic method to send a command to the HCU API."""
        await self._send_hmip_request(path, body)
    
    async def async_create_user_message_request(self, body: dict[str, Any]) -> None:
        """Create User Message Request."""
        message = {
            "id": str(uuid4()),
            "pluginId": self.plugin_id,
            "type": "CREATE_USER_MESSAGE_REQUEST",
            "body": body,
        }
        await self._send_message(message)

    async def async_delete_user_message_request(self, user_message_id: str) -> None:
        """Delete User Message Request."""
        message = {
            "id": str(uuid4()),
            "pluginId": self.plugin_id,
            "type": "DELETE_USER_MESSAGE_REQUEST",
            "body": {"userMessageId": user_message_id},
        }
        await self._send_message(message)
        
    async def async_group_control(
        self, path: str, group_id: str, body: dict[str, Any] | None = None
    ) -> None:
        """Generic method to send a control command to a group."""
        payload = {"groupId": group_id, **(body or {})}
        await self._send_hmip_request(path, payload)

    async def async_home_control(self, path: str, body: dict[str, Any] | None = None) -> None:
        """Generic method to send a control command at the home level."""
        await self._send_hmip_request(path, body or {})

    def _get_api_path_with_optional_time(self, base_path_key: str, with_time_path_key: str, time_value: float | None) -> str:
        """Helper to select API path based on time_value parameter.

        Args:
            base_path_key: The base API path key (e.g., "SET_DIM_LEVEL")
            with_time_path_key: The API path key with time support (e.g., "SET_DIM_LEVEL_WITH_TIME")
            time_value: Optional time parameter (e.g. ramp_time or on_time)

        Returns:
            The appropriate API path from API_PATHS
        """
        if time_value is not None:
            return API_PATHS[with_time_path_key]
        return API_PATHS[base_path_key]

    # --- Specific Device Control Methods ---
    async def async_set_switch_state(self, device_id: str, channel_index: int, is_on: bool, on_time: float | None = None) -> None:
        """Set the state of a switch channel."""
        body = {"on": is_on}
        
        # Determine effective on_time (ignored if switching off)
        effective_on_time = on_time if is_on else None

        if effective_on_time is not None:
            body["onTime"] = effective_on_time
        
        path = self._get_api_path_with_optional_time("SET_SWITCH_STATE", "SET_SWITCH_STATE_WITH_TIME", effective_on_time)
        await self.async_device_control(path, device_id, channel_index, body)

    async def async_set_watering_switch_state(self, device_id: str, channel_index: int, is_on: bool, on_time: float | None = None) -> None:
        
        body = {"wateringActive": is_on}
        effective_on_time = on_time if is_on else None
        if effective_on_time is not None:
            body["wateringTime"] = effective_on_time
        
        path = self._get_api_path_with_optional_time("SET_WATERING_SWITCH_STATE", "SET_WATERING_SWITCH_STATE_WITH_TIME", effective_on_time)
        await self.async_device_control(path, device_id, channel_index, body)

    async def async_set_dim_level(self, device_id: str, channel_index: int, dim_level: float, ramp_time: float | None = None, on_time: float | None = None) -> None:
        body = {"dimLevel": dim_level}
        if ramp_time is not None:
            body["rampTime"] = ramp_time
        if on_time is not None:
            body["onTime"] = on_time
        api_path = self._get_api_path_with_optional_time("SET_DIM_LEVEL", "SET_DIM_LEVEL_WITH_TIME", ramp_time if ramp_time is not None else on_time)
        await self.async_device_control(api_path, device_id, channel_index, body)

    async def async_set_color_temperature(self, device_id: str, channel_index: int, color_temp: int, dim_level: float, ramp_time: float | None = None) -> None:
        body = {"colorTemperature": color_temp, "dimLevel": dim_level}
        if ramp_time is not None:
            body["rampTime"] = ramp_time
        api_path = self._get_api_path_with_optional_time("SET_COLOR_TEMP", "SET_COLOR_TEMP_WITH_TIME", ramp_time)
        await self.async_device_control(api_path, device_id, channel_index, body)

    async def async_set_hue_saturation(self, device_id: str, channel_index: int, hue: int, saturation: float, dim_level: float, ramp_time: float | None = None) -> None:
        body = {"hue": hue, "saturationLevel": saturation, "dimLevel": dim_level}
        if ramp_time is not None:
            body["rampTime"] = ramp_time
        api_path = self._get_api_path_with_optional_time("SET_HUE", "SET_HUE_WITH_TIME", ramp_time)
        await self.async_device_control(api_path, device_id, channel_index, body)

    async def async_set_shutter_level(self, device_id: str, channel_index: int, shutter_level: float) -> None:
        await self.async_device_control(API_PATHS["SET_SHUTTER_LEVEL"], device_id, channel_index, {"shutterLevel": shutter_level})

    async def async_set_primary_shading_level(self, device_id: str, channel_index: int, shading_level: float) -> None:
        """Set primary shading level for SHADING_CHANNEL devices (e.g., HmIP-HDM1)."""
        await self.async_device_control(API_PATHS["SET_PRIMARY_SHADING_LEVEL"], device_id, channel_index, {"primaryShadingLevel": shading_level})

    async def async_set_slats_level(self, device_id: str, channel_index: int, slats_level: float, shutter_level: float | None = None) -> None:
        """Set slats (tilt) level for blind devices.

        Args:
            device_id: The device SGTIN
            channel_index: The channel index
            slats_level: The slats/tilt level (0.0 = open, 1.0 = closed)
            shutter_level: The shutter level to maintain (0.0 = open, 1.0 = closed).
                          If None, current level from device state is used.
        """
        body: dict[str, float] = {"slatsLevel": slats_level}

        # Include shutterLevel as required by API spec
        if shutter_level is not None:
            body["shutterLevel"] = shutter_level
        else:
            # Try to get current shutter level from device state
            device = self.get_device_by_address(device_id)
            if device:
                channel = device.get("functionalChannels", {}).get(str(channel_index), {})
                current_level = channel.get("shutterLevel")
                if current_level is not None:
                    body["shutterLevel"] = current_level
                else:
                    _LOGGER.warning(
                        "Could not determine shutterLevel for device %s channel %s. "
                        "setSlatsLevel API call may fail or behave unexpectedly.",
                        device_id, channel_index
                    )
            else:
                _LOGGER.warning(
                    "Device %s not found in state cache. "
                    "setSlatsLevel API call may fail or behave unexpectedly.",
                    device_id
                )

        await self.async_device_control(API_PATHS["SET_SLATS_LEVEL"], device_id, channel_index, body)

    async def async_stop_cover(self, device_id: str, channel_index: int) -> None:
        await self.async_device_control(API_PATHS["STOP_COVER"], device_id, channel_index)

    async def async_send_door_command(self, device_id: str, channel_index: int, command: str) -> None:
        await self.async_device_control(API_PATHS["SEND_DOOR_COMMAND"], device_id, channel_index, {"doorCommand": command})

    async def async_send_door_impulse(self, device_id: str, channel_index: int) -> None:
        await self.async_device_control(API_PATHS["SEND_DOOR_IMPULSE"], device_id, channel_index)

    async def async_send_identify(self, device_id: str, channel_index: int) -> None:
        await self.async_device_control(API_PATHS["DEVICE_IDENTIFY"], device_id, channel_index)

    async def async_toggle_garage_door_state(self, device_id: str, channel_index: int) -> None:
        await self.async_device_control(API_PATHS["TOGGLE_GARAGE_DOOR_STATE"], device_id, channel_index)

    async def async_set_lock_state(self, device_id: str, channel_index: int, state: str, pin: str | None) -> None:
        """
        Set the lock state (LOCKED, UNLOCKED, or OPEN).
        
        Args:
            device_id: The device SGTIN
            channel_index: The channel index
            state: Target lock state (LOCKED, UNLOCKED, OPEN)
            pin: Authorization PIN (optional - some locks don't require it)
        """
        body = {"targetLockState": state}
        
        # Only include PIN in payload if provided
        if pin:
            body["authorizationPin"] = pin
            
        await self.async_device_control(API_PATHS["SET_LOCK_STATE"], device_id, channel_index, body)

    async def async_pull_latch(self, device_id: str, channel_index: int, pin: str | None) -> None:
        """Pull the door latch."""
        body = {}
        # Only include PIN in payload if provided
        if pin:
            body["authorizationPin"] = pin

        await self.async_device_control(API_PATHS["SEND_PULL_LATCH"], device_id, channel_index, body)

    async def async_set_sound_file(self, device_id: str, channel_index: int, sound_file: str, volume: float, duration: float) -> None:
        await self.async_device_control(API_PATHS["SET_SOUND_FILE"], device_id, channel_index, {"soundFile": sound_file, "volumeLevel": volume, "onTime": duration})

    async def async_reset_energy_counter(self, device_id: str, channel_index: int) -> None:
        await self.async_device_control(API_PATHS["RESET_ENERGY_COUNTER"], device_id, channel_index)

    async def async_reset_water_volume(self, device_id: str, channel_index: int) -> None:
        await self.async_device_control(API_PATHS["RESET_WATER_VOLUME"], device_id, channel_index)

    async def async_enable_simple_rule(self, rule_id: str, enabled: bool) -> None:
        await self.async_home_control(API_PATHS["ENABLE_SIMPLE_RULE"], {"ruleId": rule_id, "enabled": enabled})

    async def async_set_epaper_display(self, device_id: str, channel_index: int, display_data: dict[str, Any]) -> None:
        await self.async_device_control(API_PATHS["SET_EPAPER_DISPLAY"], device_id, channel_index, {"display": display_data})

    # --- Specific Group and Home Control Methods ---
    async def async_set_group_boost(self, group_id: str, boost: bool) -> None:
        await self.async_group_control(API_PATHS["SET_GROUP_BOOST"], group_id, {"boost": boost})

    async def async_set_group_control_mode(self, group_id: str, mode: str, **kwargs: Any) -> None:
        """Set the control mode for a heating group."""
        body = {"controlMode": mode}
        body.update(kwargs)
        await self.async_group_control(API_PATHS["SET_GROUP_CONTROL_MODE"], group_id, body=body)
        
    async def async_set_group_active_profile(self, group_id: str, profile_index: str) -> None:
        """Set the active heating profile for a group."""
        await self.async_group_control(API_PATHS["SET_GROUP_ACTIVE_PROFILE"], group_id, {"profileIndex": profile_index})

    async def async_set_group_setpoint_temperature(self, group_id: str, temperature: float) -> None:
        await self.async_group_control(API_PATHS["SET_GROUP_SET_POINT_TEMP"], group_id, {"setPointTemperature": temperature})

    async def async_set_zones_activation(self, payload: dict[str, Any]) -> None:
        await self.async_home_control(API_PATHS["SET_ZONES_ACTIVATION"], payload)

    async def async_activate_vacation(self, temperature: float, end_time: str) -> None:
        """Activate the vacation mode for the home."""
        await self.async_home_control(
            API_PATHS["ACTIVATE_VACATION"],
            {
                "absenceType": "VACATION",
                "temperature": temperature,
                "endTime": end_time,
            },
        )

    async def async_deactivate_vacation(self) -> None:
        await self.async_home_control(API_PATHS["DEACTIVATE_VACATION"])
        
    async def async_activate_absence_permanent(self) -> None:
        """Activate the permanent absence (Eco) mode for the home."""
        await self.async_home_control(API_PATHS["ACTIVATE_ABSENCE_PERMANENT"])

    async def async_deactivate_absence(self) -> None:
        """Deactivate any absence/eco mode for the home."""
        await self.async_home_control(API_PATHS["DEACTIVATE_ABSENCE"])

    async def async_activate_group_party_mode(
        self, group_id: str, temperature: float, end_time: str
    ) -> None:
        """Activate party mode for a specific heating group."""
        await self.async_group_control(
            API_PATHS["ACTIVATE_PARTY_MODE"],
            group_id,
            {"temperature": temperature, "endTime": end_time},
        )

    async def async_set_switching_group_state(self, group_id: str, on: bool) -> None:
        """Set the on/off state for a switching group."""
        await self.async_group_control(
            API_PATHS["SET_SWITCHING_GROUP_STATE"],
            group_id,
            {"on": on},
        )

    async def async_set_alarm_switching_group_state(
        self,
        group_id: str,
        on: bool,
    ) -> None:
        """Set the state for an ALARM_SWITCHING group (siren).

        Note: The HCU API only accepts the 'on' parameter. The tone (signalAcoustic),
        optical signal (signalOptical), and duration (onTime) are configured as
        properties of the ALARM_SWITCHING group in the HCU itself and cannot be
        set dynamically via this API call.

        Args:
            group_id: The ID of the ALARM_SWITCHING group
            on: Turn the siren on or off
        """
        body = {"on": on}

        await self.async_group_control(
            API_PATHS["SET_SWITCHING_GROUP_STATE"],
            group_id,
            body,
        )

    async def async_test_alarm_signal_acoustic(
        self,
        group_id: str,
        signal_acoustic: str,
    ) -> None:
        """Trigger a test acoustic signal on an ALARM_SWITCHING group.

        Args:
            group_id: The ID of the ALARM_SWITCHING group
            signal_acoustic: The acoustic signal type (e.g. "FREQUENCY_RISING")
        """
        await self.async_group_control(
            API_PATHS["TEST_ALARM_SIGNAL_ACOUSTIC"],
            group_id,
            {"signalAcoustic": signal_acoustic},
        )

    async def async_test_alarm_signal_optical(
        self,
        group_id: str,
        signal_optical: str,
    ) -> None:
        """Trigger a test optical signal on an ALARM_SWITCHING group."""
        await self.async_group_control(
            API_PATHS["TEST_ALARM_SIGNAL_OPTICAL"],
            group_id,
            {"signalOptical": signal_optical},
        )

    async def disconnect(self) -> None:
        """Close all WebSocket connections gracefully."""
        if self.is_connected and self._websocket:
            _LOGGER.info("Closing WebSocket connection.")
            await self._websocket.close()
        self._websocket = None
        await self.disconnect_plugin()
