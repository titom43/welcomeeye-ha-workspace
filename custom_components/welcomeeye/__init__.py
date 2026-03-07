from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WelcomeEyeClient
from .const import (
    CONF_DOOR,
    DATA_RUNTIME,
    DATA_SERVICE_REGISTERED,
    DOMAIN,
    PLATFORMS,
    SERVICE_OPEN_DOOR,
)
from .coordinator import WelcomeEyeRuntime


async def _async_register_services(hass: HomeAssistant) -> None:
    if hass.data[DOMAIN].get(DATA_SERVICE_REGISTERED):
        return

    async def _handle_open_door(call: ServiceCall) -> None:
        entry_id = call.data.get("entry_id")
        if not entry_id:
            # If only one entry exists, allow implicit target.
            runtimes = hass.data[DATA_RUNTIME]
            if len(runtimes) == 1:
                entry_id = next(iter(runtimes))
        runtime: WelcomeEyeRuntime | None = hass.data[DATA_RUNTIME].get(entry_id)
        if not runtime:
            raise HomeAssistantError("No matching WelcomeEye config entry for this service call.")

        result = await runtime.async_open_door(door=call.data.get(CONF_DOOR))
        if not result.get("ok"):
            raise HomeAssistantError(
                f"Open door failed: HTTP {result.get('http_status')} CGI error {result.get('cgi_error')}"
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_OPEN_DOOR,
        _handle_open_door,
        schema=vol.Schema(
            {
                vol.Optional("entry_id"): cv.string,
                vol.Optional(CONF_DOOR): cv.positive_int,
            }
        ),
    )
    hass.data[DOMAIN][DATA_SERVICE_REGISTERED] = True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data.setdefault(DATA_RUNTIME, {})

    client = WelcomeEyeClient(async_get_clientsession(hass), dict(entry.data))
    runtime = WelcomeEyeRuntime(hass, entry.entry_id, client, dict(entry.data))
    hass.data[DATA_RUNTIME][entry.entry_id] = runtime

    await _async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await runtime.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    runtime: WelcomeEyeRuntime = hass.data[DATA_RUNTIME][entry.entry_id]
    await runtime.async_stop()
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DATA_RUNTIME].pop(entry.entry_id, None)
    return unloaded


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True
