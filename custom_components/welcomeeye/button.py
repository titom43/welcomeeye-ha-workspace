from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_NAME
from .coordinator import get_runtime


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    runtime = get_runtime(hass, entry.entry_id)
    async_add_entities([WelcomeEyeOpenDoorButton(entry, runtime)])


class WelcomeEyeOpenDoorButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Open Door"
    _attr_icon = "mdi:door-open"

    def __init__(self, entry: ConfigEntry, runtime) -> None:
        self._entry = entry
        self._runtime = runtime
        self._attr_unique_id = f"{entry.entry_id}_open_door"
        self._attr_device_info = {
            "identifiers": {("welcomeeye", entry.entry_id)},
            "name": entry.data.get(CONF_NAME, "WelcomeEye"),
            "manufacturer": "WelcomeEye",
            "model": "Connect 3",
        }

    async def async_press(self) -> None:
        await self._runtime.async_open_door()
