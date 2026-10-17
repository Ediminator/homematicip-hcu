"""Mock homeassistant.components.repairs for test environment."""


class RepairsFlow:
    """Mock RepairsFlow base class."""

    hass = None

    def async_create_entry(self, title: str = "", data: dict | None = None) -> dict:
        return {"type": "create_entry", "title": title, "data": data or {}}

    def async_show_form(
        self,
        step_id: str = "confirm",
        data_schema=None,
        errors: dict | None = None,
        description_placeholders: dict | None = None,
    ) -> dict:
        return {
            "type": "form",
            "step_id": step_id,
            "description_placeholders": description_placeholders or {},
        }


class ConfirmRepairFlow(RepairsFlow):
    """Mock ConfirmRepairFlow."""
