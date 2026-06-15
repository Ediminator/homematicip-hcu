# Contributing to Homematic IP Local (HCU) Integration

Thank you for your interest in contributing! This document provides guidelines and technical information to help you contribute effectively.

---

## 📋 Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Structure](#code-structure)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Common Development Tasks](#common-development-tasks)

---

## Getting Started

### Prerequisites

- Python 3.11 or later
- Home Assistant development environment
- Access to a Homematic IP HCU for testing
- Basic understanding of:
  - Home Assistant integrations
  - Async Python programming
  - WebSocket communication

### First Steps

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/homematicip-hcu.git
   cd homematicip-hcu
   ```
3. **Create a feature branch**:
   ```bash
   git checkout -b feature/my-new-feature
   ```

---

## Development Setup

### Setting Up Home Assistant for Development

1. Install Home Assistant in development mode:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install homeassistant
   ```

2. Create a `config` directory for testing:
   ```bash
   mkdir -p config/custom_components
   ```

3. Symlink the integration:
   ```bash
   ln -s $(pwd)/custom_components/hcu_integration config/custom_components/
   ```

4. Run Home Assistant:
   ```bash
   hass -c config
   ```

### Installing Development Dependencies

```bash
pip install pytest pytest-asyncio pytest-homeassistant-custom-component
pip install black isort mypy  # Code formatting and type checking
```

---

## Code Structure

### Directory Layout

```
homematicip-hcu/
├── custom_components/hcu_integration/
│   ├── __init__.py           # Integration setup, coordinator, services
│   ├── api.py                # HCU API client and WebSocket communication
│   ├── config_flow.py        # Configuration UI
│   ├── const.py              # Constants and mappings
│   ├── entity.py             # Base entity classes
│   ├── discovery.py          # Entity discovery logic
│   ├── util.py               # Utility functions
│   ├── diagnostics.py        # Diagnostics data provider
│   │
│   ├── alarm_control_panel.py  # Platform: Alarm systems
│   ├── binary_sensor.py         # Platform: Binary sensors
│   ├── button.py                # Platform: Buttons
│   ├── climate.py               # Platform: Heating/thermostats
│   ├── cover.py                 # Platform: Blinds/shutters
│   ├── light.py                 # Platform: Lights/dimmers
│   ├── lock.py                  # Platform: Door locks
│   ├── sensor.py                # Platform: Sensors
│   └── switch.py                # Platform: Switches
│
├── tests/
│   ├── conftest.py           # Pytest fixtures
│   ├── test_api.py           # API client tests
│   ├── test_coordinator.py  # Coordinator tests
│   └── test_entity.py        # Entity tests
│
├── .gitignore
├── README.md                 # User documentation
├── CONTRIBUTING.md           # This file
├── CHANGELOG.md              # Version history
└── hacs.json                 # HACS metadata
```

### Key Components

#### 1. API Client (`api.py`)

**Purpose**: Manages WebSocket connection and API communication with the HCU.

**Key Classes**:
- `HcuApiClient`: Main API client handling:
  - WebSocket connection lifecycle
  - Request-response correlation
  - State caching
  - Event processing

**Important Methods**:
- `connect()`: Establishes WebSocket connection
- `listen()`: Continuous message receiving loop
- `_handle_incoming_message()`: Routes incoming messages
- `process_events()`: Updates local state cache from HCU events
- `get_system_state()`: Fetches complete system state
- `async_device_control()`, `async_group_control()`: Send control commands

**API Response Validation**:
The API client includes comprehensive validation:
- Checks response structure types
- Validates presence of required fields
- Handles malformed data gracefully
- Logs warnings for debugging

#### 2. Coordinator (`__init__.py` - `HcuCoordinator`)

**Purpose**: Orchestrates data updates and manages the integration lifecycle.

**Key Responsibilities**:
- Maintains WebSocket connection with auto-reconnection
- Processes incoming events from HCU
- Fires Home Assistant events for button presses
- Manages entity discovery and registration

**Button Event Detection**:
The coordinator supports two button detection methods:
1. **Timestamp-based** (older devices): Compares `lastStatusUpdate` timestamps
2. **Event-based** (newer devices): Direct `DEVICE_CHANNEL_EVENT` messages

**Critical Methods**:
- `_handle_event_message()`: Main event processing pipeline
- `_detect_timestamp_based_button_presses()`: For legacy button devices
- `_handle_device_channel_events()`: For stateless button devices
- `_listen_for_events()`: WebSocket listener with reconnection logic

#### 3. Entity Classes (`entity.py`)

