"""Config flow: one hub entry with global options and a subentry per vehicle."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    DeviceFilterSelectorConfig,
    DeviceSelector,
    DeviceSelectorConfig,
    FileSelector,
    FileSelectorConfig,
    LocationSelector,
    LocationSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_DISCONNECT_GRACE,
    CONF_FIX_TIMEOUT,
    CONF_LIVE_MIN_INTERVAL,
    CONF_LOCATION,
    CONF_MACS,
    CONF_MAX_ACCURACY,
    CONF_PHONES,
    CONF_PICTURE,
    DEFAULT_DISCONNECT_GRACE,
    DEFAULT_FIX_TIMEOUT,
    DEFAULT_LIVE_MIN_INTERVAL,
    DEFAULT_MAX_ACCURACY,
    DOMAIN,
    SUBENTRY_VEHICLE,
)
from .helpers import normalize_mac
from .pictures import store_upload
from .providers import PROVIDERS, discover_phones

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _seconds(minimum: int, maximum: int) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum, max=maximum, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement="s"
        )
    )


class BluetoothDeviceGpsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create the single hub entry; vehicles are added as subentries afterwards."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Confirm the setup (nothing to ask: `single_config_entry` blocks duplicates)."""
        if user_input is not None:
            return self.async_create_entry(title="Bluetooth Device GPS", data={})
        return self.async_show_form(step_id="user")

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls,
        config_entry: ConfigEntry,  # noqa: ARG003
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Vehicles are subentries."""
        return {SUBENTRY_VEHICLE: VehicleSubentryFlow}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:  # noqa: ARG004
        """Global settings."""
        return GlobalOptionsFlow()


class GlobalOptionsFlow(OptionsFlow):
    """Phones, timeouts and accuracy shared by every vehicle."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Edit the global options."""
        if user_input is not None:
            user_input.setdefault(CONF_PHONES, [])
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(CONF_PHONES, default=options.get(CONF_PHONES, [])): DeviceSelector(
                    DeviceSelectorConfig(
                        filter=[
                            DeviceFilterSelectorConfig(integration=p.integration) for p in PROVIDERS
                        ],
                        multiple=True,
                    )
                ),
                vol.Required(
                    CONF_DISCONNECT_GRACE,
                    default=options.get(CONF_DISCONNECT_GRACE, DEFAULT_DISCONNECT_GRACE),
                ): _seconds(0, 600),
                vol.Required(
                    CONF_FIX_TIMEOUT, default=options.get(CONF_FIX_TIMEOUT, DEFAULT_FIX_TIMEOUT)
                ): _seconds(5, 600),
                vol.Required(
                    CONF_MAX_ACCURACY, default=options.get(CONF_MAX_ACCURACY, DEFAULT_MAX_ACCURACY)
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=5, max=500, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement="m"
                    )
                ),
                vol.Required(
                    CONF_LIVE_MIN_INTERVAL,
                    default=options.get(CONF_LIVE_MIN_INTERVAL, DEFAULT_LIVE_MIN_INTERVAL),
                ): _seconds(0, 600),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


def _known_devices(hass: HomeAssistant) -> list[SelectOptionDict]:
    """Bluetooth devices the phones know about, so MACs can be picked instead of typed."""
    options: dict[str, str] = {}
    for phone in discover_phones(hass, set()).values():
        state = hass.states.get(phone.sensor_id)
        if state is None:
            continue
        for mac, label in phone.provider.known_devices(state).items():
            options.setdefault(mac, label)
    return [
        SelectOptionDict(value=mac, label=label)
        for mac, label in sorted(options.items(), key=lambda i: i[1])
    ]


def _validate_macs(
    raw_macs: list[str], entry: ConfigEntry, subentry: ConfigSubentry | None
) -> tuple[set[str], str | None]:
    """Normalise the MACs and return the error key of the first problem, if any."""
    macs = {normalize_mac(raw) for raw in raw_macs}
    if None in macs:
        return set(), "invalid_mac"
    if not macs:
        return set(), "no_macs"
    used = {
        mac
        for other in entry.subentries.values()
        if other.subentry_type == SUBENTRY_VEHICLE
        and (subentry is None or other.subentry_id != subentry.subentry_id)
        for mac in other.data[CONF_MACS]
    }
    if macs & used:
        return set(), "mac_in_use"
    return {mac for mac in macs if mac}, None


class VehicleSubentryFlow(ConfigSubentryFlow):
    """Add or edit a vehicle: name, Bluetooth MACs and an optional picture."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Add a vehicle."""
        return await self._async_vehicle_step("user", user_input)

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> SubentryFlowResult:
        """Choose between editing the vehicle and placing it on the map."""
        return self.async_show_menu(
            step_id="reconfigure", menu_options=["edit_vehicle", "set_location"]
        )

    async def async_step_edit_vehicle(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit name, MACs and picture."""
        return await self._async_vehicle_step("edit_vehicle", user_input)

    async def async_step_set_location(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Place the vehicle by hand on the map (HA's location selector)."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        manager = getattr(entry, "runtime_data", None)
        vehicle = manager.vehicles.get(subentry.subentry_id) if manager else None
        if vehicle is None:
            return self.async_abort(reason="not_loaded")
        if user_input is not None:
            location = user_input[CONF_LOCATION]
            manager.async_set_location(
                vehicle, location["latitude"], location["longitude"], location.get("radius")
            )
            return self.async_abort(reason="location_set")

        fix = vehicle.fix
        start = (
            {"latitude": fix.latitude, "longitude": fix.longitude}
            if fix
            else {
                "latitude": self.hass.config.latitude,
                "longitude": self.hass.config.longitude,
            }
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_LOCATION, default=start): LocationSelector(
                    LocationSelectorConfig(radius=False, icon="mdi:car")
                )
            }
        )
        return self.async_show_form(step_id="set_location", data_schema=schema)

    async def _async_vehicle_step(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> SubentryFlowResult:
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry() if step_id == "edit_vehicle" else None
        errors: dict[str, str] = {}

        if user_input is not None:
            macs, error = _validate_macs(user_input.get(CONF_MACS, []), entry, subentry)
            if error:
                errors[CONF_MACS] = error

            picture = subentry.data.get(CONF_PICTURE) if subentry else None
            if not errors and (file_id := user_input.get(CONF_PICTURE)):
                try:
                    picture = await self.hass.async_add_executor_job(
                        store_upload, self.hass, file_id
                    )
                except ValueError, OSError:
                    errors[CONF_PICTURE] = "invalid_picture"

            if not errors:
                name = user_input[CONF_NAME].strip()
                data = {CONF_MACS: sorted(macs), CONF_PICTURE: picture}
                if subentry is None:
                    return self.async_create_entry(title=name, data=data)
                return self.async_update_and_abort(entry, subentry, title=name, data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_MACS): SelectSelector(
                    SelectSelectorConfig(
                        options=_known_devices(self.hass),
                        multiple=True,
                        custom_value=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_PICTURE): FileSelector(FileSelectorConfig(accept="image/*")),
            }
        )
        suggested = user_input or (
            {CONF_NAME: subentry.title, CONF_MACS: subentry.data[CONF_MACS]} if subentry else {}
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
        )
