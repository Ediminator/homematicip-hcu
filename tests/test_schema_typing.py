"""Tests for the schema types of the config flow and the device triggers."""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, get_args, get_type_hints

from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.device_automation.trigger import (
    DeviceAutomationTriggerProtocol,
    async_validate_trigger_config,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowHandler, FlowResultType
from homeassistant.helpers import device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from custom_components.hcu_integration import device_trigger
from custom_components.hcu_integration.const import (
    AUTH_TYPE_PLUGIN,
    CONF_AUTH_TYPE,
    DOMAIN,
)

REPO_ROOT = Path(__file__).parent.parent
PACKAGE_DIR = REPO_ROOT / "custom_components" / "hcu_integration"
SCHEMA_LIBRARIES = {"voluptuous", "probatio"}
SCHEMA_MODULES = ["config_flow.py", "device_trigger.py", "services.py"]

VALID_TRIGGER = {
    "platform": "device",
    "domain": DOMAIN,
    "device_id": "abc123",
    "type": "press_short",
    "subtype": "1",
}


def _is_type_checking_alias(node: ast.stmt) -> bool:
    """Return True for the block that types `vol` as probatio for mypy only."""
    return (
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "TYPE_CHECKING"
        and ast.unparse(node.body) == "import probatio as vol"
        and ast.unparse(node.orelse) == "import voluptuous as vol"
    )


def _schema_library_imports(tree: ast.AST) -> list[str]:
    """Return every import of voluptuous or probatio below `tree`."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        if any(name.split(".")[0] in SCHEMA_LIBRARIES for name in names):
            found.append(f"{node.lineno}: {ast.unparse(node)}")
    return found


def test_only_schema_modules_import_a_schema_library():
    """No other module of the integration imports voluptuous or probatio."""
    importing = sorted(
        path.name
        for path in PACKAGE_DIR.glob("*.py")
        if _schema_library_imports(ast.parse(path.read_text(encoding="utf-8")))
    )
    assert importing == SCHEMA_MODULES


@pytest.mark.parametrize("module_file", SCHEMA_MODULES)
def test_probatio_is_imported_for_type_checking_only(module_file: str):
    """probatio gives the static types, voluptuous is the only runtime import."""
    tree = ast.parse((PACKAGE_DIR / module_file).read_text(encoding="utf-8"))
    alias_blocks = [node for node in tree.body if _is_type_checking_alias(node)]
    assert len(alias_blocks) == 1

    outside = ast.Module(
        body=[node for node in tree.body if node is not alias_blocks[0]],
        type_ignores=[],
    )
    assert _schema_library_imports(outside) == []


def test_mypy_baseline_has_no_schema_type_mismatch():
    """The voluptuous against probatio mismatch must not be baselined again."""
    baseline = (REPO_ROOT / "mypy-baseline.txt").read_text(encoding="utf-8")
    assert [
        line
        for line in baseline.splitlines()
        if "voluptuous" in line or "probatio" in line
    ] == []


ISOLATED_IMPORT_SCRIPT = """
import json
import sys

# Home Assistant 2026.10 and newer import probatio themselves, so load
# Home Assistant and everything the two modules need before blocking
# probatio and its submodules.
import custom_components.hcu_integration.config_flow
import custom_components.hcu_integration.device_trigger

PACKAGE = "custom_components.hcu_integration"
for name in [m for m in sys.modules if m == PACKAGE or m.startswith(PACKAGE + ".")]:
    del sys.modules[name]
for name in [m for m in sys.modules if m.split(".")[0] == "probatio"]:
    sys.modules[name] = None

try:
    from probatio.schema import Schema  # noqa: F401
except ImportError:
    probatio_blocked = True
else:
    probatio_blocked = False

from custom_components.hcu_integration import config_flow, device_trigger

form_schema = config_flow.vol.Schema(
    {config_flow.vol.Required("activation_key"): str}
)
print(
    json.dumps(
        {
            "probatio_blocked": probatio_blocked,
            "trigger": device_trigger.TRIGGER_SCHEMA(json.loads(sys.argv[1])),
            "form": form_schema({"activation_key": "KEY"}),
        }
    )
)
"""


def test_schema_modules_work_without_probatio():
    """Both modules import and validate when probatio cannot be imported.

    Home Assistant 2026.8 and 2026.9 ship voluptuous but not probatio.
    """
    result = subprocess.run(
        [sys.executable, "-c", ISOLATED_IMPORT_SCRIPT, json.dumps(VALID_TRIGGER)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "probatio_blocked": True,
        "trigger": VALID_TRIGGER,
        "form": {"activation_key": "KEY"},
    }


def test_trigger_schema_has_the_type_of_the_protocol():
    """TRIGGER_SCHEMA is what Home Assistant declares for device triggers."""
    expected = get_type_hints(DeviceAutomationTriggerProtocol)["TRIGGER_SCHEMA"]
    assert type(device_trigger.TRIGGER_SCHEMA) is expected
    # Home Assistant picks the static schema only when this hook is absent.
    assert not hasattr(device_trigger, "async_validate_trigger_config")


@pytest.mark.parametrize(
    "name",
    ["async_attach_trigger", "async_get_trigger_capabilities", "async_get_triggers"],
)
def test_trigger_functions_match_the_protocol(name: str):
    """Parameters and type hints equal the Home Assistant protocol."""
    ours = getattr(device_trigger, name)
    theirs = getattr(DeviceAutomationTriggerProtocol, name)
    assert inspect.iscoroutinefunction(ours)
    assert list(inspect.signature(ours).parameters) == [
        param for param in inspect.signature(theirs).parameters if param != "self"
    ]
    assert get_type_hints(ours) == get_type_hints(theirs)


@pytest.mark.parametrize(
    ("trigger_type", "subtype"),
    [
        ("press_short", "1"),
        ("press_long", "2"),
        ("press_long_start", "3"),
        ("press_long_stop", "4"),
        ("ring", "1"),
    ],
)
def test_trigger_schema_accepts_every_trigger_type(trigger_type: str, subtype: str):
    """Each button and doorbell trigger validates to itself."""
    config = {**VALID_TRIGGER, "type": trigger_type, "subtype": subtype}
    assert device_trigger.TRIGGER_SCHEMA(dict(config)) == config


@pytest.mark.parametrize(
    ("change", "path"),
    [
        ({"type": "double_press"}, ["type"]),
        ({"type": None}, ["type"]),
        ({"subtype": 1}, ["subtype"]),
        ({"subtype": None}, ["subtype"]),
        ({"platform": "event"}, ["platform"]),
        ({"device_id": 5}, ["device_id"]),
        ({"unexpected": "x"}, ["unexpected"]),
    ],
)
def test_trigger_schema_rejects_invalid_values(change: dict[str, Any], path: list[str]):
    """A wrong value is rejected and the error names the offending key."""
    with pytest.raises(vol.Invalid) as err:
        device_trigger.TRIGGER_SCHEMA({**VALID_TRIGGER, **change})
    assert err.value.path == path


@pytest.mark.parametrize("missing", ["type", "subtype", "device_id", "domain"])
def test_trigger_schema_requires_every_key(missing: str):
    """Each key of a device trigger is required."""
    config = {key: value for key, value in VALID_TRIGGER.items() if key != missing}
    with pytest.raises(vol.Invalid) as err:
        device_trigger.TRIGGER_SCHEMA(config)
    assert err.value.path == [missing]


async def test_home_assistant_validates_triggers_with_trigger_schema(
    hass: HomeAssistant,
):
    """Home Assistant loads the platform and applies TRIGGER_SCHEMA."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "SGTIN_1")}
    )
    config = {**VALID_TRIGGER, "device_id": device.id}

    assert await async_validate_trigger_config(hass, dict(config)) == config

    with pytest.raises(vol.Invalid) as err:
        await async_validate_trigger_config(hass, {**config, "type": "double_press"})
    assert err.value.path == ["type"]

    with pytest.raises(InvalidDeviceAutomationConfig, match="Unknown device 'gone'"):
        await async_validate_trigger_config(hass, {**config, "device_id": "gone"})