**Purpose**: Base classes for all Home Assistant entities.

**Key Classes**:
- `HcuBaseEntity`: Base for device-channel entities (switches, lights, etc.)
- `HcuGroupBaseEntity`: Base for group entities (heating groups)
- `HcuHomeBaseEntity`: Base for home-level entities

**Entity Naming Logic**:
The `_set_entity_name()` method implements smart naming:
- **With channel label**: Uses label as entity name
- **Without label**: Uses device name (has_entity_name=True)
- **Feature entities**: Appends feature name to label/device name

#### 4. Discovery (`discovery.py`)

**Purpose**: Auto-discovers entities from HCU state data.

**Process**:
1. Iterates through all devices and channels
2. Matches channel types to entity platforms using `HMIP_CHANNEL_TYPE_TO_ENTITY`
3. Matches features to entity classes using `HMIP_FEATURE_TO_ENTITY`
4. Instantiates appropriate entity classes
5. Returns dict of entities grouped by platform

---

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=custom_components.hcu_integration --cov-report=html

# Run specific test file
pytest tests/test_api.py

# Run specific test
pytest tests/test_api.py::test_process_events_device_changed
```

### Test Structure

Tests are organized by component:
- `test_api.py`: API client functionality
- `test_coordinator.py`: Coordinator and event handling
- `test_entity.py`: Base entity classes

### Writing Tests

When adding new functionality:

1. **Add unit tests** for new methods
2. **Test edge cases**:
   - Empty/null data
   - Malformed responses
   - Network errors
3. **Use fixtures** from `conftest.py`:
   ```python
   def test_my_feature(hass, mock_hcu_client, mock_device_data):
       # Your test here
       pass
   ```

4. **Follow existing patterns**:
   ```python
   async def test_async_function(api_client):
       """Test description."""
       # Setup
       api_client._state = {"devices": {}}

       # Execute
       result = await api_client.some_method()

       # Assert
       assert result is not None
       assert result["devices"] == {}
   ```

### Test Coverage Goals

- **Minimum**: 80% code coverage
- **Target**: 90% coverage for core modules (api.py, __init__.py, entity.py)
- **Focus areas**: Error handling, edge cases, state management

---

## Pull Request Process

### Before Submitting

1. **Run tests**: Ensure all tests pass
   ```bash
   pytest
   ```

2. **Format code**: Use Black and isort
   ```bash
   black custom_components/hcu_integration
   isort custom_components/hcu_integration
   ```

3. **Type check** (optional but recommended):
   ```bash
   mypy custom_components/hcu_integration
   ```

4. **Update CHANGELOG.md**: Add your changes under "Unreleased"

5. **Test with real HCU**: If possible, test with actual hardware

### PR Guidelines

**Title Format**:
- `Fix: [brief description]` - Bug fixes
- `Feature: [brief description]` - New features
- `Docs: [brief description]` - Documentation only
- `Refactor: [brief description]` - Code refactoring
- `Test: [brief description]` - Test additions/improvements

**Description Should Include**:
- **What**: What does this PR do?
- **Why**: Why is this change needed?
- **How**: How does it work?
- **Testing**: How was it tested?
- **Screenshots**: If UI changes

**Example**:
```markdown
## What
Adds support for HmIP-FROLL blind control

