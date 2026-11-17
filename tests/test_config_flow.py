from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.bluetooth_device_gps.const import (
    CONF_FIX_TIMEOUT,
    CONF_MACS,
    CONF_PICTURE,
    DOMAIN,
    SUBENTRY_VEHICLE,
)


async def _create_entry(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return result["result"]


async def test_single_instance(hass):
    await _create_entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def _add_vehicle(hass, entry, name, macs):
    flow = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_VEHICLE), context={"source": config_entries.SOURCE_USER}
    )
    assert flow["type"] is FlowResultType.FORM
    return await hass.config_entries.subentries.async_configure(
        flow["flow_id"], {"name": name, CONF_MACS: macs}
    )


async def test_add_vehicle_normalizes_macs(hass):
    entry = await _create_entry(hass)
    result = await _add_vehicle(hass, entry, " Car ", ["00-0e-9f-7f-77-dc"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Car"
    assert result["data"] == {CONF_MACS: ["00:0E:9F:7F:77:DC"], CONF_PICTURE: None}


async def test_vehicle_errors(hass):
    entry = await _create_entry(hass)
    assert (await _add_vehicle(hass, entry, "Car", ["00:0E:9F:7F:77:DC"]))[
        "type"
    ] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    result = await _add_vehicle(hass, entry, "Van", ["nonsense"])
    assert result["errors"] == {CONF_MACS: "invalid_mac"}
    result = await _add_vehicle(hass, entry, "Van", [])
    assert result["errors"] == {CONF_MACS: "no_macs"}
    result = await _add_vehicle(hass, entry, "Van", ["00:0e:9f:7f:77:dc"])
    assert result["errors"] == {CONF_MACS: "mac_in_use"}


async def test_options_flow(hass):
    entry = await _create_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"disconnect_grace": 10, CONF_FIX_TIMEOUT: 30, "max_accuracy": 25},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_FIX_TIMEOUT] == 30
    assert entry.options["phones"] == []
