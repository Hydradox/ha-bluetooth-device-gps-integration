"""Config flow for Integration Template."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME

from .const import DOMAIN

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_NAME): str})


class IntegrationTemplateConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI setup. Add `async_step_reauth` / an options flow when you need them."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the name (replace with the fields your integration needs)."""
        if user_input is not None:
            # Validate the input here (try to connect) and use `errors["base"]` for failures.
            await self.async_set_unique_id(user_input[CONF_NAME].strip().lower())
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input[CONF_NAME].strip(), data=user_input)

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)