## Why
Users requested support for this device type (Issue #123)

## How
- Added BLIND_CHANNEL mapping in const.py
- Implemented tilt position control in cover.py
- Added tests for new functionality

## Testing
- Unit tests added
- Tested with real HmIP-FROLL device
- Verified open/close/tilt operations

## Related Issues
Fixes #123
```

### Review Process

1. Automated checks must pass (if configured)
2. Maintainer will review code
3. Address any feedback
4. Once approved, PR will be merged

---

## Coding Standards

### Python Style

Follow [PEP 8](https://pep8.org/) with these additions:
- **Line length**: 100 characters (not strict 79)
- **Formatting**: Use Black (default config)
- **Import sorting**: Use isort
- **Type hints**: Add type hints to all function signatures

### Docstrings

Use Google-style docstrings:

```python
def process_events(self, events: dict[str, Any]) -> set[str]:
    """Process push events from the HCU and update the local state cache.

    This method handles three types of events from the HCU:
    - DEVICE_CHANGED: Updates to device states and channels
    - GROUP_CHANGED: Updates to group configurations
    - HOME_CHANGED: Updates to home-level settings

    Args:
        events: Dictionary of event data from the HCU, where each event
                contains a pushEventType and associated data

    Returns:
        A set of device, group, or home IDs that were updated.
        Empty set if no valid events were processed.

    Raises:
        ValueError: If events parameter is not a dict
    """
```

### Error Handling

**Principle**: Fail gracefully, log comprehensively.

**DO**:
```python
try:
    result = await self._client.async_set_switch_state(device_id, channel, True)
except (HcuApiError, ConnectionError) as err:
    _LOGGER.error("Failed to turn on switch %s: %s", self.name, err)
    self._attr_assumed_state = False
```

**DON'T**:
```python
try:
    result = await self._client.async_set_switch_state(device_id, channel, True)
except:  # Too broad
    pass  # Silent failure
```

### Logging

Use appropriate log levels:
- `_LOGGER.error()`: Errors that affect functionality
- `_LOGGER.warning()`: Unexpected but handled situations
- `_LOGGER.info()`: Important state changes
- `_LOGGER.debug()`: Detailed troubleshooting info

Include context in log messages:
```python
_LOGGER.debug(
    "Button press detected via %s: device=%s, channel=%s",
    reason, device_id, channel_idx
)
```

---

## Common Development Tasks

### Adding Support for a New Device Type

1. **Identify the device channel type**:
   - Get diagnostics from a user with the device
   - Find the `functionalChannelType` in the JSON

2. **Add mapping in `const.py`**:
   ```python
   HMIP_CHANNEL_TYPE_TO_ENTITY = {
       # ... existing mappings ...
       "NEW_CHANNEL_TYPE": ("HcuNewEntity", Platform.SWITCH),
   }
   ```

3. **Create or update entity class** (e.g., in `switch.py`):
   ```python
   class HcuNewEntity(HcuBaseEntity, SwitchEntity):
       """Representation of the new device type."""

       PLATFORM = Platform.SWITCH

       def __init__(self, coordinator, client, device_data, channel_index, **kwargs):
           super().__init__(coordinator, client, device_data, channel_index)
           self._set_entity_name(channel_label=self._channel.get("label"))
           self._attr_unique_id = f"{self._device_id}_{self._channel_index}_new"
   ```

4. **Add tests**:
   - Create test fixtures for the device type
   - Test entity creation and state management

5. **Update documentation**:
   - Add device to supported devices list in README

### Adding a New Service

1. **Define service in `const.py`**:
   ```python
   SERVICE_NEW_ACTION = "new_action"
   ATTR_NEW_PARAM = "new_param"
   ```

2. **Add to `_INTEGRATION_SERVICES` list** in `__init__.py`

3. **Implement handler** in `__init__.py`:
   ```python
   async def handle_new_action(call: ServiceCall) -> None:
       """Handle the new_action service call."""
       param = call.data[ATTR_NEW_PARAM]
       try:
           client = _get_client_for_service()
           await client.async_new_action(param=param)
           _LOGGER.info("Successfully performed new action")
       except (HcuApiError, ConnectionError) as err:
           _LOGGER.error("Error performing new action: %s", err)
   ```

4. **Register in `SERVICES` dict**

5. **Create `services.yaml`** entry (if not exists) describing the service

6. **Add documentation** in README with usage example

### Debugging WebSocket Messages

Enable debug logging to see all WebSocket traffic:

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.hcu_integration: debug
    custom_components.hcu_integration.api: debug
```

Look for these log entries:
- `Sending message to HCU: ...` - Outgoing requests
- `Received HMIP_SYSTEM_RESPONSE: ...` - API responses
- `Button press detected via ...` - Button events
- `WebSocket listener disconnected: ...` - Connection issues

---

## API Response Validation

The integration includes comprehensive API response validation to handle unexpected data gracefully:

### Validation Locations

1. **`get_system_state()`**: Validates structure of initial state response
2. **`process_events()`**: Validates event structure and required fields
3. **`_handle_incoming_message()`**: Validates WebSocket message format

### Adding Validation

When processing API responses, always:

```python
# Check type
if not isinstance(data, dict):
    _LOGGER.warning("Invalid data type: expected dict, got %s", type(data).__name__)
    return

# Check required fields
if "id" not in data:
    _LOGGER.warning("Data missing required 'id' field")
    return

# Use .get() with defaults
device_type = data.get("type", "UNKNOWN")
```

---

## Getting Help

- **Questions**: Open a [GitHub Discussion](https://github.com/Ediminator/homematicip-hcu/discussions)
- **Bug Reports**: Open a [GitHub Issue](https://github.com/Ediminator/homematicip-hcu/issues)
- **Security Issues**: Contact maintainers privately

---

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

**Thank you for contributing!** 🎉