def _declared_form_schema_type() -> type:
    """Return the schema class Home Assistant declares for async_show_form."""
    declared = get_type_hints(FlowHandler.async_show_form)["data_schema"]
    (schema_type,) = [arg for arg in get_args(declared) if arg is not type(None)]
    return schema_type


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_config_flow_form_schema_has_the_declared_type(hass: HomeAssistant):
    """The user step hands Home Assistant the schema type it declares."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert type(result["data_schema"]) is _declared_form_schema_type()
    assert result["data_schema"]({"host": "192.0.2.20"}) == {"host": "192.0.2.20"}


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_options_flow_form_schema_has_the_declared_type(hass: HomeAssistant):
    """The global settings step hands Home Assistant the declared type."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.10", CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN},
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)

    menu = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        menu["flow_id"], user_input={"next_step_id": "global_settings"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "global_settings"
    assert type(result["data_schema"]) is _declared_form_schema_type()
    assert result["data_schema"]({"comfort_temperature": "19"}) == {
        "disable_unconfigured_channels": True,
        "auto_reload_on_device_change": True,
        "comfort_temperature": 19.0,
        "disabled_groups": [],
    }
    with pytest.raises(vol.Invalid) as err:
        result["data_schema"]({"comfort_temperature": "warm"})
    assert err.value.path == ["comfort_temperature"]
