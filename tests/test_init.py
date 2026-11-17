from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME, STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.integration_template.const import DOMAIN


async def _setup(hass) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="Home", unique_id="home", data={CONF_NAME: "Home"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_and_unload(hass):
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_sensor_state(hass):
    entry = await _setup(hass)

    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_value")
    assert entity_id == "sensor.home_value"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state not in (STATE_UNAVAILABLE, "unknown")
