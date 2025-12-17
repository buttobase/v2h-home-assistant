from __future__ import annotations

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from . import DOMAIN


class NichiconV2HConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Nichicon V2H."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step from the UI."""
        if user_input is not None:
            # We don't ask for any data yet, just create a single entry.
            return self.async_create_entry(title="Nichicon V2H", data={})

        return self.async_show_form(step_id="user")
